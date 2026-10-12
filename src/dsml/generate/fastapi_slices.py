# trace: PRD-APP-102, PRD-APP-103, PRD-APP-106, PRD-APP-110, PRD-APP-111, PRD-APP-112,
# PRD-APP-113, PRD-APP-114, PRD-APP-115
"""The CRUD slices of the FastAPI generator.

Each CRUD operation of an exposed entity is one vertical slice in
`app/features/<entity>/<operation>_<entity>/` (PRD-APP-102, Q37, AD3):

- `endpoint_gen.py`: the router with the endpoint. It checks the token and
  the roles (PRD-APP-008), validates the input and calls the handler.
- `schemas_gen.py`: the Pydantic v2 models of the operation (PRD-APP-111,
  PRD-APP-112, PRD-APP-115).
- `handler_gen.py`: the handler that reads or writes the database
  (PRD-APP-103, PRD-APP-113, PRD-APP-114).

A file of a slice imports only from its own slice and from `app/shared/`
(PRD-APP-106). Thus each slice has its own schemas. The names of the
schema classes start with the name of the slice, for example
`CreateOrderInput`, so the OpenAPI document has no two schemas with one
name.

The methods and the paths come from `dsml.ir.operations`, the module that
the rule STR-009 also uses (PRD-APP-110). The module
`dsml.generate.fastapi_operations` gives the slices of the custom
operations.

The functions of this module also give the data of the HTTP tests of each
exposed entity (`dsml.generate.fastapi_examples`).
"""

import keyword
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from http import HTTPStatus
from typing import Final

from dsml.database.schema import DECIMAL_PRECISION, DECIMAL_SCALE, FIELD_RULES
from dsml.errors import ToolchainError
from dsml.generate.fastapi_database import (
    LINE_LENGTH,
    Model,
    ModelColumn,
    import_lines,
    python_call,
)
from dsml.generate.fastapi_examples import (
    ROWS,
    UNKNOWN_INDEX,
    Invalid,
    Rules,
    invalid_values,
    literal,
    sample,
)
from dsml.generate.names import pascal_case, snake_case
from dsml.ir.model import (
    BooleanValue,
    Element,
    EnumValue,
    IntegerValue,
    Ir,
    ListValue,
    RealValue,
    StringValue,
)
from dsml.ir.operations import Endpoint, attribute, endpoints

FEATURES_FOLDER: Final = "app/features"
"""The folder of the slices, relative to the output folder of the application."""

CRUD_KINDS: Final = ("create", "read", "update", "delete", "list")
"""The CRUD operations in the order of the CRUD table of the FastAPI PRD."""

LIMIT_DEFAULT: Final = 50
"""The default value of `limit` of a `list` operation (PRD-APP-114)."""

LIMIT_MAX: Final = 200
"""The maximum value of `limit` of a `list` operation (PRD-APP-114)."""

GENERATED_KEYS: Final = ("Integer", "Uuid")
"""The key types that the application can make for a new entity.

The create input has no key (PRD-APP-111). The handler makes a UUID key,
and the database makes an integer key.
"""

FIELD_KINDS: Final = {
    "Decimal": "Decimal",
    "UUID": "Uuid",
    "bool": "Boolean",
    "date": "Date",
    "datetime": "DateTime",
    "float": "Real",
    "int": "Integer",
    "str": "String",
}
"""The DSML field type of each Python type of a column."""

_TYPE_IMPORTS: Final = {
    "Decimal": "decimal",
    "UUID": "uuid",
    "date": "datetime",
    "datetime": "datetime",
}
"""The module of each Python type that needs an import."""

PAGE_DOC: Final = "One page of the entities, sorted by key, and the number of all entities."
"""The docstring of the page schema of a `list` operation."""

_ENDPOINT_DOCS: Final = {
    "create": "Add an entity {entity}. Return HTTP 201 with the new entity.",
    "read": "Return the entity {entity} with the key, or HTTP 404.",
    "update": "Change the entity {entity} with the key, or return HTTP 404.",
    "delete": "Delete the entity {entity} with the key. Return HTTP 204, or HTTP 404.",
    "list": "Return one page of the entities {entity}, sorted by key.",
}
"""The docstring of the endpoint function of each CRUD operation."""

_PARAMETER: Final = re.compile(r"\{([^{}]*)\}")
_NUMERIC: Final = re.compile(r"Numeric\((\d+), (\d+)\)")


# trace: PRD-APP-111, PRD-APP-112, PRD-APP-115
@dataclass(frozen=True, slots=True)
class SchemaField:
    """One field of the schemas of an entity: one column of its table.

    A `[0..1]` or `[1]` relation is a foreign key column. Thus the schemas
    give a related entity as its key (PRD-APP-115).
    """

    column: ModelColumn
    rules: Rules

    @property
    def name(self) -> str:
        """The name of the field in JSON: the column name."""
        return self.column.name

    @property
    def attribute(self) -> str:
        """The name of the attribute of the Pydantic model and of the SQLAlchemy model."""
        return self.column.attribute

    @property
    def key(self) -> bool:
        return self.column.primary_key

    @property
    def nullable(self) -> bool:
        return self.column.nullable

    @property
    def unique(self) -> bool:
        return self.column.unique

    @property
    def foreign_table(self) -> str | None:
        """The table that a foreign key column refers to, or `None`."""
        if self.column.foreign_key is None:
            return None
        return self.column.foreign_key.partition(".")[0]

    @property
    def python_type(self) -> str:
        """The Python type of the field. An enumeration has a type alias."""
        if self.column.values:
            return self.value_alias
        return self.column.type.python

    @property
    def value_alias(self) -> str:
        """The name of the type alias of the values of an enumeration field."""
        return f"{pascal_case(self.name)}Value"

    @property
    def value_alias_lines(self) -> list[str]:
        """Give the lines of the type alias of an enumeration field and its docstring."""
        items = [literal(value) for value in self.column.values]
        return [
            *bracket_lines(f"{self.value_alias} = Literal", items),
            f'"""The values of the field `{self.name}`."""',
        ]

    @property
    def constraints(self) -> list[str]:
        """Give the arguments of `Field` for the field rules (PRD-APP-112)."""
        rules = self.rules
        result: list[str] = []
        if rules.min_length is not None:
            result.append(f"min_length={rules.min_length}")
        if rules.max_length is not None:
            result.append(f"max_length={rules.max_length}")
        if rules.min_value is not None:
            result.append(f"ge={literal(rules.min_value)}")
        if rules.max_value is not None:
            result.append(f"le={literal(rules.max_value)}")
        if rules.pattern is not None:
            result.append(f"pattern={literal(rules.pattern)}")
        if rules.kind == "Decimal" and rules.precision is not None:
            result.append(f"max_digits={rules.precision}")
            result.append(f"decimal_places={rules.scale or 0}")
        return result

    def input_lines(self, optional: bool) -> list[str]:
        """Give the lines of the field in an input schema.

        If `optional` is true or the field is nullable, the field has the
        default value `None`.
        """
        arguments = list(self.constraints)
        if self.attribute != self.name:
            arguments.append(f"alias={literal(self.name)}")
        python = self.python_type
        if optional or self.nullable:
            python = f"{python} | None"
            if not arguments:
                return [f"    {self.attribute}: {python} = None"]
            arguments.insert(0, "default=None")
        if not arguments:
            return [f"    {self.attribute}: {python}"]
        return python_call(f"{self.attribute}: {python} = Field", arguments, 1)

    @property
    def output_lines(self) -> list[str]:
        """Give the lines of the field in an output schema."""
        python = f"{self.python_type} | None" if self.nullable else self.python_type
        if self.attribute == self.name:
            return [f"    {self.attribute}: {python}"]
        return python_call(
            f"{self.attribute}: {python} = Field", [f"serialization_alias={literal(self.name)}"], 1
        )


# trace: PRD-APP-102, PRD-APP-103, PRD-APP-110
@dataclass(frozen=True, slots=True)
class Slice:
    """One CRUD operation of an exposed entity: one slice folder."""

    operation: str
    """The CRUD kind, for example `create`."""
    method: str
    """The HTTP method in lower case, for example `post`."""
    path: str
    parameter: str | None
    """The name of the path parameter of the key, for example `id`, or `None`."""
    exposed: str
    """The identity of the `#Exposed` element."""
    collection: str
    """The name of the `#Exposed` element, for example `orders`."""
    model: Model
    roles: tuple[str, ...]
    public: bool
    fields: tuple[SchemaField, ...]

    @property
    def name(self) -> str:
        """The name of the slice folder, for example `create_order`."""
        return f"{self.operation}_{self.model.table}"

    @property
    def folder(self) -> str:
        """The path of the slice folder in the output folder of the application."""
        return f"{FEATURES_FOLDER}/{self.model.table}/{self.name}"

    @property
    def package(self) -> str:
        """The Python package of the slice, for example `app.features.order.create_order`."""
        return self.folder.replace("/", ".")

    @property
    def elements(self) -> list[str]:
        """The identities of the elements of the slice files: the exposed element and the entity."""
        return sorted({self.exposed, self.model.entity})

    @property
    def entity_name(self) -> str:
        return self.model.entity_name

    @property
    def model_class(self) -> str:
        return self.model.class_name

    @property
    def prefix(self) -> str:
        """The start of the names of the schema classes, for example `CreateOrder`."""
        return pascal_case(self.name)

    @property
    def input_class(self) -> str | None:
        """The name of the input schema, or `None` if the operation has no request body."""
        return f"{self.prefix}Input" if self.operation in ("create", "update") else None

    @property
    def output_class(self) -> str | None:
        """The name of the output schema, or `None` if the operation has no response body."""
        return None if self.operation == "delete" else f"{self.prefix}Output"

    @property
    def page_class(self) -> str | None:
        """The name of the schema of the response of a `list` operation."""
        return f"{self.prefix}Page" if self.operation == "list" else None

    @property
    def key(self) -> SchemaField:
        return next(item for item in self.fields if item.key)

    @property
    def input_fields(self) -> tuple[SchemaField, ...]:
        """The fields of the input schema: all fields but the key (PRD-APP-111)."""
        return tuple(item for item in self.fields if not item.key)

    @property
    def required_fields(self) -> list[str]:
        """The names of the input fields that must not be null."""
        return [item.attribute for item in self.input_fields if not item.nullable]

    @property
    def tag(self) -> str:
        """The OpenAPI tag of the endpoint as a Python text: the name of the exposed element."""
        return literal(self.collection)

    @property
    def router(self) -> str:
        """The name of the router of the slice in `app/main_gen.py`."""
        return f"{self.name}_router"

    # The lines of schemas_gen.py.

    @property
    def schema_fields(self) -> tuple[SchemaField, ...]:
        """The fields that the schemas of the slice use."""
        if self.operation == "delete":
            return ()
        return self.fields

    @property
    def value_alias_fields(self) -> list[SchemaField]:
        return [item for item in self.schema_fields if item.column.values]

    @property
    def schema_import_lines(self) -> list[str]:
        if self.operation == "delete":
            return []
        modules = type_imports(item.column.type.python for item in self.schema_fields)
        if self.value_alias_fields:
            modules.setdefault("typing", set()).add("Literal")
        pydantic = {"BaseModel", "ConfigDict"}
        if self.operation in ("create", "update") and any(
            len(item.input_lines(self.operation == "update")) > 1
            or " = Field(" in item.input_lines(self.operation == "update")[0]
            for item in self.input_fields
        ):
            pydantic.add("Field")
        if any(item.attribute != item.name for item in self.fields):
            pydantic.add("Field")
        if self.operation == "update" and self.required_fields:
            pydantic.add("field_validator")
        lines = from_imports(modules)
        return [*lines, *([""] if lines else []), *import_lines("pydantic", ruff_order(pydantic))]

    @property
    def input_field_lines(self) -> list[str]:
        optional = self.operation == "update"
        return [line for item in self.input_fields for line in item.input_lines(optional)]

    @property
    def validator_lines(self) -> list[str]:
        """Give the lines of the decorator of the validator that refuses null."""
        names = [literal(name) for name in self.required_fields]
        return python_call("@field_validator", names, 1)

    @property
    def output_field_lines(self) -> list[str]:
        return [line for item in self.fields for line in item.output_lines]

    # The lines of endpoint_gen.py.

    @property
    def endpoint_import_lines(self) -> list[str]:
        modules = type_imports([self.key.column.type.python] if self.parameter else [])
        if self.operation in ("create", "delete"):
            modules.setdefault("http", set()).add("HTTPStatus")
        modules.setdefault("typing", set()).add("Annotated")
        fastapi = {"APIRouter", "Depends"}
        if self.operation == "list":
            fastapi.add("Query")
        schemas = [name for name in (self.input_class, self.output_class) if name]
        if self.page_class:
            schemas = [self.page_class]
        schema_lines = import_lines(f"{self.package}.schemas_gen", ruff_order(set(schemas)))
        return [
            *from_imports(modules),
            "",
            *import_lines("fastapi", ruff_order(fastapi)),
            "from sqlalchemy.ext.asyncio import AsyncSession",
            "",
            f"from {self.package}.handler_gen import handle",
            *(schema_lines if schemas else []),
            *([] if self.public else ["from app.shared.auth.cognito_gen import require_roles"]),
            "from app.shared.db.session_gen import get_session",
            "from app.shared.errors_gen import problem_responses",
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
        if self.operation == "create":
            arguments.append("status_code=HTTPStatus.CREATED")
        if self.operation == "delete":
            arguments.append("status_code=HTTPStatus.NO_CONTENT")
        if not self.public:
            arguments.append("dependencies=[Depends(require_roles(*ALLOWED_ROLES))]")
        arguments.append(problem_argument(self.problem_statuses))
        return python_call(f"@router.{self.method}", arguments, 0)

    # trace: PRD-APP-004, PRD-APP-008, PRD-APP-113
    @property
    def problem_statuses(self) -> tuple[int, ...]:
        """Give the error statuses of the endpoint, sorted (PRD-APP-113).

        Each CRUD operation has an input, thus it can return HTTP 422. An
        operation that is not public can return HTTP 401 and HTTP 403.
        """
        statuses = {HTTPStatus.UNPROCESSABLE_CONTENT}
        if not self.public:
            statuses.update((HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN))
        if self.parameter:
            statuses.add(HTTPStatus.NOT_FOUND)
        if self.operation in ("create", "update", "delete"):
            statuses.add(HTTPStatus.CONFLICT)
        return tuple(sorted(int(status) for status in statuses))

    @property
    def endpoint_doc(self) -> str:
        """The docstring of the endpoint function: the description in the OpenAPI document."""
        return _ENDPOINT_DOCS[self.operation].format(entity=self.entity_name)

    @property
    def input_doc(self) -> str:
        """The docstring of the input schema."""
        if self.operation == "create":
            return f"The request body. The key `{self.key.name}` is not in the body."
        return "The request body. Each field is optional. A missing field does not change."

    @property
    def output_doc(self) -> str:
        """The docstring of the output schema."""
        return f"The entity {self.entity_name} in a response."

    @property
    def page_doc(self) -> str:
        """The docstring of the page schema of a `list` operation."""
        return PAGE_DOC

    @property
    def signature_lines(self) -> list[str]:
        parameters: list[str] = []
        if self.parameter:
            parameters.append(f"{self.parameter}: {self.key.column.type.python}")
        if self.input_class:
            parameters.append(f"data: {self.input_class}")
        parameters.append("session: Annotated[AsyncSession, Depends(get_session)]")
        if self.operation == "list":
            parameters.append("limit: Annotated[int, Query(ge=1, le=LIMIT_MAX)] = LIMIT_DEFAULT")
            parameters.append("offset: Annotated[int, Query(ge=0)] = 0")
        result = self.page_class or self.output_class or "None"
        return python_call(f"async def {self.name}", parameters, 0, f" -> {result}:")

    @property
    def call(self) -> str:
        """Give the call of the handler in the endpoint."""
        arguments: list[str] = []
        if self.parameter:
            arguments.append(self.parameter)
        if self.input_class:
            arguments.append("data")
        if self.operation == "list":
            arguments.extend(("limit", "offset"))
        arguments.append("session")
        return f"handle({', '.join(arguments)})"

    @property
    def route(self) -> str:
        """The method and the path of the endpoint, for example `POST /orders`."""
        return f"{self.method.upper()} {self.path}"

    # The lines of handler_gen.py.

    @property
    def handler_import_lines(self) -> list[str]:
        python: list[str] = []
        if self.parameter:
            python.append(self.key.column.type.python)
            modules = type_imports(python)
            modules.setdefault("http", set()).add("HTTPStatus")
        else:
            modules = {}
        if self.operation == "create" and self.key.rules.kind == "Uuid":
            modules.setdefault("uuid", set()).add("uuid4")
        lines = [*from_imports(modules), *([""] if modules else [])]
        if self.operation == "list":
            lines.append("from sqlalchemy import func, select")
        lines.append("from sqlalchemy.ext.asyncio import AsyncSession")
        lines.append("")
        schemas = {name for name in (self.input_class, self.output_class, self.page_class) if name}
        if schemas:
            lines.extend(import_lines(f"{self.package}.schemas_gen", ruff_order(schemas)))
        if self.operation in ("create", "update", "delete"):
            lines.append("from app.shared.db.commit_gen import commit")
        lines.extend(import_lines(f"app.shared.db.models.{self.model.module}", [self.model_class]))
        if self.parameter:
            lines.append("from app.shared.errors_gen import ProblemError")
        return lines

    @property
    def handler_signature_lines(self) -> list[str]:
        parameters: list[str] = []
        if self.parameter:
            parameters.append(f"key: {self.key.column.type.python}")
        if self.input_class:
            parameters.append(f"data: {self.input_class}")
        if self.operation == "list":
            parameters.extend(("limit: int", "offset: int"))
        parameters.append("session: AsyncSession")
        result = self.page_class or self.output_class or "None"
        return python_call("async def handle", parameters, 0, f" -> {result}:")

    @property
    def new_row_line(self) -> str:
        """Give the line that makes the new row of a `create` operation."""
        arguments = "**data.model_dump()"
        if self.key.rules.kind == "Uuid":
            arguments = f"{self.key.attribute}=uuid4(), {arguments}"
        return f"    row = {self.model_class}({arguments})"


# trace: PRD-APP-111, PRD-APP-113, PRD-APP-114, PRD-APP-115
@dataclass(frozen=True, slots=True)
class EntityTests:
    """The data of the HTTP tests of the CRUD operations of one exposed entity."""

    exposed: str
    collection: str
    model: Model
    slices: tuple[Slice, ...]
    roles: tuple[str, ...]
    public: bool
    rows: tuple[tuple[tuple[SchemaField, object], ...], ...] = ()
    """The rows of the tests: the value of each field, for each row."""
    parents: tuple[tuple[str, tuple[tuple[str, object], ...]], ...] = ()
    """The rows that the rows of the tests refer to, in the order of insertion."""
    unknown_key: object = None
    problem: str | None = None
    """The reason why the generator cannot make the test values, or `None`."""
    invalid: tuple[tuple[SchemaField, Invalid], ...] = field(default=())

    @property
    def path(self) -> str:
        """The path of the test file in the output folder of the application."""
        return f"tests/test_{snake_case(self.collection)}_http_gen.py"

    @property
    def elements(self) -> list[str]:
        return sorted({self.exposed, self.model.entity})

    @property
    def entity_name(self) -> str:
        return self.model.entity_name

    @property
    def operations(self) -> dict[str, Slice]:
        return {item.operation: item for item in self.slices}

    @property
    def key(self) -> SchemaField:
        return self.slices[0].key

    @property
    def role(self) -> str:
        """A role that the operations permit. A public operation needs no role."""
        return self.roles[0] if self.roles else "dsml-test-role"

    def test_path(self, operation: Slice) -> str:
        """Give the path of an operation with `{key}` in place of the key parameter."""
        if operation.parameter is None:
            return operation.path
        return operation.path.replace(f"{{{operation.parameter}}}", "{key}")

    @property
    def protected_lines(self) -> list[str]:
        items = [
            f"({literal(item.method.upper())}, {literal(self.test_path(item))})"
            for item in self.slices
        ]
        return bracket_lines("PROTECTED = ", items, "[", "]", always_split=True)

    @property
    def path_lines(self) -> list[str]:
        return [
            f"{item.operation.upper()}_PATH = {literal(self.test_path(item))}"
            for item in self.slices
        ]

    @property
    def row_lines(self) -> list[str]:
        lines = ["ROWS: list[dict[str, object]] = ["]
        for row in self.rows:
            lines.append("    {")
            lines.extend(f"        {literal(item.name)}: {literal(value)}," for item, value in row)
            lines.append("    },")
        lines.append("]")
        return lines

    @property
    def parent_lines(self) -> list[str]:
        if not self.parents:
            return ["PARENTS: list[tuple[str, dict[str, object]]] = []"]
        lines = ["PARENTS: list[tuple[str, dict[str, object]]] = ["]
        for table, row in self.parents:
            lines.extend(["    (", f"        {literal(table)},", "        {"])
            lines.extend(f"            {literal(name)}: {literal(value)}," for name, value in row)
            lines.extend(["        },", "    ),"])
        lines.append("]")
        return lines

    @property
    def create_invalid_lines(self) -> list[str]:
        items = [_invalid_param(item, invalid) for item, invalid in self.invalid]
        key = self.key
        value = literal(self._value(1, key))
        items.append(f"pytest.param({literal(key.name)}, {value}, id={literal('key')})")
        return bracket_lines("CREATE_INVALID = ", items, "[", "]", always_split=True)

    @property
    def update_invalid_lines(self) -> list[str]:
        items = [_invalid_param(item, invalid) for item, invalid in self.invalid]
        items.extend(
            f"pytest.param({literal(item.name)}, None, id={literal(f'{item.name}-null')})"
            for item in self.key_free_fields
            if not item.nullable
        )
        return bracket_lines("UPDATE_INVALID = ", items, "[", "]", always_split=True)

    @property
    def key_free_fields(self) -> list[SchemaField]:
        return [item for item, _ in self.rows[0] if not item.key] if self.rows else []

    @property
    def unique_fields(self) -> list[str]:
        return [item.name for item in self.key_free_fields if item.unique]

    @property
    def change_lines(self) -> list[str]:
        """Give the lines of the request body of the update test."""
        changed = next((item for item in self.key_free_fields if item.foreign_table is None), None)
        if changed is None:
            return ["CHANGE: dict[str, object] = {}"]
        return [
            "CHANGE: dict[str, object] = {",
            f"    {literal(changed.name)}: {literal(self._value(1, changed))},",
            "}",
        ]

    @property
    def support_import_lines(self) -> list[str]:
        names = {"SETTINGS", "SKIP_REASON", "api", "assert_same", "headers"}
        if not self.public:
            names.add("NO_ROLE")
        return import_lines("tests.http_support_gen", ruff_order(names))

    def request_lines(
        self, operation: str, path: str, json: str = "", params: str = "", target: str = "response"
    ) -> list[str]:
        """Give the lines of a request of the operation in a test, in a `with` block."""
        arguments = [literal(self.operations[operation].method.upper()), path]
        if json:
            arguments.append(f"json={json}")
        if params:
            arguments.append(f"params={params}")
        arguments.append("headers=headers(ROLE)")
        return python_call(f"{target} = client.request", arguments, 2)

    def _value(self, index: int, item: SchemaField) -> object:
        return next(value for field_, value in self.rows[index] if field_ is item)


def _invalid_param(item: SchemaField, invalid: Invalid) -> str:
    name = f"{item.name}-{invalid.rule}"
    return f"pytest.param({literal(item.name)}, {invalid.expression}, id={literal(name)})"


# trace: PRD-APP-102, PRD-APP-110, PRD-APP-111
def slices(ir: Ir, application: Element, models: list[Model]) -> list[Slice]:
    """Give the CRUD slices of an application, sorted by folder.

    Two operations with one slice folder, a path parameter that is not a
    Python name, or a create operation with a key that the application
    cannot make give a `ToolchainError`.
    """
    by_entity = {model.entity: model for model in models}
    elements: Mapping[str, Element] = {item.identity: item for item in ir.elements}
    result: dict[str, Slice] = {}
    for endpoint in endpoints(ir, application.identity):
        if not endpoint.crud or endpoint.method is None or endpoint.path is None:
            continue
        model = next(
            (by_entity[identity] for identity in endpoint.exposed.types if identity in by_entity),
            None,
        )
        if model is None:
            continue
        item = Slice(
            operation=endpoint.operation,
            method=endpoint.method,
            path=endpoint.path,
            parameter=_parameter(endpoint),
            exposed=endpoint.exposed.identity,
            collection=endpoint.exposed.name,
            model=model,
            roles=roles_of(endpoint.exposed),
            public=is_public(endpoint.exposed),
            fields=entity_fields(model, elements),
        )
        if item.folder in result:
            raise ToolchainError(
                f"The application {application.name} has two {item.operation} operations "
                f"of the entity {model.entity_name}. Expose the entity one time only."
            )
        if item.operation == "create" and item.key.rules.kind not in GENERATED_KEYS:
            raise ToolchainError(
                f"The entity {model.entity_name} has a key of the type {item.key.rules.kind}. "
                "The create operation needs a key of the type Uuid or Integer."
            )
        result[item.folder] = item
    return [result[folder] for folder in sorted(result)]


def _parameter(endpoint: Endpoint) -> str | None:
    assert endpoint.path is not None
    found = _PARAMETER.findall(endpoint.path)
    needs_key = endpoint.operation in ("read", "update", "delete")
    if len(found) != (1 if needs_key else 0):
        expected = "one path parameter for the key" if needs_key else "no path parameter"
        raise ToolchainError(
            f"The {endpoint.operation} operation of {endpoint.exposed.name} has the path "
            f'"{endpoint.path}". The path must have {expected}.'
        )
    if not found:
        return None
    name: str = found[0]
    if not name.isidentifier() or keyword.iskeyword(name) or name in ("data", "session"):
        raise ToolchainError(
            f'The path parameter "{name}" of {endpoint.exposed.name} is not a correct '
            "Python name. Use a name such as id."
        )
    return name


def roles_of(exposed: Element) -> tuple[str, ...]:
    """Give the roles of the attribute `allowedRoles` of an exposed element, sorted."""
    value = attribute(exposed, "allowedRoles")
    if not isinstance(value, ListValue):
        return ()
    return tuple(sorted({item.literal for item in value.items if isinstance(item, EnumValue)}))


def is_public(exposed: Element) -> bool:
    """Tell if an exposed element has `public = true`. Then it needs no token."""
    value = attribute(exposed, "public")
    return isinstance(value, BooleanValue) and value.value


def entity_fields(model: Model, elements: Mapping[str, Element]) -> tuple[SchemaField, ...]:
    """Give the schema fields of an entity: one field for each column of its table."""
    fields = {
        snake_case(item.name): item
        for item in elements.values()
        if item.kind == "Field" and item.owner == model.entity
    }
    return tuple(_field(column, fields.get(column.name)) for column in model.columns)


def _field(column: ModelColumn, element: Element | None) -> SchemaField:
    kind = "Enumeration" if column.values else FIELD_KINDS[column.type.python]
    precision = scale = None
    if kind == "Decimal":
        match = _NUMERIC.fullmatch(column.type.expression)
        precision = int(match.group(1)) if match else DECIMAL_PRECISION
        scale = int(match.group(2)) if match else DECIMAL_SCALE
    values = _rules(element) if element is not None else {}
    pattern = values.get("pattern")
    return SchemaField(
        column,
        Rules(
            kind=kind,
            min_length=_integer(values.get("minLength")),
            max_length=_integer(values.get("maxLength")),
            min_value=_number(values.get("minValue")),
            max_value=_number(values.get("maxValue")),
            pattern=pattern.value if isinstance(pattern, StringValue) else None,
            precision=precision,
            scale=scale,
            values=column.values,
        ),
    )


def _rules(element: Element) -> dict[str, object]:
    return {
        item.name: item.value
        for annotation in element.annotations
        if annotation.name == FIELD_RULES
        for item in annotation.attributes
    }


def _integer(value: object) -> int | None:
    return value.value if isinstance(value, IntegerValue) else None


def _number(value: object) -> int | float | None:
    if isinstance(value, IntegerValue | RealValue):
        return value.value
    return None


# trace: PRD-APP-113, PRD-APP-114, PRD-APP-115
def entity_tests(ir: Ir, items: list[Slice], models: list[Model]) -> list[EntityTests]:
    """Give the data of the HTTP tests of each exposed entity, sorted by test file."""
    by_exposed: dict[str, list[Slice]] = {}
    for item in items:
        by_exposed.setdefault(item.exposed, []).append(item)
    by_table = {model.table: model for model in models}
    elements: Mapping[str, Element] = {item.identity: item for item in ir.elements}
    result: list[EntityTests] = []
    for group in by_exposed.values():
        group.sort(key=lambda item: CRUD_KINDS.index(item.operation))
        result.append(_entity_tests(group, by_table, elements))
    return sorted(result, key=lambda item: item.path)


def _entity_tests(
    group: list[Slice], by_table: Mapping[str, Model], elements: Mapping[str, Element]
) -> EntityTests:
    first = group[0]
    tests = EntityTests(
        exposed=first.exposed,
        collection=first.collection,
        model=first.model,
        slices=tuple(group),
        roles=first.roles,
        public=first.public,
    )
    try:
        parents = _Parents(by_table, elements)
        rows = tuple(
            tuple(
                (item, _row_value(item, index, first.model.table, parents)) for item in first.fields
            )
            for index in range(ROWS)
        )
        for item in first.fields:
            values = [value for row in rows for field_, value in row if field_ is item]
            if (item.unique or item.key) and len({literal(value) for value in values}) < ROWS:
                raise _NoValue(f"three different values of the field {item.name}")
        unknown = sample(first.key.rules, UNKNOWN_INDEX)
        invalid = tuple(
            (item, invalid)
            for item in first.input_fields
            if item.foreign_table is None
            for invalid in invalid_values(item.rules)
        )
    except _NoValue as error:
        return replace(tests, problem=f"The generator cannot make {error}.")
    return replace(
        tests,
        rows=rows,
        parents=tuple(parents.rows),
        unknown_key=unknown,
        invalid=invalid,
    )


class _NoValue(Exception):
    """The generator cannot make a test value."""


def _row_value(item: SchemaField, index: int, table: str, parents: _Parents) -> object:
    target = item.foreign_table
    if target is not None:
        if target == table or target in parents.visiting:
            if item.nullable:
                return None
            raise _NoValue(f"a row for the required relation {item.name}")
        return parents.key(target)
    value = sample(item.rules, index)
    if value is None and not item.nullable:
        raise _NoValue(f"a value of the field {item.name}")
    return value


class _Parents:
    """The rows of the tables that the rows of the tests refer to."""

    def __init__(self, by_table: Mapping[str, Model], elements: Mapping[str, Element]) -> None:
        self.by_table = by_table
        self.elements = elements
        self.rows: list[tuple[str, tuple[tuple[str, object], ...]]] = []
        self.keys: dict[str, object] = {}
        self.visiting: set[str] = set()

    def key(self, table: str) -> object:
        """Give the key of the row of a table. Add the row and its parents first."""
        if table in self.keys:
            return self.keys[table]
        model = self.by_table.get(table)
        if model is None:
            raise _NoValue(f"a row of the table {table}")
        self.visiting.add(table)
        fields = entity_fields(model, self.elements)
        row = tuple((item.name, _row_value(item, 0, table, self)) for item in fields)
        self.visiting.discard(table)
        key = next(item for item in fields if item.key)
        self.keys[table] = next(value for name, value in row if name == key.name)
        self.rows.append((table, row))
        return self.keys[table]


# trace: PRD-CORE-035
def bracket_lines(
    head: str,
    items: list[str],
    opening: str = "[",
    closing: str = "]",
    always_split: bool = False,
) -> list[str]:
    """Give the lines of a list, a tuple or a subscript in the form that `ruff format` gives.

    The items are on one line if the line has 100 characters or fewer.
    If not, each item is on its own line with a comma.
    """
    line = f"{head}{opening}{', '.join(items)}{closing}"
    if items and not always_split and len(line) <= LINE_LENGTH:
        return [line]
    if not items:
        return [f"{head}{opening}{closing}"]
    return [f"{head}{opening}", *(f"    {item}," for item in items), closing]


# trace: PRD-APP-004, PRD-APP-014
def problem_argument(statuses: Iterable[int]) -> str:
    """Give the argument of the route decorator for the problem details responses."""
    return f"responses=problem_responses({', '.join(str(status) for status in statuses)})"


def type_imports(types: Iterable[str]) -> dict[str, set[str]]:
    """Give the modules and the names to import for the Python types."""
    modules: dict[str, set[str]] = {}
    for python in types:
        module = _TYPE_IMPORTS.get(python)
        if module is not None:
            modules.setdefault(module, set()).add(python)
    return modules


def from_imports(modules: Mapping[str, set[str]]) -> list[str]:
    """Give the import lines of the modules, sorted by module."""
    return [
        line
        for module, names in sorted(modules.items())
        for line in import_lines(module, ruff_order(names))
    ]


def ruff_order(names: set[str]) -> list[str]:
    """Sort imported names as ruff sorts them: constants, classes, then other names."""

    def key(name: str) -> tuple[int, str]:
        if name.isupper() and len(name) > 1:
            return (0, name)
        if name[0].isupper():
            return (1, name)
        return (2, name)

    return sorted(names, key=key)
