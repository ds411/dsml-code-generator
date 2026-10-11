"""Tests of the conversion of the needs and requirements layers into the IR (story #30).

These tests start a private `sysml-grpc` child process. If the binary is not
in the cache, the `opensysml` client downloads it one time.
"""

import csv
import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from jsonschema.protocols import Validator

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.adapter.source import SourceGraph, value_of
from dsml.ir.model import (
    Annotation,
    BooleanValue,
    Element,
    EnumValue,
    IntegerValue,
    Ir,
    ListValue,
    Location,
    RealValue,
    ReferenceValue,
    StringValue,
    Value,
)
from dsml.ir.schema import load_schema
from dsml.ir.writer import write_ir
from dsml.library import library_document

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = "docs/model/examples/order-service.sysml"
PRD_FILES = sorted(
    path.relative_to(ROOT).as_posix() for path in (ROOT / "docs/model/prd").glob("*.sysml")
)
NEEDS_LINKS = "tests/models/ir/needs-links.sysml"
PROJECT_LIBRARY = [
    "tests/models/ir/project-library/library.sysml",
    "tests/models/ir/project-library/model.sysml",
]
REQUIREMENTS_CSV = ROOT / "docs" / "index" / "requirements.csv"
NEEDS_KINDS = {"Package", "Stakeholder", "Need", "Requirement"}


def _build(files: list[str]) -> Ir:
    documents = [(file, (ROOT / file).read_text(encoding="utf-8")) for file in files]
    with Engine() as engine:
        model = engine.parse_texts([library_document(), *documents])
        return build_ir(model, files)


@pytest.fixture(scope="module")
def example() -> Ir:
    return _build([EXAMPLE])


@pytest.fixture(scope="module")
def prd() -> Ir:
    return _build(PRD_FILES)


@pytest.fixture(scope="module")
def needs_links() -> Ir:
    return _build([NEEDS_LINKS])


@pytest.fixture(scope="module")
def project_library() -> Ir:
    return _build(PROJECT_LIBRARY)


def _validator() -> Validator:
    return jsonschema.Draft202012Validator(load_schema())


def _elements(ir: Ir) -> dict[str, Element]:
    return {element.identity: element for element in ir.elements}


def _links(ir: Ir) -> set[tuple[str, str, str]]:
    return {(link.source, link.type, link.target) for link in ir.links}


def _values(element: Element | Annotation) -> dict[str, Value]:
    return {attribute.name: attribute.value for attribute in element.attributes}


# The link types of the needs and requirements layers.
NEEDS_LINK_TYPES = {"stakeholder", "frame", "derivation", "refinement"}


def _enum(enumeration: str, literal: str) -> EnumValue:
    return EnumValue(enumeration=f"DSML::{enumeration}", literal=literal)


def _line_of(file: str, pattern: str) -> int:
    """Give the line of the first line in the file that contains the pattern."""
    lines = (ROOT / file).read_text(encoding="utf-8").splitlines()
    return next(number for number, line in enumerate(lines, 1) if pattern in line)


# trace: PRD-CORE-024, PRD-DSML-011, PRD-DSML-013, PRD-DSML-015, PRD-DSML-053
def test_example_model_gives_the_needs_and_requirements(example: Ir) -> None:
    elements = _elements(example)
    # The elements of the other layers are in tests/test_solution_layers.py (story #31).
    assert sorted((e.identity, e.kind) for e in example.elements if e.kind in NEEDS_KINDS) == [
        ("N-001", "Need"),
        ("OrderService", "Package"),
        ("OrderService::ShopOwner", "Stakeholder"),
        ("R-001", "Requirement"),
        ("R-002", "Requirement"),
    ]
    need = elements["N-001"]
    assert need.name == "trackOrders"
    assert need.qualified_name == "OrderService::trackOrders"
    assert need.short_name == "N-001"
    assert need.owner == "OrderService"
    assert need.doc == "The shop owner must see the status of each order."
    assert _values(need) == {
        "title": StringValue("Track orders"),
        "priority": _enum("Priority", "must"),
        "status": _enum("Status", "approved"),
    }
    assert _values(elements["R-002"]) == {
        "title": StringValue("Order data in two zones"),
        "kind": _enum("RequirementKind", "constraint"),
        "priority": _enum("Priority", "must"),
        "status": _enum("Status", "approved"),
    }
    stakeholder = elements["OrderService::ShopOwner"]
    assert stakeholder.short_name is None
    assert stakeholder.doc is None


# trace: PRD-TRACE-001, PRD-TRACE-003
def test_example_model_gives_each_link_of_the_three_layers(example: Ir) -> None:
    assert {link for link in _links(example) if link[1] in NEEDS_LINK_TYPES} == {
        ("N-001", "stakeholder", "OrderService::ShopOwner"),
        ("R-001", "frame", "N-001"),
        ("R-002", "frame", "N-001"),
    }


# trace: PRD-CORE-007, PRD-CORE-024
def test_example_model_gives_the_source_locations(example: Ir) -> None:
    elements = _elements(example)
    assert elements["N-001"].location == Location(EXAMPLE, _line_of(EXAMPLE, "#Need"), 5)
    assert elements["OrderService"].location == Location(EXAMPLE, 1, 1)
    title = next(a for a in elements["R-001"].attributes if a.name == "title")
    assert title.location == Location(EXAMPLE, _line_of(EXAMPLE, '"Get order status"'), 9)
    locations = {(link.type, link.source): link.location for link in example.links}
    assert locations[("stakeholder", "N-001")] == Location(
        EXAMPLE, _line_of(EXAMPLE, "stakeholder owner"), 9
    )
    assert locations[("frame", "R-001")].line == _line_of(EXAMPLE, "frame trackOrders")


# trace: PRD-DSML-056
def test_root_package_gives_the_dsml_version(example: Ir) -> None:
    package = _elements(example)["OrderService"]
    assert [annotation.name for annotation in package.annotations] == ["DsmlVersion"]
    assert _values(package.annotations[0]) == {"major": IntegerValue(1), "minor": IntegerValue(0)}


# trace: PRD-CORE-024, PRD-DSML-013, PRD-DSML-015
def test_prd_model_gives_each_requirement_of_the_index(prd: Ir) -> None:
    with REQUIREMENTS_CSV.open(encoding="utf-8", newline="") as file:
        rows = {row["id"]: row["requirement"] for row in csv.DictReader(file)}
    requirements = {e.identity: e for e in prd.elements if e.kind == "Requirement"}
    assert sorted(requirements) == sorted(rows)
    problems: list[str] = []
    for identity, text in sorted(rows.items()):
        element = requirements[identity]
        values = _values(element)
        if element.doc != text.replace("`", ""):
            problems.append(f"{identity}: doc {element.doc!r}")
        if sorted(values) != ["kind", "priority", "status", "title"]:
            problems.append(f"{identity}: attributes {sorted(values)}")
        if not isinstance(values.get("title"), StringValue):
            problems.append(f"{identity}: title {values.get('title')!r}")
        for name in ("kind", "priority", "status"):
            if not isinstance(values.get(name), EnumValue):
                problems.append(f"{identity}: {name} {values.get(name)!r}")
    assert problems == []


# trace: PRD-TRACE-001, PRD-TRACE-003
def test_prd_model_gives_the_needs_and_their_links(prd: Ir) -> None:
    elements = _elements(prd)
    needs = sorted(e.identity for e in prd.elements if e.kind == "Need")
    assert needs == ["N-001", "N-002", "N-003", "N-004", "N-005"]
    assert [e.kind for e in prd.elements if e.kind == "Stakeholder"] == ["Stakeholder"] * 3
    frames = [link for link in prd.links if link.type == "frame"]
    assert {link.source for link in frames} == {
        e.identity for e in prd.elements if e.kind == "Requirement"
    }
    assert {link.target for link in frames} <= set(needs)
    stakeholders = _links(prd) - {(f.source, f.type, f.target) for f in frames}
    assert ("N-001", "stakeholder", "PrdNeeds::SystemsEngineer") in stakeholders
    assert all(elements[target].kind == "Stakeholder" for _, _, target in stakeholders)
    assert len(stakeholders) == 10


# trace: PRD-CORE-007, PRD-CORE-024, PRD-CORE-033
def test_each_element_and_each_link_has_a_location_in_a_model_file(prd: Ir) -> None:
    files = set(PRD_FILES)
    assert {element.location.file for element in prd.elements} == files
    assert {link.location.file for link in prd.links} <= files
    assert all(e.kind in NEEDS_KINDS for e in prd.elements)


# trace: PRD-DSML-015
def test_requirement_gives_the_optional_attributes(needs_links: Ir) -> None:
    values = _values(_elements(needs_links)["R-001"])
    assert values["rationale"] == StringValue("The owner needs the history.")
    assert values["source"] == StringValue("Workshop 3")
    assert values["owner"] == StringValue("Order team")
    assert _values(_elements(needs_links)["R-003"])["kind"] == _enum("RequirementKind", "interface")


# trace: PRD-DSML-012, PRD-DSML-017, PRD-TRACE-001, PRD-TRACE-003
def test_test_model_gives_each_link_type(needs_links: Ir) -> None:
    assert _links(needs_links) == {
        ("N-001", "stakeholder", "NeedsLinks::Auditor"),
        ("N-001", "stakeholder", "NeedsLinks::Owner"),
        ("R-001", "frame", "N-001"),
        ("R-002", "derivation", "R-001"),
        ("R-003", "derivation", "R-001"),
        ("R-003", "refinement", "R-001"),
    }
    locations = {(link.type, link.source): link.location.line for link in needs_links.links}
    assert locations[("derivation", "R-002")] == _line_of(NEEDS_LINKS, "#derivation connection")
    assert locations[("refinement", "R-003")] == _line_of(NEEDS_LINKS, "#refinement dependency")


# trace: PRD-DSML-053
def test_element_with_no_short_name_uses_its_qualified_name(needs_links: Ir) -> None:
    element = _elements(needs_links)["NeedsLinks::noShortName"]
    assert element.short_name is None
    assert element.kind == "Requirement"


# trace: PRD-DSML-055
def test_waiver_is_an_annotation_of_its_element(needs_links: Ir) -> None:
    requirement = _elements(needs_links)["R-001"]
    assert [annotation.name for annotation in requirement.annotations] == ["Waiver"]
    waiver = requirement.annotations[0]
    assert _values(waiver) == {
        "rule": StringValue("COV-003"),
        "reason": StringValue("The test comes in the next release."),
        "owner": StringValue("Order team"),
        "expires": StringValue("2027-01-31"),
    }
    assert waiver.location == Location(NEEDS_LINKS, _line_of(NEEDS_LINKS, "@Waiver"), 9)


# trace: PRD-DSML-019
def test_project_library_adds_attributes(project_library: Ir) -> None:
    elements = _elements(project_library)
    need = elements["N-001"]
    assert need.types == ("ProjectLibrary::ProjectNeed",)
    assert _values(need)["businessValue"] == IntegerValue(8)
    assert _values(elements["R-001"])["costCenter"] == StringValue("CC-100")
    assert elements["R-001"].types == ("ProjectLibrary::ProjectRequirement",)
    assert _links(project_library) == {("R-001", "frame", "N-001"), ("R-002", "frame", "N-001")}


# trace: PRD-DSML-019
def test_project_keyword_that_specializes_a_dsml_keyword_gives_its_kind(
    project_library: Ir,
) -> None:
    element = _elements(project_library)["R-002"]
    assert element.kind == "Requirement"
    assert _values(element)["safetyRelated"] == BooleanValue(True)
    assert [annotation.name for annotation in element.annotations] == []


# trace: PRD-CORE-022, PRD-CORE-025, PRD-CORE-028
@pytest.mark.parametrize("name", ["example", "prd", "needs_links", "project_library"])
def test_ir_agrees_with_the_schema_and_has_no_opensysml_id(
    name: str, request: pytest.FixtureRequest
) -> None:
    ir: Ir = request.getfixturevalue(name)
    text = write_ir(ir).decode("utf-8")
    _validator().validate(json.loads(text))
    assert "@id" not in text
    assert "sysx:" not in text
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text)
    assert not re.search(r"\w__\w", text)


# trace: PRD-CORE-028
def test_two_conversions_give_the_same_bytes(needs_links: Ir) -> None:
    assert write_ir(_build([NEEDS_LINKS])) == write_ir(needs_links)


# trace: PRD-CORE-021
def test_model_with_an_error_gives_only_the_findings() -> None:
    file = "tests/models/rules/SYN-001/reject.sysml"
    ir = _build([file])
    assert ir.elements == ()
    assert ir.links == ()
    assert ir.files == (file,)
    assert {finding.rule for finding in ir.findings} == {"SYN-001"}


def _graph(items: list[dict[str, Any]]) -> SourceGraph:
    return SourceGraph(items, files=())


def _ref(identifier: str) -> dict[str, str]:
    return {"@id": identifier}


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        ({"@type": "LiteralString", "value": "a"}, StringValue("a")),
        ({"@type": "LiteralInteger", "value": 3}, IntegerValue(3)),
        ({"@type": "LiteralRational", "value": 0.5}, RealValue(0.5)),
        ({"@type": "LiteralBoolean", "value": False}, BooleanValue(False)),
        ({"@type": "LiteralInteger", "value": "3"}, None),
        ({"@type": "LiteralInfinity"}, None),
        ({"@type": "OperatorExpression", "operator": "+"}, None),
    ],
)
def test_value_of_a_literal(item: dict[str, Any], expected: Value | None) -> None:
    graph = _graph([{"@id": "v", **item}])
    element = graph.element("v")
    assert element is not None
    assert value_of(element) == expected


# trace: PRD-CORE-024, PRD-CORE-025
def test_value_of_references_and_lists() -> None:
    graph = _graph(
        [
            {"@id": "E", "@type": "EnumerationDefinition", "qualifiedName": "P::Color"},
            {
                "@id": "E_red",
                "@type": "EnumerationUsage",
                "qualifiedName": "P::Color::red",
                "declaredName": "red",
                "owner": _ref("E"),
            },
            {
                "@id": "R",
                "@type": "RequirementUsage",
                "qualifiedName": "P::r",
                "declaredShortName": "R-001",
            },
            {"@id": "a", "@type": "FeatureReferenceExpression", "referent": _ref("E_red")},
            {"@id": "b", "@type": "FeatureReferenceExpression", "referent": _ref("R")},
            {
                "@id": "c",
                "@type": "OperatorExpression",
                "operator": ",",
                "argument": [_ref("a"), _ref("b")],
            },
            {
                "@id": "d",
                "@type": "OperatorExpression",
                "operator": ",",
                "argument": [_ref("a"), _ref("x")],
            },
            {"@id": "x", "@type": "OperatorExpression", "operator": "+"},
        ]
    )
    expected = {
        "a": EnumValue("P::Color", "red"),
        "b": ReferenceValue("R-001"),
        "c": ListValue((EnumValue("P::Color", "red"), ReferenceValue("R-001"))),
        "d": None,
    }
    for identifier, value in expected.items():
        element = graph.element(identifier)
        assert element is not None
        assert value_of(element) == value
