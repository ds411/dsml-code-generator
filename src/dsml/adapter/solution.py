# trace: PRD-CORE-024, PRD-CORE-025, PRD-TRACE-001, PRD-TRACE-003
"""Convert the application, infrastructure and verification layers into the IR.

The adapter reads the structure, the metadata usages, the links and the
source locations from the API JSON form (`dsml.adapter.source`). It reads the
values of the DSML attributes through OpenSysML expressions. Thus a default
value of the DSML library is also in the IR, for example `public = false`,
and an attribute with a list type always gives a list.

The links are `satisfy`, `allocate`, `realizes`, `uses`, `calls` and `verify`
(PRD-TRACE-001, PRD-DSML-030, PRD-DSML-040). `docs/notes/ir-solution-layers.md`
gives the source and the target of each link.

The needs and requirements layers are in `dsml.adapter.needs`. The formal
constraints are not in this module (story #32).
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from dsml.adapter.engine import EngineError, EnumLiteral, ParsedModel, PlainValue
from dsml.adapter.needs import annotations
from dsml.adapter.needs import attributes as declared_attributes
from dsml.adapter.source import LIBRARY_PACKAGE, SourceElement, SourceGraph, keyword_of
from dsml.ir.model import (
    Attribute,
    BooleanValue,
    Direction,
    Element,
    ElementKind,
    EnumValue,
    IntegerValue,
    Link,
    LinkType,
    ListValue,
    Location,
    Multiplicity,
    RealValue,
    StringValue,
    Value,
)

# trace: PRD-DSML-020, PRD-DSML-022, PRD-DSML-027, PRD-DSML-028, PRD-DSML-033,
# PRD-DSML-035, PRD-DSML-037, PRD-DSML-041, PRD-DSML-042, PRD-DSML-043, PRD-DSML-045
KEYWORDS: dict[str, ElementKind] = {
    "Application": "Application",
    "Entity": "Entity",
    "Exposed": "Exposed",
    "Operation": "Operation",
    "Roles": "Roles",
    "Network": "Network",
    "ContainerService": "ContainerService",
    "RelationalDatabase": "RelationalDatabase",
    "UserDirectory": "UserDirectory",
    "SecretStore": "SecretStore",
    "AwsVpc": "AwsVpc",
    "AwsEcsService": "AwsEcsService",
    "AwsRdsPostgres": "AwsRdsPostgres",
    "AwsCognito": "AwsCognito",
    "AwsSecrets": "AwsSecrets",
    "Environment": "Environment",
    "Override": "Override",
    "ToolingAccount": "ToolingAccount",
    "Verification": "Verification",
}
"""The DSML keywords of this module and the IR kinds that they give."""

# The definitions of the library that hold the DSML attributes of each kind.
_BASE_TYPES: dict[ElementKind, str] = {
    "Application": "DSML::BaseTypes::Application",
    "Exposed": "DSML::BaseTypes::exposures",
    "Operation": "DSML::BaseTypes::Operation",
    "AwsVpc": "DSML::BaseTypes::AwsVpc",
    "AwsEcsService": "DSML::BaseTypes::AwsEcsService",
    "AwsRdsPostgres": "DSML::BaseTypes::AwsRdsPostgres",
    "AwsCognito": "DSML::BaseTypes::AwsCognito",
    "AwsSecrets": "DSML::BaseTypes::AwsSecrets",
    "Environment": "DSML::BaseTypes::Environment",
    "ToolingAccount": "DSML::BaseTypes::ToolingAccount",
    "Verification": "DSML::BaseTypes::Verification",
}

# trace: PRD-DSML-035, PRD-DSML-036
# The logical kinds have no DSML attributes. The IR holds each attribute that
# the model declares on a logical element, thus rule STR-016 can find an AWS
# attribute on it.
_LOGICAL_KINDS: frozenset[ElementKind] = frozenset(
    {"Network", "ContainerService", "RelationalDatabase", "UserDirectory", "SecretStore"}
)

# The metadata on a dependency and the link type that it gives.
_DEPENDENCY_LINKS: dict[str, LinkType] = {
    "Realizes": "realizes",
    "Uses": "uses",
    "Calls": "calls",
}

CRUD_DEFAULTS = "crudDefaults"
"""The IR attribute that gives the default method and path of each CRUD operation."""

LITERALS = "literals"
"""The IR attribute that gives the literals of an enumeration."""


@dataclass(frozen=True, slots=True)
class _AttributeSpec:
    """A DSML attribute of a kind. `is_list` is true for the multiplicity `[*]`."""

    name: str
    is_list: bool


# trace: PRD-CORE-024, PRD-DSML-053
def convert_elements(graph: SourceGraph, model: ParsedModel) -> Iterator[Element]:
    """Give the elements of the application, infrastructure and verification layers."""
    yield from _Converter(graph, model).elements()


# trace: PRD-TRACE-001, PRD-TRACE-002, PRD-TRACE-003
def convert_links(graph: SourceGraph) -> Iterator[Link]:
    """Give the `satisfy`, `allocate`, `realizes`, `uses`, `calls` and `verify` links."""
    for source in graph.model_elements():
        yield from _links(source)


class _Converter:
    def __init__(self, graph: SourceGraph, model: ParsedModel) -> None:
        self._graph = graph
        self._model = model
        self._kinds: dict[str, ElementKind] = {}
        for source in graph.model_elements():
            keyword = keyword_of(source, KEYWORDS)
            if keyword is not None:
                self._kinds[source.json_id] = KEYWORDS[keyword]
        self._specs: dict[ElementKind, tuple[_AttributeSpec, ...]] = {}
        self._crud: dict[str, tuple[Value, Value]] | None = None

    def elements(self) -> Iterator[Element]:
        for source in self._graph.model_elements():
            kind = self._kind(source)
            if kind is not None:
                yield self._element(source, kind)

    # trace: PRD-CORE-024, PRD-DSML-053
    def _element(self, source: SourceElement, kind: ElementKind) -> Element:
        location = source.location
        if location is None:
            raise EngineError(f"OpenSysML gave no location for {source.qualified_name}.")
        match kind:
            case "Override":
                attributes = self._override_attributes(source)
            case "Roles" | "Enumeration":
                attributes = (_literals(source),)
            case _ if kind in _LOGICAL_KINDS:
                attributes = tuple(declared_attributes(source))
            case _:
                attributes = self._attributes(source, kind)
        if kind == "Exposed":
            attributes = (*attributes, *self._crud_defaults(source, attributes))
        owner = source.owner
        keyword = kind if kind in KEYWORDS else None
        return Element(
            identity=source.identity,
            kind=kind,
            name=source.name,
            qualified_name=source.qualified_name,
            location=location,
            short_name=source.short_name,
            owner=owner.identity if owner is not None and owner.qualified_name else None,
            doc=source.documentation,
            multiplicity=_multiplicity(source),
            direction=_direction(source) if kind == "Parameter" else None,
            types=_types(source),
            attributes=attributes,
            annotations=tuple(annotations(source, keyword)),
        )

    def _kind(self, source: SourceElement) -> ElementKind | None:
        """Give the IR kind of an element of the three layers, or None."""
        kind = self._kinds.get(source.json_id)
        if kind is not None:
            return kind
        metaclass = source.metaclass
        if metaclass == "EnumerationDefinition":
            return "Enumeration"
        if not source.name:
            return None
        owner = source.owner
        owner_kind = None if owner is None else self._kinds.get(owner.json_id)
        # trace: PRD-DSML-022, PRD-DSML-026
        if owner_kind == "Entity":
            if metaclass == "AttributeUsage":
                return "Field"
            if metaclass in ("ReferenceUsage", "PartUsage") and any(
                self._kinds.get(item.json_id) == "Entity" for item in source.types()
            ):
                return "Relation"
        # trace: PRD-DSML-028
        if owner_kind == "Operation" and _direction(source) is not None:
            return "Parameter"
        return None

    # Attributes ---------------------------------------------------------------

    # trace: PRD-CORE-024
    def _attributes(self, source: SourceElement, kind: ElementKind) -> tuple[Attribute, ...]:
        declared = _declared(source)
        result: list[Attribute] = []
        for spec in self._kind_specs(kind):
            value = self._value(source.qualified_name, spec)
            if value is not None:
                result.append(Attribute(spec.name, value, declared.get(spec.name)))
        return tuple(result)

    # trace: PRD-DSML-041, PRD-DSML-042
    def _override_attributes(self, source: SourceElement) -> tuple[Attribute, ...]:
        """Give the attributes that the override changes, with their values."""
        specs = {
            spec.name: spec
            for realization in source.references("subsets")
            if (kind := self._kinds.get(realization.json_id)) is not None
            for spec in self._kind_specs(kind)
        }
        result: list[Attribute] = []
        for name, location in sorted(_declared(source).items()):
            spec = specs.get(name)
            value = None if spec is None else self._value(source.qualified_name, spec)
            if value is not None:
                result.append(Attribute(name, value, location))
        return tuple(result)

    def _kind_specs(self, kind: ElementKind) -> tuple[_AttributeSpec, ...]:
        """Give the attribute usages of the base type of a kind in the library."""
        if kind in self._specs:
            return self._specs[kind]
        specs: list[_AttributeSpec] = []
        base_name = _BASE_TYPES.get(kind)
        if base_name is not None:
            base = self._graph.find(base_name)
            if base is None:
                raise EngineError(f"The DSML library does not contain {base_name}.")
            for membership, member in base.members():
                if membership != "FeatureMembership" or member.metaclass != "AttributeUsage":
                    continue
                bounds = _multiplicity(member)
                is_list = bounds is not None and (bounds.upper is None or bounds.upper > 1)
                specs.append(_AttributeSpec(member.name, is_list))
        self._specs[kind] = tuple(specs)
        return self._specs[kind]

    def _value(self, namespace: str, spec: _AttributeSpec) -> Value | None:
        plain = self._model.evaluate_value(_quoted(spec.name), namespace)
        if plain is None:
            return None
        if spec.is_list:
            items = plain if isinstance(plain, tuple) else (plain,)
            return ListValue(tuple(_ir_value(item) for item in items))
        if isinstance(plain, tuple):
            if len(plain) != 1:
                raise EngineError(f'The attribute "{spec.name}" of {namespace} has more values.')
            plain = plain[0]
        return _ir_value(plain)

    # trace: PRD-DSML-027, PRD-DSML-029
    def _crud_defaults(
        self, source: SourceElement, attributes: Sequence[Attribute]
    ) -> tuple[Attribute, ...]:
        """Give the default HTTP method and path of each CRUD operation of an exposed entity.

        The value has one item for each item of `crud`, in the same order. Each
        item is a list: the CRUD kind, the HTTP method and the path.
        """
        crud = next((item.value for item in attributes if item.name == "crud"), None)
        if not isinstance(crud, ListValue):
            return ()
        defaults = self._library_crud_defaults()
        items: list[Value] = []
        for kind in crud.items:
            if not isinstance(kind, EnumValue) or kind.literal not in defaults:
                raise EngineError(
                    f"The DSML library has no CRUD default for {kind} in {source.qualified_name}."
                )
            method, path = defaults[kind.literal]
            items.append(ListValue((kind, method, path)))
        return (Attribute(CRUD_DEFAULTS, ListValue(tuple(items))),)

    def _library_crud_defaults(self) -> dict[str, tuple[Value, Value]]:
        if self._crud is not None:
            return self._crud

        def column(feature: str) -> tuple[PlainValue, ...]:
            expression = f"{_quoted(LIBRARY_PACKAGE)}::'crudDefaults'.{_quoted(feature)}"
            value = self._model.evaluate_value(expression, LIBRARY_PACKAGE)
            return value if isinstance(value, tuple) else ()

        kinds, methods, paths = column("crud"), column("method"), column("path")
        if not kinds or len(kinds) != len(methods) or len(kinds) != len(paths):
            raise EngineError("The DSML library does not give the CRUD defaults.")
        self._crud = {
            kind.literal: (_ir_value(method), _ir_value(path))
            for kind, method, path in zip(kinds, methods, paths, strict=True)
            if isinstance(kind, EnumLiteral)
        }
        return self._crud


# trace: PRD-DSML-022, PRD-DSML-033
def _literals(source: SourceElement) -> Attribute:
    """Give the literals of an enumeration definition, in the order of the model."""
    items = tuple(
        EnumValue(source.qualified_name, member.name)
        for _, member in source.members()
        if member.metaclass == "EnumerationUsage" and member.name
    )
    return Attribute(LITERALS, ListValue(items))


def _declared(source: SourceElement) -> dict[str, Location | None]:
    """Give the names of the features that the body of the element redefines, with locations."""
    result: dict[str, Location | None] = {}
    for membership, member in source.members():
        if membership != "FeatureMembership" or not member.references("redefines"):
            continue
        name = member.redefined_name()
        if name and name not in result:
            result[name] = member.location
    return result


def _types(source: SourceElement) -> tuple[str, ...]:
    """Give the identities of the types of the element and of the features that it subsets."""
    found = (*source.types(), *source.references("subsets"))
    return tuple(sorted({item.identity for item in found if item.qualified_name}))


def _multiplicity(source: SourceElement) -> Multiplicity | None:
    """Give the declared multiplicity. `[n]` gives (n, n), and `[*]` gives (0, None)."""
    ranges = source.references("multiplicity")
    if not ranges:
        return None
    uppers = ranges[0].references("upperBound")
    lowers = ranges[0].references("lowerBound")
    upper = _bound(uppers[0]) if uppers else None
    if uppers and upper is None and uppers[0].metaclass != "LiteralInfinity":
        return None
    if lowers:
        lower = _bound(lowers[0])
        if lower is None:
            return None
    else:
        lower = 0 if upper is None else upper
    return Multiplicity(lower, upper)


def _bound(source: SourceElement) -> int | None:
    value = source.data.get("value")
    if source.metaclass == "LiteralInteger" and isinstance(value, int):
        return value
    return None


def _direction(source: SourceElement) -> Direction | None:
    match source.data.get("direction"):
        case "in":
            return "in"
        case "out":
            return "out"
        case "inout":
            return "inout"
        case _:
            return None


# Links ------------------------------------------------------------------------


# trace: PRD-TRACE-001, PRD-TRACE-002, PRD-TRACE-003, PRD-DSML-030, PRD-DSML-037,
# PRD-DSML-039, PRD-DSML-040, PRD-DSML-047
def _links(source: SourceElement) -> Iterator[Link]:
    metaclass = source.metaclass
    if metaclass == "SatisfyRequirementUsage":
        for satisfier in source.references("subject"):
            for requirement in source.references("subsets"):
                yield from _link("satisfy", satisfier, requirement, source)
    elif metaclass == "RequirementUsage" and source.data.get("sysx:declaredKeyword") == "verify":
        verification = _enclosing_verification(source)
        if verification is not None:
            for requirement in source.references("subsets"):
                yield from _link("verify", verification, requirement, source)
    elif metaclass == "AllocationUsage":
        for allocated in source.references("sourceFeature"):
            for target in source.references("targetFeature"):
                yield from _link("allocate", allocated, target, source)
    elif metaclass == "Dependency":
        keyword = keyword_of(source, _DEPENDENCY_LINKS)
        if keyword is not None:
            for client in source.references("client"):
                for supplier in source.references("supplier"):
                    yield from _link(_DEPENDENCY_LINKS[keyword], client, supplier, source)


def _link(
    link_type: LinkType, start: SourceElement, end: SourceElement, statement: SourceElement
) -> Iterator[Link]:
    location = statement.location
    if location is not None and start.qualified_name and end.qualified_name:
        yield Link(type=link_type, source=start.identity, target=end.identity, location=location)


def _enclosing_verification(source: SourceElement) -> SourceElement | None:
    current = source.owner
    while current is not None:
        if keyword_of(current, {"Verification"}) is not None:
            return current
        current = current.owner
    return None


def _quoted(name: str) -> str:
    """Give a name as an unrestricted name, so that a SysML keyword is also a name."""
    escaped = name.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _ir_value(value: PlainValue) -> Value:
    match value:
        case bool():
            return BooleanValue(value)
        case int():
            return IntegerValue(value)
        case float():
            return RealValue(value)
        case str():
            return StringValue(value)
        case EnumLiteral():
            return EnumValue(value.enumeration, value.literal)
        case tuple():
            return ListValue(tuple(_ir_value(item) for item in value))
