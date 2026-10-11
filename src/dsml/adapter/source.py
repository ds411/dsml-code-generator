# trace: PRD-CORE-024, PRD-CORE-025, PRD-DSML-053
"""Read the elements of a parsed model from the SysML v2 API JSON form.

`ParsedModel.api_elements()` gives the JSON objects. This module gives a
graph of `SourceElement` objects with the data that the layer converters
need: names, the keyword of the element kind, the source location, the
members, the metadata usages and the values of the features.

The JSON form refers to an element with an OpenSysML internal ID (the key
"@id"). Only this module uses these IDs. The converters use qualified names
and identities, so the IR contains no OpenSysML ID (PRD-CORE-025).
"""

from collections.abc import Collection, Iterator, Mapping, Sequence
from typing import Any, cast

from dsml.adapter.engine import EngineError
from dsml.ir.model import (
    BooleanValue,
    EnumValue,
    IntegerValue,
    ListValue,
    Location,
    RealValue,
    ReferenceValue,
    StringValue,
    Value,
)

type JsonObject = Mapping[str, Any]

LIBRARY_PACKAGE = "DSML"
"""The name of the root package of the DSML library."""

# The JSON keys of the extension data of OpenSysML.
_LINE = "sysx:sourceLine"
_COLUMN = "sysx:sourceColumn"
_DOCUMENT = "sysx:sourceDocument"

_LITERALS = {"LiteralString", "LiteralInteger", "LiteralRational", "LiteralBoolean"}


def _ids(value: Any) -> tuple[str, ...]:
    """Give the IDs of a reference value: one object, a list of objects or None."""
    if value is None:
        return ()
    items = cast(list[Any], value) if isinstance(value, list) else [value]
    objects = (cast(dict[str, Any], item) for item in items if isinstance(item, dict))
    return tuple(str(item["@id"]) for item in objects)


class SourceGraph:
    """The elements of a model, with an index by OpenSysML ID.

    `files` gives the names of the model files. An element of another file,
    for example of the DSML library, is not a model element.
    """

    def __init__(self, items: Sequence[JsonObject], files: Collection[str]) -> None:
        self.files = frozenset(files)
        self._items: dict[str, JsonObject] = {}
        for item in items:
            identifier = item.get("@id")
            if not isinstance(identifier, str):
                raise EngineError("An item of the API JSON form has no ID.")
            self._items[identifier] = item
        self._elements: dict[str, SourceElement] = {}
        self._documents: dict[str, str | None] = {}

    def element(self, identifier: str) -> SourceElement | None:
        """Give the element with an OpenSysML ID, or None if the form does not contain it."""
        found = self._elements.get(identifier)
        if found is None:
            data = self._items.get(identifier)
            if data is None:
                return None
            found = SourceElement(self, data)
            self._elements[identifier] = found
        return found

    def elements(self, identifiers: Sequence[str]) -> tuple[SourceElement, ...]:
        """Give the elements with the IDs that the form contains, in the same order."""
        found = (self.element(identifier) for identifier in identifiers)
        return tuple(element for element in found if element is not None)

    def model_elements(self) -> Iterator[SourceElement]:
        """Give each element of the model files that has a qualified name."""
        for identifier in self._items:
            element = self.element(identifier)
            if element is not None and element.qualified_name and element.in_model:
                yield element

    def document(self, element: SourceElement) -> str | None:
        """Give the file of an element: the document of its root package."""
        identifier = element.json_id
        if identifier not in self._documents:
            document = element.data.get(_DOCUMENT)
            if isinstance(document, str):
                self._documents[identifier] = document
            else:
                owner = element.owner
                self._documents[identifier] = None if owner is None else self.document(owner)
        return self._documents[identifier]


class SourceElement:
    """One element of the API JSON form."""

    def __init__(self, graph: SourceGraph, data: JsonObject) -> None:
        self.graph = graph
        self.data = data

    def __repr__(self) -> str:
        return f"SourceElement({self.metaclass} {self.qualified_name})"

    @property
    def json_id(self) -> str:
        """The OpenSysML ID. Do not put it in the IR (PRD-CORE-025)."""
        return str(self.data["@id"])

    @property
    def metaclass(self) -> str:
        """The name of the SysML v2 metaclass, for example "ConcernUsage"."""
        return str(self.data.get("@type", ""))

    @property
    def qualified_name(self) -> str:
        """The qualified name, or an empty text for an element with no name."""
        return str(self.data.get("qualifiedName", ""))

    @property
    def name(self) -> str:
        """The declared name, or an empty text."""
        return str(self.data.get("declaredName", ""))

    @property
    def short_name(self) -> str | None:
        """The declared short name, or None."""
        value = self.data.get("declaredShortName")
        return str(value) if value else None

    # trace: PRD-DSML-053
    @property
    def identity(self) -> str:
        """The short name, or the qualified name if the element has no short name."""
        return self.short_name or self.qualified_name

    @property
    def owner(self) -> SourceElement | None:
        """The element that owns this element, or None."""
        owners = _ids(self.data.get("owner"))
        return self.graph.element(owners[0]) if owners else None

    @property
    def file(self) -> str | None:
        """The model file of the element, relative to the repository root."""
        return self.graph.document(self)

    @property
    def in_model(self) -> bool:
        """True if the element is in a model file, not in a library file."""
        return self.file in self.graph.files

    # trace: PRD-CORE-007, PRD-CORE-024
    @property
    def location(self) -> Location | None:
        """The file, the line and the column of the element, or None."""
        file = self.file
        line = self.data.get(_LINE)
        column = self.data.get(_COLUMN)
        if file is None or not isinstance(line, int) or not isinstance(column, int):
            return None
        return Location(file=file, line=max(line, 1), column=max(column, 1))

    def references(self, key: str) -> tuple[SourceElement, ...]:
        """Give the elements that the JSON key refers to."""
        return self.graph.elements(_ids(self.data.get(key)))

    def relationships(self) -> tuple[SourceElement, ...]:
        """Give the relationships that this element owns, in the order of the model."""
        return self.references("ownedRelationship")

    def members(self) -> Iterator[tuple[str, SourceElement]]:
        """Give each owned member with the metaclass of its membership.

        The metaclass of the membership tells the role of the member, for
        example "StakeholderMembership" or "FramedConcernMembership".
        """
        for relationship in self.relationships():
            for member in relationship.references("ownedMemberElement"):
                yield relationship.metaclass, member

    def metadata(self) -> tuple[SourceElement, ...]:
        """Give the metadata usages on this element, in the order of the model.

        A metadata usage is an owned member of the element, for example
        `#Need` or `@Waiver { ... }` in its body, or the element of an owned
        annotation, for example `#refinement` on a dependency.
        """
        found: list[SourceElement] = []
        for relationship in self.relationships():
            for related in relationship.references("ownedRelatedElement"):
                if related.metaclass == "MetadataUsage" and related is not self:
                    found.append(related)
        return tuple(found)

    def types(self) -> tuple[SourceElement, ...]:
        """Give the types of the element: the definitions in its key "type"."""
        return self.references("type")

    def generals(self) -> tuple[SourceElement, ...]:
        """Give the general types that the element specializes, subsets or redefines."""
        found: list[SourceElement] = []
        for relationship in self.relationships():
            if relationship.data.get("general") is not None and relationship.metaclass in {
                "Subclassification",
                "Subsetting",
                "Redefinition",
                "FeatureTyping",
                "Specialization",
            }:
                found.extend(
                    general for general in relationship.references("general") if general is not self
                )
        return tuple(found)

    def specializes(self, qualified_name: str) -> bool:
        """True if the element is the definition `qualified_name` or specializes it."""
        seen: set[str] = set()
        pending: list[SourceElement] = [self]
        while pending:
            current = pending.pop()
            if current.json_id in seen:
                continue
            seen.add(current.json_id)
            if current.qualified_name == qualified_name:
                return True
            pending.extend(current.generals())
        return False

    @property
    def documentation(self) -> str | None:
        """The text of the first `doc` comment, with no white space at the ends."""
        for kind, member in self.members():
            if kind == "OwningMembership" and member.metaclass == "Documentation":
                body = str(member.data.get("body", "")).strip()
                return body or None
        return None

    def referenced_feature(self) -> SourceElement | None:
        """Give the feature that a reference subsetting gives, for example `frame n;`."""
        for relationship in self.relationships():
            if relationship.metaclass == "ReferenceSubsetting":
                found = relationship.references("referencedFeature")
                if found:
                    return found[0]
        found = self.references("references")
        return found[0] if found else None

    def redefined_name(self) -> str:
        """Give the name of the feature: its declared name, or the name that it redefines."""
        if self.name:
            return self.name
        for redefined in self.references("redefines"):
            if redefined.name:
                return redefined.name
            if redefined.qualified_name:
                return redefined.qualified_name.rsplit("::", 1)[-1]
        return ""

    def value(self) -> Value | None:
        """Give the value of the feature (`= value` or `default = value`), or None.

        The function gives None for a value that is not a literal, a
        reference to an element or a list of these values.
        """
        found = self.references("value")
        if not found:
            for kind, member in self.members():
                if kind == "FeatureValue":
                    found = (member,)
                    break
        return value_of(found[0]) if found else None


# trace: PRD-CORE-024
def value_of(expression: SourceElement) -> Value | None:
    """Convert a value expression into an IR value, or give None.

    An enumeration literal gives an `EnumValue`. A reference to another
    element gives a `ReferenceValue` with the identity of the element. The
    sequence operator "," gives a `ListValue` in the order of the model.
    """
    metaclass = expression.metaclass
    if metaclass in _LITERALS:
        raw: Any = expression.data.get("value")
        match metaclass:
            case "LiteralString":
                return StringValue(value=str(raw))
            case "LiteralInteger" if isinstance(raw, int) and not isinstance(raw, bool):
                return IntegerValue(value=raw)
            case "LiteralRational" if isinstance(raw, int | float) and not isinstance(raw, bool):
                return RealValue(value=float(raw))
            case "LiteralBoolean" if isinstance(raw, bool):
                return BooleanValue(value=raw)
            case _:
                return None
    if metaclass == "FeatureReferenceExpression":
        referents = expression.references("referent")
        if not referents:
            return None
        referent = referents[0]
        owner = referent.owner
        if (
            referent.metaclass == "EnumerationUsage"
            and owner is not None
            and owner.metaclass == "EnumerationDefinition"
        ):
            return EnumValue(enumeration=owner.qualified_name, literal=referent.redefined_name())
        return ReferenceValue(target=referent.identity) if referent.qualified_name else None
    if metaclass == "OperatorExpression" and expression.data.get("operator") == ",":
        items = [value_of(argument) for argument in expression.references("argument")]
        if any(item is None for item in items):
            return None
        return ListValue(items=tuple(item for item in items if item is not None))
    return None


def keyword_of(element: SourceElement, keywords: Collection[str]) -> str | None:
    """Give the DSML keyword of the element kind, or None.

    The keyword is the name of a metadata definition of the DSML library, for
    example "Need". A metadata definition of a project library that
    specializes a DSML keyword gives that keyword (PRD-DSML-019).
    """
    for usage in element.metadata():
        for definition in usage.types():
            for keyword in sorted(keywords):
                if definition.specializes(f"{LIBRARY_PACKAGE}::{keyword}"):
                    return keyword
    return None
