"""Tests of the link graph and the element hash of the traceability engine (story #69)."""

import ast
import dataclasses
from pathlib import Path

import pytest

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.ir.model import (
    Annotation,
    Attribute,
    Element,
    Ir,
    Link,
    Location,
    StringValue,
)
from dsml.library import library_document
from dsml.trace import TRACE_LINK_TYPES, LinkGraph, element_hash, element_hashes

ROOT = Path(__file__).resolve().parent.parent
TRACE_PACKAGE = ROOT / "src" / "dsml" / "trace"
EXAMPLE = "docs/model/examples/order-service.sysml"
SOLUTION_LAYERS = "tests/models/ir/solution-layers.sysml"
NEEDS_LINKS = "tests/models/ir/needs-links.sysml"

# The kinds of the elements that can satisfy a requirement, with their AWS
# realizations.
NOT_SOLUTION = {"Need", "Package", "Requirement", "Stakeholder", "Verification"}


def _build(files: list[str]) -> Ir:
    documents = [(file, (ROOT / file).read_text(encoding="utf-8")) for file in files]
    with Engine() as engine:
        model = engine.parse_texts([library_document(), *documents])
        return build_ir(model, files)


@pytest.fixture(scope="module")
def example() -> Ir:
    return _build([EXAMPLE])


@pytest.fixture(scope="module")
def solution_layers() -> Ir:
    return _build([SOLUTION_LAYERS])


@pytest.fixture(scope="module")
def needs_links() -> Ir:
    return _build([NEEDS_LINKS])


def _solution(graph: LinkGraph, identities: tuple[str, ...]) -> list[str]:
    kinds = {
        identity: element.kind for identity in identities if (element := graph.element(identity))
    }
    return [identity for identity in identities if kinds[identity] not in NOT_SOLUTION]


# trace: PRD-TRACE-004
def test_example_need_goes_down_to_its_elements_and_verifications(example: Ir) -> None:
    graph = LinkGraph(example)
    assert graph.downstream("N-001", ["Requirement"]) == ("R-001", "R-002")
    assert graph.downstream("N-001", ["Verification"]) == ("V-001",)
    assert _solution(graph, graph.downstream("N-001")) == [
        "OrderService::apiService",
        "OrderService::apiServiceAws",
        "OrderService::orderApi",
    ]
    assert graph.satisfying_elements("R-001") == ("OrderService::orderApi",)
    assert graph.verifications("R-001") == ("V-001",)
    assert graph.satisfying_elements("R-002") == ()
    assert graph.verifications("R-002") == ()


# trace: PRD-TRACE-004
def test_example_element_goes_up_to_its_requirements_and_needs(example: Ir) -> None:
    graph = LinkGraph(example)
    for identity in ("OrderService::orderApi", "OrderService::apiServiceAws", "V-001"):
        assert graph.requirements_of(identity) == ("R-001",), identity
        assert graph.needs_of(identity) == ("N-001",), identity
    assert graph.upstream("OrderService::apiServiceAws") == (
        "N-001",
        "OrderService::ShopOwner",
        "OrderService::apiService",
        "OrderService::orderApi",
        "R-001",
    )
    assert graph.needs_of("R-002") == ("N-001",)
    # No application element is allocated to the database, thus it has no need.
    assert graph.needs_of("OrderService::orderDbAws") == ()


# trace: PRD-TRACE-004
@pytest.mark.parametrize("model", [EXAMPLE, NEEDS_LINKS])
def test_each_need_goes_down_and_each_element_goes_back_up(model: str) -> None:
    ir = _build([model])
    graph = LinkGraph(ir)
    needs = [element.identity for element in ir.elements if element.kind == "Need"]
    assert needs
    for need in needs:
        down = graph.downstream(need)
        assert down
        for identity in down:
            assert need in graph.needs_of(identity), identity


# trace: PRD-TRACE-002
def test_satisfy_link_can_come_from_an_infrastructure_element(solution_layers: Ir) -> None:
    graph = LinkGraph(solution_layers)
    assert graph.satisfying_elements("R-010") == ("Shop::apiAws", "Shop::shopApi")
    assert graph.requirements_of("Shop::apiAws") == ("R-010",)
    assert graph.downstream("R-010") == ("Shop::api", "Shop::apiAws", "Shop::shopApi", "V-010")


# trace: PRD-TRACE-001
def test_graph_uses_only_the_trace_link_types(solution_layers: Ir) -> None:
    graph = LinkGraph(solution_layers)
    assert {link.type for link in solution_layers.links} - TRACE_LINK_TYPES == {"calls", "uses"}
    assert all(link.type in TRACE_LINK_TYPES for link in graph.links)
    assert graph.links_from("Shop::shopWeb") == ()
    assert graph.upstream("Shop::secrets") == ()


# trace: PRD-TRACE-001, PRD-TRACE-004
def test_derivation_and_refinement_go_from_the_original_requirement(needs_links: Ir) -> None:
    graph = LinkGraph(needs_links)
    assert graph.downstream("R-001", ["Requirement"]) == ("R-002", "R-003")
    assert graph.requirements_of("R-003") == ("R-001",)
    assert graph.needs_of("R-003") == ("N-001",)
    assert graph.upstream("N-001") == ("NeedsLinks::Auditor", "NeedsLinks::Owner")
    assert [link.type for link in graph.links_from("R-003")] == ["derivation", "refinement"]
    assert [link.source for link in graph.links_to("R-001", "derivation")] == ["R-002", "R-003"]


# trace: PRD-CORE-028, PRD-TRACE-003
def test_results_are_sorted_and_do_not_change_with_the_order_of_the_ir(example: Ir) -> None:
    graph = LinkGraph(example)
    links = list(graph.links)
    assert links == sorted(links, key=lambda link: link.sort_key())
    reversed_ir = dataclasses.replace(
        example, elements=example.elements[::-1], links=example.links[::-1]
    )
    other = LinkGraph(reversed_ir)
    assert other.links == graph.links
    for element in example.elements:
        identity = element.identity
        assert other.downstream(identity) == graph.downstream(identity)
        assert other.upstream(identity) == graph.upstream(identity)
        assert list(graph.downstream(identity)) == sorted(graph.downstream(identity))
        assert list(graph.upstream(identity)) == sorted(graph.upstream(identity))


def test_cycle_of_links_does_not_stop_the_queries() -> None:
    at = Location("model.sysml", 1, 1)
    ir = Ir(
        links=(
            Link("derivation", "R-001", "R-002", at),
            Link("derivation", "R-002", "R-001", at),
        )
    )
    graph = LinkGraph(ir)
    assert graph.downstream("R-001") == ("R-002",)
    assert graph.upstream("R-001") == ("R-002",)


def test_unknown_identity_gives_an_error(example: Ir) -> None:
    with pytest.raises(KeyError, match="R-999"):
        LinkGraph(example).downstream("R-999")


def _move(location: Location | None, lines: int) -> Location | None:
    if location is None:
        return None
    return dataclasses.replace(location, line=location.line + lines, column=location.column + 1)


def _moved(element: Element, lines: int) -> Element:
    """Give the element with all its source locations moved."""
    return dataclasses.replace(
        element,
        location=Location("other/model.sysml", element.location.line + lines, 1),
        attributes=tuple(
            dataclasses.replace(attribute, location=_move(attribute.location, lines))
            for attribute in element.attributes
        ),
        annotations=tuple(
            dataclasses.replace(annotation, location=_move(annotation.location, lines))
            for annotation in element.annotations
        ),
    )


# trace: PRD-TRACE-015
def test_hash_does_not_change_when_only_the_source_location_changes(example: Ir) -> None:
    for element in example.elements:
        moved = _moved(element, 7)
        assert moved != element
        assert element_hash(moved) == element_hash(element), element.identity


# trace: PRD-TRACE-015
def test_hash_changes_when_the_element_changes(example: Ir) -> None:
    need = next(element for element in example.elements if element.identity == "N-001")
    original = element_hash(need)
    assert len(original) == 64
    assert int(original, 16) >= 0
    assert element_hash(dataclasses.replace(need, doc="Other text.")) != original
    title = Attribute("title", StringValue("Other title"))
    others = tuple(attribute for attribute in need.attributes if attribute.name != "title")
    assert element_hash(dataclasses.replace(need, attributes=(*others, title))) != original
    waiver = Annotation("Waiver")
    assert element_hash(dataclasses.replace(need, annotations=(waiver,))) != original


# trace: PRD-TRACE-015, PRD-CORE-028
def test_hash_does_not_change_with_the_order_of_the_lists(example: Ir) -> None:
    for element in example.elements:
        reversed_element = dataclasses.replace(
            element, attributes=element.attributes[::-1], annotations=element.annotations[::-1]
        )
        assert element_hash(reversed_element) == element_hash(element)


# trace: PRD-TRACE-015
def test_element_hashes_give_each_element_in_sorted_order(example: Ir) -> None:
    hashes = element_hashes(example)
    assert list(hashes) == sorted(element.identity for element in example.elements)
    assert hashes["N-001"] == element_hash(
        next(element for element in example.elements if element.identity == "N-001")
    )
    assert element_hashes(_build([EXAMPLE])) == hashes


# trace: PRD-CORE-020, PRD-CORE-026
def test_trace_package_reads_only_the_ir() -> None:
    allowed = ("dsml.ir", "dsml.trace")
    for path in sorted(TRACE_PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert not name.startswith("opensysml"), path
                if name.startswith("dsml"):
                    assert name.startswith(allowed), f"{path.name} imports {name}"
