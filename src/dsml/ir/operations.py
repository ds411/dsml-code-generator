# trace: PRD-DSML-027, PRD-DSML-028, PRD-DSML-029, PRD-APP-110, PRD-CORE-026
"""Give the operations of an application with their HTTP methods and paths.

An application exposes entities and custom operations with `#Exposed`
elements. An exposed entity gives one CRUD operation for each item of its
attribute `crud`. The IR adapter writes the default method and path of each
CRUD operation from the DSML library into the IR attribute `crudDefaults`
(PRD-DSML-029). A custom operation gives its method and path itself.

The validator (rule STR-009) and the FastAPI generator use this module. Thus
the two parts use the same methods and paths (PRD-APP-110). The functions
read only the IR (PRD-CORE-026). This module does not import OpenSysML.
"""

import re
from dataclasses import dataclass
from typing import Final

from dsml.ir.model import Element, EnumValue, Ir, ListValue, Location, StringValue, Value

CRUD_DEFAULTS: Final = "crudDefaults"
"""The IR attribute of an exposed entity with the default method and path of each CRUD operation."""

ENTITIES: Final = "{entities}"
"""The part of a default path that the collection name of the exposed entity replaces."""

_PARAMETER: Final = re.compile(r"\{[^{}]*\}")


# trace: PRD-DSML-029, PRD-APP-110
@dataclass(frozen=True, slots=True)
class Endpoint:
    """One operation of an application.

    `exposed` is the `#Exposed` element. `operation` is the CRUD kind, for
    example "read", or the identity of the custom operation. `crud` is true
    for a CRUD operation. `method` is the HTTP method in lower case, for
    example "get". `method` and `path` are None if the model gives no value.
    """

    exposed: Element
    operation: str
    crud: bool
    method: str | None
    path: str | None

    @property
    def location(self) -> Location:
        """The location of the exposed element."""
        return self.exposed.location

    @property
    def route(self) -> tuple[str, str] | None:
        """Give the method and the path with no names of path parameters.

        Two endpoints with the same route are the same endpoint for an HTTP
        server. For example, `/orders/{id}` and `/orders/{orderId}` have the
        same route. The result is None if the method or the path is missing.
        """
        if self.method is None or self.path is None:
            return None
        path = _PARAMETER.sub("{}", self.path)
        if len(path) > 1:
            path = path.rstrip("/")
        return (self.method, path)


def attribute(element: Element, name: str) -> Value | None:
    """Give the value of an attribute of an element, or None."""
    return next((item.value for item in element.attributes if item.name == name), None)


# trace: PRD-DSML-029
def method_of(element: Element) -> str | None:
    """Give the HTTP method of a custom operation in lower case, or None."""
    value = attribute(element, "method")
    return value.literal if isinstance(value, EnumValue) else None


# trace: PRD-DSML-029
def path_of(element: Element) -> str | None:
    """Give the path of a custom operation, or None if it has no path or an empty path."""
    value = attribute(element, "path")
    return value.value if isinstance(value, StringValue) and value.value else None


# trace: PRD-DSML-027, PRD-DSML-028, PRD-DSML-029, PRD-APP-110
def endpoints(ir: Ir, application: str) -> tuple[Endpoint, ...]:
    """Give the operations of one application, in the order of the exposed elements.

    `application` is the identity of an application. In a default path, the
    name of the exposed entity usage replaces `{entities}`, for example
    `/orders/{id}` for `#Exposed part orders : Order [*]`.
    """
    operations = {
        element.identity: element for element in ir.elements if element.kind == "Operation"
    }
    exposed = sorted(
        (
            element
            for element in ir.elements
            if element.kind == "Exposed" and element.owner == application
        ),
        key=lambda element: (element.location.sort_key(), element.identity),
    )
    result: list[Endpoint] = []
    for element in exposed:
        defaults = attribute(element, CRUD_DEFAULTS)
        if isinstance(defaults, ListValue):
            result.extend(_crud_endpoints(element, defaults))
        for identity in element.types:
            operation = operations.get(identity)
            if operation is not None:
                result.append(
                    Endpoint(element, identity, False, method_of(operation), path_of(operation))
                )
    return tuple(result)


def _crud_endpoints(element: Element, defaults: ListValue) -> list[Endpoint]:
    """Give the CRUD operations of an exposed entity from its `crudDefaults`."""
    result: list[Endpoint] = []
    for item in defaults.items:
        if not isinstance(item, ListValue) or len(item.items) != 3:
            continue
        kind, method, path = item.items
        if not isinstance(kind, EnumValue):
            continue
        result.append(
            Endpoint(
                element,
                kind.literal,
                True,
                method.literal if isinstance(method, EnumValue) else None,
                path.value.replace(ENTITIES, element.name)
                if isinstance(path, StringValue)
                else None,
            )
        )
    return result
