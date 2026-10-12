# trace: PRD-VAL-015
"""The STR rules of the application layer: STR-005 to STR-010.

The rules read only the IR (PRD-VAL-001, PRD-CORE-026). STR-010 examines the
exposed entities, the exposed operations and the views.
"""

from collections.abc import Iterator
from typing import Final

from dsml.config import Configuration
from dsml.ir.model import BooleanValue, Element, EnumValue, Ir, ListValue
from dsml.ir.operations import Endpoint, attribute, endpoints, method_of, path_of
from dsml.validate.rule import Hit, Rule, implements

# trace: PRD-DSML-020
TARGETS: Final = ("fastapi", "nextjs", "react")
"""The application targets that the toolchain knows (PRD-DSML-020)."""

# trace: PRD-DSML-023
SCALAR_TYPES: Final = frozenset(
    {
        "ScalarValues::Boolean",
        "ScalarValues::Integer",
        "ScalarValues::Real",
        "ScalarValues::String",
        "DSML::Date",
        "DSML::DateTime",
        "DSML::Decimal",
        "DSML::Uuid",
    }
)
"""The identities of the scalar field types (PRD-DSML-023)."""

KEY: Final = "Key"
"""The metadata of the primary key field of an entity (PRD-DSML-024)."""

# trace: PRD-DSML-020
STR_005 = Rule(
    id="STR-005",
    severity="error",
    message="An application has no target, or a target that the toolchain does not know.",
    fix_hint="Set the attribute target of the application to Target::fastapi, "
    "Target::react or Target::nextjs.",
)

# trace: PRD-DSML-024
STR_006 = Rule(
    id="STR-006",
    severity="error",
    message="An entity has no #Key field, or more than one.",
    fix_hint="Put the #Key metadata on one field of the entity.",
)

# trace: PRD-DSML-023
STR_007 = Rule(
    id="STR-007",
    severity="error",
    message="A field type is not a supported type.",
    fix_hint="Use String, Integer, Boolean, Real, Decimal, Date, DateTime, Uuid "
    "or an enumeration definition of the model as the field type.",
)

# trace: PRD-DSML-029
STR_008 = Rule(
    id="STR-008",
    severity="error",
    message="A custom operation has no HTTP method or no path.",
    fix_hint="Set the attributes method and path of the operation, for example "
    ':>> method = HttpMethod::post; :>> path = "/orders/{orderId}/cancel";.',
)

# trace: PRD-DSML-029, PRD-APP-110
STR_009 = Rule(
    id="STR-009",
    severity="error",
    message="Two operations of one application have the same method and path.",
    fix_hint="Change the path or the method of one operation, or expose the "
    "operation in a different application.",
)

# trace: PRD-DSML-033
STR_010 = Rule(
    id="STR-010",
    severity="error",
    message="An exposed entity, operation or view has no allowedRoles and is not public.",
    fix_hint="Give the roles that can use the element in the attribute allowedRoles, "
    "or set public = true.",
)


def _of_kind(ir: Ir, kind: str) -> Iterator[Element]:
    """Give the elements of one kind, sorted by identity."""
    return iter(sorted((item for item in ir.elements if item.kind == kind), key=Element.sort_key))


# trace: PRD-DSML-020
@implements(STR_005)
def str_005(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    for application in _of_kind(ir, "Application"):
        target = attribute(application, "target")
        if target is None:
            yield Hit(
                f"The application {application.name} has no target.",
                application.location,
                application.identity,
            )
        elif not isinstance(target, EnumValue) or target.literal not in TARGETS:
            shown = target.literal if isinstance(target, EnumValue) else target.TYPE
            yield Hit(
                f'The application {application.name} has the target "{shown}". '
                f"The toolchain knows only these targets: {', '.join(TARGETS)}.",
                application.location,
                application.identity,
            )


# trace: PRD-DSML-024
@implements(STR_006)
def str_006(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    keys: dict[str, list[Element]] = {}
    for field in _of_kind(ir, "Field"):
        if field.owner is not None and any(item.name == KEY for item in field.annotations):
            keys.setdefault(field.owner, []).append(field)
    for entity in _of_kind(ir, "Entity"):
        found = keys.get(entity.identity, [])
        if not found:
            yield Hit(
                f"The entity {entity.name} has no #Key field.", entity.location, entity.identity
            )
        elif len(found) > 1:
            names = ", ".join(sorted(field.name for field in found))
            yield Hit(
                f"The entity {entity.name} has {len(found)} #Key fields: {names}. "
                "It must have one.",
                entity.location,
                entity.identity,
            )


# trace: PRD-DSML-023
@implements(STR_007)
def str_007(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    supported = SCALAR_TYPES | {
        item.identity for item in ir.elements if item.kind in ("Enumeration", "Roles")
    }
    for field in _of_kind(ir, "Field"):
        if not field.types:
            yield Hit(f"The field {field.name} has no type.", field.location, field.identity)
            continue
        wrong = [item for item in field.types if item not in supported]
        if wrong:
            yield Hit(
                f"The field {field.name} has the type {', '.join(wrong)}. "
                "This is not a supported field type.",
                field.location,
                field.identity,
            )


# trace: PRD-DSML-029
@implements(STR_008)
def str_008(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    for operation in _of_kind(ir, "Operation"):
        missing = [
            name
            for name, value in (("method", method_of(operation)), ("path", path_of(operation)))
            if value is None
        ]
        if missing:
            yield Hit(
                f"The operation {operation.name} has no {' and no '.join(missing)}.",
                operation.location,
                operation.identity,
            )


def _describe(endpoint: Endpoint) -> str:
    """Give the name of an operation for a message."""
    if endpoint.crud:
        return f"{endpoint.operation} of {endpoint.exposed.name}"
    return endpoint.exposed.name


# trace: PRD-DSML-029, PRD-APP-110
@implements(STR_009)
def str_009(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    """Report each operation that has the route of an operation before it.

    The route is the method and the path with no names of path parameters.
    The first operation of a route, in the order of the model, gets no hit.
    """
    for application in _of_kind(ir, "Application"):
        first: dict[tuple[str, str], Endpoint] = {}
        for endpoint in endpoints(ir, application.identity):
            route = endpoint.route
            if route is None or endpoint.method is None:
                continue
            earlier = first.setdefault(route, endpoint)
            if earlier is endpoint:
                continue
            yield Hit(
                f"In the application {application.name}, the operation {_describe(endpoint)} "
                f"has the same method and path as {_describe(earlier)}: "
                f"{endpoint.method.upper()} {endpoint.path}.",
                endpoint.location,
                endpoint.exposed.identity,
            )


# trace: PRD-DSML-031, PRD-DSML-033
@implements(STR_010)
def str_010(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    guarded = sorted(
        (item for item in ir.elements if item.kind in ("Exposed", "View")), key=Element.sort_key
    )
    for element in guarded:
        roles = attribute(element, "allowedRoles")
        public = attribute(element, "public")
        if isinstance(public, BooleanValue) and public.value:
            continue
        if isinstance(roles, ListValue) and roles.items:
            continue
        noun = "view" if element.kind == "View" else "exposed element"
        yield Hit(
            f"The {noun} {element.name} has no allowedRoles and is not public.",
            element.location,
            element.identity,
        )


RULES = (str_005, str_006, str_007, str_008, str_009, str_010)
"""The rules of this module."""
