# trace: PRD-APP-005, PRD-APP-006, PRD-CORE-026
"""The external APIs that a React application calls.

A `react` application can call an external API in place of an application
of the model (PRD-APP-006). The IR adapter converts the OpenAPI file of
each `ExternalApi` element into `Entity`, `Field`, `Relation`, `Operation`
and `Parameter` elements (`dsml.adapter.openapi`, PRD-CORE-055). This
module reads these elements from the IR and gives them to the entities
layer and to the features layer (PRD-CORE-026). It does not read the
OpenAPI file.

The names of the schemas, the properties, the operations and the
parameters are the names of the OpenAPI file. The client sends and reads
the properties with these names. Thus the name of each property and each
parameter must be a TypeScript identifier.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from dsml.database.schema import ENUMERATION, SCALAR_TYPES
from dsml.errors import ToolchainError
from dsml.generate.fastapi_examples import Rules
from dsml.ir.model import Element, Ir, ListValue, StringValue

KIND: Final = "ExternalApi"
"""The IR kind of an external API."""

_LITERALS: Final = "literals"
"""The attribute of the values of an enumeration property."""


# trace: PRD-APP-006
@dataclass(frozen=True, slots=True)
class ExternalField:
    """One property of an object schema, or one path or query parameter of an operation."""

    name: str
    """The name in JSON, as the OpenAPI file gives it."""
    identity: str
    rules: Rules | None
    """The type of one value, or `None` for a reference to an object schema."""
    target: str | None
    """The identity of the object schema of a reference, or `None`."""
    lower: int
    upper: int | None

    @property
    def many(self) -> bool:
        """Tell if the property is an array."""
        return self.upper is None or self.upper > 1

    @property
    def optional(self) -> bool:
        """Tell if the value can be missing or null: the multiplicity is `[0..1]`."""
        return not self.many and self.lower == 0


# trace: PRD-APP-006
@dataclass(frozen=True, slots=True)
class ExternalEntity:
    """One object schema of an external API."""

    identity: str
    name: str
    """The name of the schema, for example `Pet`."""
    fields: tuple[ExternalField, ...]
    """The properties in the order of the IR."""

    @property
    def targets(self) -> list[str]:
        """The identities of the object schemas that the properties refer to, sorted."""
        return sorted({item.target for item in self.fields if item.target is not None})


# trace: PRD-APP-006
@dataclass(frozen=True, slots=True)
class ExternalOperation:
    """One operation of an external API."""

    identity: str
    name: str
    """The `operationId`, for example `createPet`."""
    method: str
    """The HTTP method in lower case, for example `post`."""
    path: str
    parameters: tuple[ExternalField, ...]
    """The path parameters, then the query parameters, each in the order of the IR."""
    places: Mapping[str, str]
    """The place of each parameter by name: `path` or `query`."""
    body: str | None
    """The identity of the object schema of the request body, or `None`."""
    response: str | None
    """The identity of the object schema of the success response, or `None`."""
    response_many: bool
    """Tell if the success response is an array of the object schema."""

    @property
    def path_parameters(self) -> list[ExternalField]:
        return [item for item in self.parameters if self.places[item.name] == "path"]

    @property
    def query_parameters(self) -> list[ExternalField]:
        return [item for item in self.parameters if self.places[item.name] == "query"]

    @property
    def elements(self) -> list[str]:
        """The identities of the header: the operation and its object schemas, sorted."""
        found = {self.identity, *(item for item in (self.body, self.response) if item)}
        return sorted(found)

    @property
    def route(self) -> str:
        """The method and the path, for example `GET /pets/{petId}`."""
        return f"{self.method.upper()} {self.path}"


# trace: PRD-APP-006
@dataclass(frozen=True, slots=True)
class ExternalApi:
    """One external API that a React application calls, with its schemas and operations."""

    identity: str
    name: str
    entities: Mapping[str, ExternalEntity]
    """The object schemas by identity."""
    operations: tuple[ExternalOperation, ...]
    """The operations, sorted by name."""

    def closure(self, identity: str) -> list[ExternalEntity]:
        """Give an object schema and each schema that it refers to, in the order of definition.

        A schema comes after the schemas that it refers to. Two schemas with
        the same rank are in the order of their names. A cycle of
        references gives a `ToolchainError`, because the React target has
        no recursive schema.
        """
        result: list[ExternalEntity] = []
        done: set[str] = set()

        def visit(current: str, path: tuple[str, ...]) -> None:
            if current in done:
                return
            entity = self.entities[current]
            if current in path:
                raise ToolchainError(
                    f"The schema {entity.name} of the external API {self.name} refers to "
                    "itself. The React target has no recursive schema. Remove the cycle of "
                    "references from the OpenAPI file."
                )
            for target in sorted(entity.targets, key=lambda item: self.entities[item].name):
                visit(target, (*path, current))
            done.add(current)
            result.append(entity)

        visit(identity, ())
        return result


# trace: PRD-APP-006
def external_apis(ir: Ir, application: Element) -> list[ExternalApi]:
    """Give the external APIs that an application calls (`#Calls`), sorted by identity."""
    called = {
        link.target
        for link in ir.links
        if link.type == "calls" and link.source == application.identity
    }
    apis = sorted(
        (item for item in ir.elements if item.kind == KIND and item.identity in called),
        key=lambda item: item.identity,
    )
    children: dict[str, list[Element]] = {}
    for item in ir.elements:
        if item.owner is not None:
            children.setdefault(item.owner, []).append(item)
    return [_api(api, children) for api in apis]


def _api(api: Element, children: Mapping[str, list[Element]]) -> ExternalApi:
    entities: dict[str, ExternalEntity] = {}
    operations: list[ExternalOperation] = []
    for item in children.get(api.identity, []):
        if item.kind == "Entity":
            fields = tuple(
                _field(child)
                for child in children.get(item.identity, [])
                if child.kind in ("Field", "Relation")
            )
            entities[item.identity] = ExternalEntity(item.identity, item.name, fields)
        elif item.kind == "Operation":
            operations.append(_operation(item, children.get(item.identity, [])))
    return ExternalApi(
        identity=api.identity,
        name=api.name,
        entities={key: entities[key] for key in sorted(entities)},
        operations=tuple(sorted(operations, key=lambda item: item.name)),
    )


def _operation(operation: Element, parameters: list[Element]) -> ExternalOperation:
    method = path = ""
    for attribute in operation.attributes:
        value = attribute.value
        if attribute.name == "method":
            method = str(getattr(value, "literal", "")).lower()
        elif attribute.name == "path" and isinstance(value, StringValue):
            path = value.value
    places: dict[str, str] = {}
    found: list[ExternalField] = []
    body: str | None = None
    response: str | None = None
    response_many = False
    for item in parameters:
        if item.kind != "Parameter":
            continue
        place = _text(item, "in")
        if place == "body":
            body = item.types[0] if item.types else None
        elif place == "response":
            response = item.types[0] if item.types else None
            response_many = _field(item).many
        else:
            places[item.name] = place
            found.append(_field(item))
    order = {"path": 0, "query": 1}
    found.sort(key=lambda item: order.get(places[item.name], 2))
    return ExternalOperation(
        identity=operation.identity,
        name=operation.name,
        method=method,
        path=path,
        parameters=tuple(found),
        places=places,
        body=body,
        response=response,
        response_many=response_many,
    )


def _field(element: Element) -> ExternalField:
    if not (element.name.isidentifier() and element.name.isascii()):
        raise ToolchainError(
            f'The name "{element.name}" of the external API is not a TypeScript identifier. '
            "The React target uses the names of the OpenAPI file in the code. Use a name with "
            "letters, digits and underscores."
        )
    lower, upper = 1, 1
    if element.multiplicity is not None:
        lower, upper = element.multiplicity.lower, element.multiplicity.upper
    identity = element.types[0] if element.types else ""
    rules: Rules | None = None
    target: str | None = None
    literals = _literals(element)
    if literals:
        rules = Rules(kind=ENUMERATION, values=literals)
    elif identity in SCALAR_TYPES:
        rules = Rules(kind=SCALAR_TYPES[identity])
    elif element.kind in ("Relation", "Parameter"):
        target = identity
    else:
        raise ToolchainError(
            f"The property {element.name} has the type {identity}. The React target does not "
            "know this type."
        )
    return ExternalField(element.name, element.identity, rules, target, lower, upper)


def _literals(element: Element) -> tuple[str, ...]:
    for item in element.attributes:
        if item.name == _LITERALS and isinstance(item.value, ListValue):
            return tuple(
                value.value for value in item.value.items if isinstance(value, StringValue)
            )
    return ()


def _text(element: Element, name: str) -> str:
    for item in element.attributes:
        if item.name == name and isinstance(item.value, StringValue):
            return item.value.value
    return ""
