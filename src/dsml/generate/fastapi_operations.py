# trace: PRD-APP-102, PRD-APP-103, PRD-APP-106, PRD-APP-110, PRD-APP-116, PRD-APP-117,
# PRD-CORE-044, PRD-CORE-045
"""The custom operation slices of the FastAPI generator.

Each custom operation of an application is one vertical slice in
`app/features/<entity>/<operation>/` (PRD-APP-102, Q37, AD3):

- `endpoint_gen.py`: the router with the endpoint. It validates the input,
  checks the roles, opens a database session and calls the hand-written
  handler (PRD-APP-116).
- `schemas_gen.py`: the Pydantic v2 models of the input and of the output.
- `handler.py`: the hand-written handler. The generator writes it one time
  as a stub, and does not change it after that (PRD-APP-103, PRD-APP-117,
  PRD-CORE-044).

The endpoint calls `handle(data, session, user)` with the typed input
schema, the database session and the user of the token. The handler
returns the typed output schema. Thus a change of the operation in the
model that the handler does not agree with gives a type check error
(PRD-CORE-045, Q15).

The `in` parameters of the operation are the fields of the input schema.
A parameter in the path is a path parameter. The other `in` parameters are
the request body (POST, PUT and PATCH) or the query parameters (GET and
DELETE). A parameter that an entity types gives the key of the entity.

If the operation has one `out` parameter and an entity types it, the output
schema has the fields of the entity. If not, the output schema has one
field for each `out` parameter. An operation with no `out` parameter
returns HTTP 204.

The entity folder of the slice is the table of the first entity of the
`out` parameters, then of the `in` parameters. An operation with no entity
gets a folder with the name of the operation.
"""

import keyword
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from dsml.database.schema import ENUMERATION, ENUMERATION_KINDS, SCALAR_TYPES
from dsml.errors import ToolchainError
from dsml.generate.fastapi_database import Model, import_lines, python_call
from dsml.generate.fastapi_examples import Rules, literal, sample
from dsml.generate.fastapi_slices import (
    FEATURES_FOLDER,
    SchemaField,
    Slice,
    bracket_lines,
    entity_fields,
    from_imports,
    is_public,
    roles_of,
    ruff_order,
    type_imports,
)
from dsml.generate.names import pascal_case, python_name, snake_case
from dsml.ir.model import Element, EnumValue, Ir, ListValue
from dsml.ir.operations import Endpoint, endpoints

HANDLER_FILE: Final = "handler.py"
"""The name of the create-once handler file in a custom slice (PRD-APP-103)."""

BODY_METHODS: Final = frozenset({"patch", "post", "put"})
"""The HTTP methods that send the `in` parameters that are not in the path as a body."""

RESERVED_PARAMETERS: Final = frozenset({"body", "data", "query", "session", "user"})
"""The names of the parameters of the endpoint function. A path parameter cannot use them."""

_PYTHON_TYPES: Final = {
    "Boolean": "bool",
    "Date": "date",
    "DateTime": "datetime",
    "Decimal": "Decimal",
    "Integer": "int",
    "Real": "float",
    "String": "str",
    "Uuid": "UUID",
}
"""The Python type of each DSML scalar type."""

_PARAMETER: Final = re.compile(r"\{([^{}]*)\}")


# trace: PRD-APP-116, PRD-CORE-045
@dataclass(frozen=True, slots=True)
class ParameterField:
    """One `in` or `out` parameter of a custom operation: one field of a schema."""

    name: str
    """The name of the parameter in the model, for example `orderId`."""
    rules: Rules
    """The DSML type of one value. A parameter that an entity types has the type of the key."""
    optional: bool
    """Tell if the lower multiplicity is 0 and the upper multiplicity is 1."""
    many: bool
    """Tell if the upper multiplicity is more than 1."""
    lower: int
    upper: int | None
    in_path: bool = False

    @property
    def json_name(self) -> str:
        """The name of the field in JSON, in snake case, for example `order_id`."""
        return snake_case(self.name)

    @property
    def attribute(self) -> str:
        """The name of the attribute of the Pydantic model."""
        return python_name(self.name)

    @property
    def value_alias(self) -> str | None:
        """The name of the type alias of the values of an enumeration, or `None`."""
        if self.rules.kind != ENUMERATION:
            return None
        return f"{pascal_case(self.json_name)}Value"

    @property
    def value_alias_lines(self) -> list[str]:
        """Give the lines of the type alias of an enumeration parameter and its docstring."""
        assert self.value_alias is not None
        items = [literal(value) for value in self.rules.values]
        return [
            *bracket_lines(f"{self.value_alias} = Literal", items),
            f'"""The values of the field `{self.json_name}`."""',
        ]

    @property
    def base_type(self) -> str:
        """The Python type of one value."""
        return self.value_alias or _PYTHON_TYPES[self.rules.kind]

    @property
    def python_type(self) -> str:
        """The Python type of the field: a list, an optional value or one value."""
        if self.many:
            return f"list[{self.base_type}]"
        if self.optional:
            return f"{self.base_type} | None"
        return self.base_type

    @property
    def field_lines(self) -> list[str]:
        """Give the lines of the field in a schema."""
        arguments: list[str] = []
        if self.many:
            if self.lower > 0:
                arguments.append(f"min_length={self.lower}")
            if self.upper is not None:
                arguments.append(f"max_length={self.upper}")
        if self.attribute != self.json_name:
            arguments.append(f"alias={literal(self.json_name)}")
        default = None
        if self.optional:
            default = "None"
        elif self.many and self.lower == 0:
            default = "[]"
        if default is not None and arguments:
            arguments.insert(0, f"default={default}")
        if arguments:
            return python_call(f"{self.attribute}: {self.python_type} = Field", arguments, 1)
        if default is not None:
            return [f"    {self.attribute}: {self.python_type} = {default}"]
        return [f"    {self.attribute}: {self.python_type}"]

    @property
    def sample_literal(self) -> str:
        """Give the Python expression of a correct JSON value for the HTTP tests."""
        value = literal(sample(self.rules, 0))
        return f"[{value}]" if self.many else value


# trace: PRD-APP-102, PRD-APP-103, PRD-APP-110, PRD-APP-116, PRD-APP-117, PRD-CORE-045
@dataclass(frozen=True, slots=True)
class CustomSlice:
    """One custom operation of an application: one slice folder."""

    name: str
    """The name of the slice folder: the exposed element in snake case (`cancel_order`)."""
    entity_folder: str
    """The name of the entity folder, for example `order`."""
    method: str
    """The HTTP method in lower case, for example `post`."""
    path: str
    exposed: str
    """The identity of the `#Exposed` element."""
    operation: str
    """The identity of the `#Operation` action definition."""
    operation_name: str
    collection: str
    """The name of the `#Exposed` element, for example `cancelOrder`."""
    roles: tuple[str, ...]
    public: bool
    inputs: tuple[ParameterField, ...]
    outputs: tuple[ParameterField, ...]
    entity_output: tuple[SchemaField, ...] | None
    """The fields of the entity of the output, or `None` if the output is not one entity."""
    entity_many: bool = False
    """Tell if the output is a list of entities."""
    entity_optional: bool = False
    """Tell if the output is one entity or `None`."""
    entities: tuple[str, ...] = ()
    """The identities of the entities of the parameters."""
    folder_entity: str | None = None
    """The identity of the entity of the entity folder, or `None`."""

    @property
    def folder(self) -> str:
        """The path of the slice folder in the output folder of the application."""
        return f"{FEATURES_FOLDER}/{self.entity_folder}/{self.name}"

    @property
    def package(self) -> str:
        """The Python package of the slice, for example `app.features.order.cancel_order`."""
        return self.folder.replace("/", ".")

    @property
    def elements(self) -> list[str]:
        """The identities of the elements of the slice files."""
        return sorted({self.exposed, self.operation, *self.entities})

    @property
    def prefix(self) -> str:
        """The start of the names of the schema classes, for example `CancelOrder`."""
        return pascal_case(self.name)

    @property
    def input_class(self) -> str:
        return f"{self.prefix}Input"

    @property
    def request_class(self) -> str | None:
        """The name of the schema of the body or of the query parameters, or `None`."""
        if not self.request_fields:
            return None
        return f"{self.prefix}Body" if self.has_body else f"{self.prefix}Query"

    @property
    def output_class(self) -> str | None:
        """The name of the output schema, or `None` if the operation has no output."""
        if self.entity_output is None and not self.outputs:
            return None
        return f"{self.prefix}Output"

    @property
    def result_type(self) -> str:
        """The Python type of the result of `handle` and of the endpoint."""
        if self.output_class is None:
            return "None"
        if self.entity_many:
            return f"list[{self.output_class}]"
        if self.entity_optional:
            return f"{self.output_class} | None"
        return self.output_class

    @property
    def has_body(self) -> bool:
        return self.method in BODY_METHODS

    @property
    def path_fields(self) -> list[ParameterField]:
        return [item for item in self.inputs if item.in_path]

    @property
    def request_fields(self) -> list[ParameterField]:
        """The `in` parameters that are not in the path."""
        return [item for item in self.inputs if not item.in_path]

    @property
    def tag(self) -> str:
        return literal(self.collection)

    @property
    def router(self) -> str:
        return f"{self.name}_router"

    @property
    def route(self) -> str:
        return f"{self.method.upper()} {self.path}"

    @property
    def test_path(self) -> str:
        """The path of the test file in the output folder of the application."""
        return f"tests/test_{self.name}_http_gen.py"

    @property
    def role(self) -> str:
        """A role that the operation permits. A public operation needs no role."""
        return self.roles[0] if self.roles else "dsml-test-role"

    # The lines of schemas_gen.py.

    @property
    def value_aliases(self) -> list[tuple[str, list[str]]]:
        """Give the name and the lines of each type alias of an enumeration, sorted by name."""
        found: dict[str, tuple[tuple[str, ...], list[str]]] = {}
        items: list[tuple[str, tuple[str, ...], list[str]]] = [
            (alias, item.rules.values, item.value_alias_lines)
            for item in (*self.inputs, *self.outputs)
            if (alias := item.value_alias) is not None
        ]
        items.extend(
            (item.value_alias, item.column.values, item.value_alias_lines)
            for item in self.entity_output or ()
            if item.column.values
        )
        for alias, values, lines in items:
            old = found.get(alias)
            if old is not None and old[0] != values:
                raise ToolchainError(
                    f"The schemas of the operation {self.operation_name} have two enumerations "
                    f"with the name {alias}. Give one of the parameters an other name."
                )
            found[alias] = (values, lines)
        return [(alias, found[alias][1]) for alias in sorted(found)]

    @property
    def schema_import_lines(self) -> list[str]:
        python = [
            _PYTHON_TYPES[item.rules.kind]
            for item in (*self.inputs, *self.outputs)
            if item.value_alias is None
        ]
        python.extend(item.column.type.python for item in self.entity_output or ())
        modules = type_imports(python)
        if self.value_aliases:
            modules.setdefault("typing", set()).add("Literal")
        pydantic = {"BaseModel", "ConfigDict"}
        lines = [line for item in (*self.inputs, *self.outputs) for line in item.field_lines]
        lines.extend(line for item in self.entity_output or () for line in item.output_lines)
        if any(" = Field(" in line or line.endswith(" = Field(") for line in lines):
            pydantic.add("Field")
        result = from_imports(modules)
        return [*result, *([""] if result else []), *import_lines("pydantic", ruff_order(pydantic))]

    @property
    def input_field_lines(self) -> list[str]:
        return [line for item in self.inputs for line in item.field_lines]

    @property
    def request_field_lines(self) -> list[str]:
        return [line for item in self.request_fields for line in item.field_lines]

    @property
    def output_field_lines(self) -> list[str]:
        if self.entity_output is not None:
            return [line for item in self.entity_output for line in item.output_lines]
        return [line for item in self.outputs for line in item.field_lines]

    # The lines of endpoint_gen.py.

    @property
    def endpoint_import_lines(self) -> list[str]:
        python = [
            _PYTHON_TYPES[item.rules.kind] for item in self.path_fields if not item.value_alias
        ]
        modules = type_imports(python)
        if self.output_class is None:
            modules.setdefault("http", set()).add("HTTPStatus")
        modules.setdefault("typing", set()).add("Annotated")
        fastapi = {"APIRouter", "Depends"}
        if self.request_class is not None and not self.has_body:
            fastapi.add("Query")
        schemas = {self.input_class}
        if self.request_class is not None:
            schemas.add(self.request_class)
        if self.output_class is not None:
            schemas.add(self.output_class)
        for item in self.path_fields:
            if item.value_alias is not None:
                schemas.add(item.value_alias)
        return [
            *from_imports(modules),
            "",
            *import_lines("fastapi", ruff_order(fastapi)),
            "from sqlalchemy.ext.asyncio import AsyncSession",
            "",
            f"from {self.package}.handler import handle",
            *import_lines(f"{self.package}.schemas_gen", ruff_order(schemas)),
            *(
                []
                if self.public
                else import_lines("app.shared.auth.cognito_gen", ["User", "require_roles"])
            ),
            "from app.shared.db.session_gen import get_session",
        ]

    @property
    def roles_lines(self) -> list[str]:
        items = [literal(role) for role in self.roles]
        if len(items) == 1:
            return [f"ALLOWED_ROLES = ({items[0]},)"]
        return bracket_lines("ALLOWED_ROLES = ", items, "(", ")")

    @property
    def decorator_lines(self) -> list[str]:
        arguments = [literal(self.path)]
        if self.output_class is None:
            arguments.append("status_code=HTTPStatus.NO_CONTENT")
        return python_call(f"@router.{self.method}", arguments, 0)

    @property
    def signature_lines(self) -> list[str]:
        parameters = [f"{item.name}: {item.base_type}" for item in self.path_fields]
        if self.request_class is not None:
            if self.has_body:
                parameters.append(f"body: {self.request_class}")
            else:
                parameters.append(f"query: Annotated[{self.request_class}, Query()]")
        parameters.append("session: Annotated[AsyncSession, Depends(get_session)]")
        if not self.public:
            parameters.append("user: Annotated[User, Depends(require_roles(*ALLOWED_ROLES))]")
        return python_call(f"async def {self.name}", parameters, 0, f" -> {self.result_type}:")

    @property
    def input_lines(self) -> list[str]:
        """Give the lines that make the input schema from the path and the request."""
        items = [f"{literal(item.json_name)}: {item.name}" for item in self.path_fields]
        if not items and self.request_class is None:
            return [f"    data = {self.input_class}()"]
        head = f"    data = {self.input_class}.model_validate("
        if self.request_class is not None:
            dump = f"{'body' if self.has_body else 'query'}.model_dump(by_alias=True)"
            if not items:
                return [f"{head}{dump})"]
            items.append(f"**{dump}")
        line = f"{head}{{{', '.join(items)}}})"
        if len(line) <= 100:
            return [line]
        inner = f"        {{{', '.join(items)}}}"
        if len(inner) <= 100:
            return [head, inner, "    )"]
        return [
            head,
            "        {",
            *(f"            {item}," for item in items),
            "        }",
            "    )",
        ]

    @property
    def call(self) -> str:
        """Give the call of the handler in the endpoint."""
        user = "None" if self.public else "user"
        return f"handle(data, session, {user})"

    # The lines of handler.py.

    @property
    def handler_import_lines(self) -> list[str]:
        schemas = {self.input_class}
        if self.output_class is not None:
            schemas.add(self.output_class)
        return [
            "from sqlalchemy.ext.asyncio import AsyncSession",
            "",
            *import_lines(f"{self.package}.schemas_gen", ruff_order(schemas)),
            "from app.shared.auth.cognito_gen import User",
        ]

    @property
    def user_type(self) -> str:
        """The type of the user of `handle`. A public operation gives `None`."""
        return "User | None" if self.public else "User"

    @property
    def handler_signature_lines(self) -> list[str]:
        parameters = [
            f"data: {self.input_class}",
            "session: AsyncSession",
            f"user: {self.user_type}",
        ]
        return python_call("async def handle", parameters, 0, f" -> {self.result_type}:")

    # The lines of the HTTP test.

    @property
    def test_url(self) -> str:
        """The path of the request of the tests, with a value for each path parameter."""
        values = {item.name: sample(item.rules, 0) for item in self.path_fields}
        return _PARAMETER.sub(lambda match: str(values[match.group(1)]), self.path)

    @property
    def test_path_literal(self) -> str:
        return literal(self.test_url)

    @property
    def role_literal(self) -> str:
        return literal(self.role)

    @property
    def test_request_arguments(self) -> str:
        """Give the argument of the request body or of the query parameters of the tests."""
        return "json=BODY" if self.has_body else "params=QUERY"

    @property
    def request_lines(self) -> list[str]:
        """Give the lines of the request body or of the query parameters of the tests."""
        head = "BODY: dict[str, object] | None" if self.has_body else "QUERY: dict[str, Any] | None"
        if not self.request_fields:
            return [f"{head} = None"]
        lines = [f"{head} = {{"]
        lines.extend(
            f"    {literal(item.json_name)}: {item.sample_literal}," for item in self.request_fields
        )
        lines.append("}")
        return lines


# trace: PRD-APP-102, PRD-APP-110, PRD-APP-116
def custom_slices(
    ir: Ir, application: Element, models: list[Model], crud: list[Slice]
) -> list[CustomSlice]:
    """Give the custom operation slices of an application, sorted by folder.

    A slice folder that an other slice also uses, a path parameter that is
    not an `in` parameter, or a parameter type that the target does not know
    gives a `ToolchainError`. A custom operation needs a database, thus the
    application must have an entity.
    """
    elements: Mapping[str, Element] = {item.identity: item for item in ir.elements}
    by_entity = {model.entity: model for model in models}
    folders = {item.folder for item in crud}
    result: dict[str, CustomSlice] = {}
    for endpoint in endpoints(ir, application.identity):
        if endpoint.crud or endpoint.method is None or endpoint.path is None:
            continue
        operation = elements.get(endpoint.operation)
        if operation is None:
            continue
        if not models:
            raise ToolchainError(
                f"The application {application.name} has the custom operation "
                f"{operation.name}, but no entity. A custom operation needs a database. "
                "Expose an entity in the application."
            )
        item = _custom_slice(endpoint, operation, elements, by_entity)
        if item.folder in folders or item.folder in result:
            raise ToolchainError(
                f"The custom operation {endpoint.exposed.name} of the application "
                f"{application.name} has the slice folder {item.folder}, and an other "
                "operation has the same folder. Give the operation an other name."
            )
        result[item.folder] = item
    return [result[folder] for folder in sorted(result)]


def _custom_slice(
    endpoint: Endpoint,
    operation: Element,
    elements: Mapping[str, Element],
    by_entity: Mapping[str, Model],
) -> CustomSlice:
    assert endpoint.method is not None and endpoint.path is not None
    parameters = sorted(
        (
            item
            for item in elements.values()
            if item.kind == "Parameter" and item.owner == operation.identity
        ),
        key=lambda item: (item.location.sort_key(), item.identity),
    )
    path_names = _PARAMETER.findall(endpoint.path)
    inputs: list[ParameterField] = []
    outputs: list[ParameterField] = []
    entities: list[str] = []
    output_entities: list[tuple[Element, Model]] = []
    for parameter in parameters:
        if parameter.direction not in ("in", "out"):
            raise ToolchainError(
                f"The parameter {parameter.name} of the operation {operation.name} must be an "
                "in parameter or an out parameter."
            )
        rules, entity = _rules(parameter, operation, elements, by_entity)
        if entity is not None:
            entities.append(entity.entity)
            if parameter.direction == "out":
                output_entities.append((parameter, entity))
        lower, upper = _multiplicity(parameter)
        field = ParameterField(
            name=parameter.name,
            rules=rules,
            optional=lower == 0 and upper == 1,
            many=upper is None or upper > 1,
            lower=lower,
            upper=upper,
            in_path=parameter.direction == "in" and parameter.name in path_names,
        )
        (inputs if parameter.direction == "in" else outputs).append(field)
    _check_path(endpoint, operation, inputs, path_names)
    entity_output: tuple[SchemaField, ...] | None = None
    entity_many = entity_optional = False
    if len(outputs) == 1 and output_entities:
        parameter, model = output_entities[0]
        entity_output = entity_fields(model, elements)
        entity_many = outputs[0].many
        entity_optional = outputs[0].optional
        outputs = []
    first = (
        output_entities[0][1]
        if output_entities
        else next((by_entity[identity] for identity in entities), None)
    )
    name = snake_case(endpoint.exposed.name)
    return CustomSlice(
        name=name,
        entity_folder=first.table if first is not None else name,
        method=endpoint.method,
        path=endpoint.path,
        exposed=endpoint.exposed.identity,
        operation=operation.identity,
        operation_name=operation.name,
        collection=endpoint.exposed.name,
        roles=roles_of(endpoint.exposed),
        public=is_public(endpoint.exposed),
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        entity_output=entity_output,
        entity_many=entity_many,
        entity_optional=entity_optional,
        entities=tuple(sorted(set(entities))),
        folder_entity=first.entity if first is not None else None,
    )


def _rules(
    parameter: Element,
    operation: Element,
    elements: Mapping[str, Element],
    by_entity: Mapping[str, Model],
) -> tuple[Rules, Model | None]:
    """Give the DSML type of one value of a parameter, and the model of its entity or `None`."""
    for identity in parameter.types:
        if identity in SCALAR_TYPES:
            return Rules(kind=SCALAR_TYPES[identity]), None
        model = by_entity.get(identity)
        if model is not None:
            keys = [item for item in entity_fields(model, elements) if item.key]
            if len(keys) != 1:
                raise ToolchainError(
                    f"The parameter {parameter.name} of the operation {operation.name} has the "
                    f"entity {model.entity_name}. The entity must have one key field."
                )
            return keys[0].rules, model
        typed = elements.get(identity)
        if typed is not None and typed.kind in ENUMERATION_KINDS:
            return Rules(kind=ENUMERATION, values=_literals(typed)), None
    raise ToolchainError(
        f"The parameter {parameter.name} of the operation {operation.name} has a type that "
        "the FastAPI target does not know. Use a scalar type, an enumeration or an entity."
    )


def _literals(enumeration: Element) -> tuple[str, ...]:
    for item in enumeration.attributes:
        if item.name == "literals" and isinstance(item.value, ListValue):
            return tuple(
                value.literal for value in item.value.items if isinstance(value, EnumValue)
            )
    return ()


def _multiplicity(parameter: Element) -> tuple[int, int | None]:
    multiplicity = parameter.multiplicity
    if multiplicity is None:
        return 1, 1
    return multiplicity.lower, multiplicity.upper


def _check_path(
    endpoint: Endpoint, operation: Element, inputs: list[ParameterField], path_names: list[str]
) -> None:
    by_name = {item.name: item for item in inputs}
    for name in path_names:
        item = by_name.get(name)
        if item is None:
            raise ToolchainError(
                f'The path "{endpoint.path}" of the operation {operation.name} has the '
                f'parameter "{name}". The operation must have an in parameter with this name.'
            )
        if not name.isidentifier() or keyword.iskeyword(name) or name in RESERVED_PARAMETERS:
            raise ToolchainError(
                f'The path parameter "{name}" of the operation {operation.name} is not a '
                "correct Python name. Use an other name, such as orderId."
            )
        if item.many or item.optional:
            raise ToolchainError(
                f'The path parameter "{name}" of the operation {operation.name} must have '
                "the multiplicity [1]."
            )
