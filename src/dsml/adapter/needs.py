# trace: PRD-CORE-024, PRD-TRACE-001, PRD-TRACE-003
"""Convert the packages, the needs layer and the requirements layer into the IR.

- A part definition with `#Stakeholder` gives a `Stakeholder` element
  (PRD-DSML-011).
- A concern usage with `#Need` gives a `Need` element (PRD-DSML-012,
  PRD-DSML-013).
- A requirement usage with `#Requirement` gives a `Requirement` element
  (PRD-DSML-014, PRD-DSML-015).
- A package of a model file gives a `Package` element. Its annotations hold
  `@DsmlVersion` (PRD-DSML-056).

Each element has its identity, its `doc` text, the values of its attributes
and its plain metadata usages, for example `@Waiver` (PRD-DSML-055). The
attributes include the attributes that a project library adds (PRD-DSML-019).

The links are `stakeholder`, `frame`, `derivation` and `refinement`
(PRD-TRACE-001). The source of a link is the element that declares it:

| Link | Source | Target |
| --- | --- | --- |
| `stakeholder` | The need | The stakeholder that types the `stakeholder` member |
| `frame` | The requirement | The framed need |
| `derivation` | Each `#derive` end | The `#original` end |
| `refinement` | Each client of the dependency | Each supplier of the dependency |
"""

from collections.abc import Iterator

from dsml.adapter.engine import EngineError
from dsml.adapter.source import SourceElement, SourceGraph, keyword_of
from dsml.ir.model import Annotation, Attribute, Element, ElementKind, Link

# trace: PRD-DSML-011, PRD-DSML-012, PRD-DSML-014
KEYWORDS: dict[str, ElementKind] = {
    "Stakeholder": "Stakeholder",
    "Need": "Need",
    "Requirement": "Requirement",
}
"""The DSML keywords of this module and the IR kinds that they give."""

# trace: PRD-DSML-017
DERIVATION = "RequirementDerivation::DerivationMetadata"
ORIGINAL = "RequirementDerivation::OriginalRequirementMetadata"
DERIVED = "RequirementDerivation::DerivedRequirementMetadata"
REFINEMENT = "ModelingMetadata::Refinement"

_PACKAGES = {"Package", "LibraryPackage"}


# trace: PRD-CORE-024, PRD-DSML-053
def convert_elements(graph: SourceGraph) -> Iterator[Element]:
    """Give the packages, stakeholders, needs and requirements of the model."""
    for source in graph.model_elements():
        if source.metaclass in _PACKAGES:
            yield _element(source, "Package", keyword=None)
            continue
        keyword = keyword_of(source, KEYWORDS)
        if keyword is not None:
            yield _element(source, KEYWORDS[keyword], keyword=keyword)


# trace: PRD-TRACE-001, PRD-TRACE-003
def convert_links(graph: SourceGraph) -> Iterator[Link]:
    """Give the `stakeholder`, `frame`, `derivation` and `refinement` links."""
    for source in graph.model_elements():
        keyword = keyword_of(source, KEYWORDS)
        if keyword == "Need":
            yield from _stakeholder_links(source)
        elif keyword == "Requirement":
            yield from _frame_links(source)
        if _has_metadata(source, DERIVATION):
            yield from _derivation_links(source)
        if _has_metadata(source, REFINEMENT):
            yield from _refinement_links(source)


# trace: PRD-CORE-024, PRD-DSML-013, PRD-DSML-015, PRD-DSML-019, PRD-DSML-053
def _element(source: SourceElement, kind: ElementKind, keyword: str | None) -> Element:
    location = source.location
    if location is None:
        raise EngineError(f"OpenSysML gave no location for {source.qualified_name}.")
    owner = source.owner
    return Element(
        identity=source.identity,
        kind=kind,
        name=source.name,
        qualified_name=source.qualified_name,
        location=location,
        short_name=source.short_name,
        owner=owner.identity if owner is not None and owner.qualified_name else None,
        doc=source.documentation,
        types=tuple(sorted({item.identity for item in source.types() if item.qualified_name})),
        attributes=tuple(attributes(source)),
        annotations=tuple(annotations(source, keyword)),
    )


# trace: PRD-CORE-024, PRD-DSML-019
def attributes(source: SourceElement) -> Iterator[Attribute]:
    """Give the attribute values of an element or of a metadata usage.

    An attribute value is an owned feature with a value, for example
    `:>> priority = Priority::must;`. The name of the attribute is the name of
    the feature that it redefines.
    """
    for kind, member in source.members():
        if kind != "FeatureMembership" or member.metaclass not in {
            "ReferenceUsage",
            "AttributeUsage",
        }:
            continue
        value = member.value()
        name = member.redefined_name()
        if value is not None and name:
            yield Attribute(name=name, value=value, location=member.location)


# trace: PRD-DSML-055, PRD-DSML-056
def annotations(source: SourceElement, keyword: str | None) -> Iterator[Annotation]:
    """Give the metadata usages on an element, except the keyword of its kind.

    Examples are `@Waiver` (PRD-DSML-055) and `@DsmlVersion` (PRD-DSML-056).
    """
    for usage in source.metadata():
        for definition in usage.types():
            if keyword is not None and definition.specializes(f"DSML::{keyword}"):
                continue
            yield Annotation(
                name=definition.name or definition.qualified_name.rsplit("::", 1)[-1],
                attributes=tuple(attributes(usage)),
                location=usage.location,
            )


def _has_metadata(source: SourceElement, qualified_name: str) -> bool:
    return any(
        definition.specializes(qualified_name)
        for usage in source.metadata()
        for definition in usage.types()
    )


# trace: PRD-DSML-012, PRD-TRACE-001
def _stakeholder_links(need: SourceElement) -> Iterator[Link]:
    for kind, member in need.members():
        if kind != "StakeholderMembership":
            continue
        location = member.location or need.location
        if location is None:
            continue
        for stakeholder in member.types():
            if stakeholder.qualified_name:
                yield Link(
                    type="stakeholder",
                    source=need.identity,
                    target=stakeholder.identity,
                    location=location,
                )


# trace: PRD-DSML-014, PRD-TRACE-001
def _frame_links(requirement: SourceElement) -> Iterator[Link]:
    for kind, member in requirement.members():
        if kind != "FramedConcernMembership":
            continue
        need = member.referenced_feature()
        location = member.location or requirement.location
        if need is not None and need.qualified_name and location is not None:
            yield Link(
                type="frame",
                source=requirement.identity,
                target=need.identity,
                location=location,
            )


# trace: PRD-DSML-017, PRD-TRACE-001
def _derivation_links(connection: SourceElement) -> Iterator[Link]:
    location = connection.location
    if location is None:
        return
    originals: list[SourceElement] = []
    derived: list[SourceElement] = []
    for kind, end in connection.members():
        if kind != "FeatureMembership" or not end.data.get("isEnd"):
            continue
        requirement = end.referenced_feature()
        if requirement is None or not requirement.qualified_name:
            continue
        if _has_metadata(end, ORIGINAL):
            originals.append(requirement)
        elif _has_metadata(end, DERIVED):
            derived.append(requirement)
    for original in originals:
        for item in derived:
            yield Link(
                type="derivation",
                source=item.identity,
                target=original.identity,
                location=location,
            )


# trace: PRD-DSML-017, PRD-TRACE-001
def _refinement_links(dependency: SourceElement) -> Iterator[Link]:
    location = dependency.location
    if location is None:
        return
    for client in dependency.references("client"):
        for supplier in dependency.references("supplier"):
            if client.qualified_name and supplier.qualified_name:
                yield Link(
                    type="refinement",
                    source=client.identity,
                    target=supplier.identity,
                    location=location,
                )
