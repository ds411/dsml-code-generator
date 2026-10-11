"""Tests of the IR models, the JSON Schema and the canonical JSON writer (story #28)."""

import ast
import dataclasses
import getpass
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import typing
import zipfile
from pathlib import Path
from typing import Any, cast

import jsonschema
import pytest
from jsonschema.protocols import Validator

from dsml.ir import model
from dsml.ir.model import (
    IR_VERSION,
    MODEL,
    ORDER,
    SORTED,
    Annotation,
    Attribute,
    BooleanValue,
    ConstraintResult,
    Element,
    EnumValue,
    Finding,
    IntegerValue,
    Ir,
    Link,
    ListValue,
    Location,
    Multiplicity,
    Node,
    RealValue,
    ReferenceValue,
    StringValue,
    Value,
)
from dsml.ir.schema import SCHEMA_FILE, load_schema, schema_text
from dsml.ir.writer import canonical_json, json_key, to_data, write_ir

ROOT = Path(__file__).resolve().parent.parent
IR_PACKAGE = ROOT / "src" / "dsml" / "ir"
MODEL_FILE = "docs/model/examples/order-service.sysml"

# Each IR model and the schema definition of its JSON form. "" is the root.
SCHEMA_DEFINITIONS: dict[type[Node], str] = {
    Ir: "",
    Element: "Element",
    Link: "Link",
    ConstraintResult: "ConstraintResult",
    Finding: "Finding",
    Location: "Location",
    Multiplicity: "Multiplicity",
    Attribute: "Attribute",
    Annotation: "Annotation",
    StringValue: "StringValue",
    IntegerValue: "IntegerValue",
    RealValue: "RealValue",
    BooleanValue: "BooleanValue",
    EnumValue: "EnumValue",
    ReferenceValue: "ReferenceValue",
    ListValue: "ListValue",
}


def at(line: int, column: int = 5) -> Location:
    return Location(MODEL_FILE, line, column)


def sample_ir() -> Ir:
    """Make an IR with each model class, from a part of the example model."""
    priority = Attribute("priority", EnumValue("DSML::Priority", "must"), at(10, 9))
    status = Attribute("status", EnumValue("DSML::Status", "approved"), at(11, 9))
    elements = (
        Element(
            identity="OrderService",
            kind="Package",
            name="OrderService",
            qualified_name="OrderService",
            location=at(1, 1),
            annotations=(
                Annotation(
                    "DsmlVersion",
                    (Attribute("minor", IntegerValue(0)), Attribute("major", IntegerValue(1))),
                    at(4),
                ),
            ),
        ),
        Element(
            identity="OrderService::ShopOwner",
            kind="Stakeholder",
            name="ShopOwner",
            qualified_name="OrderService::ShopOwner",
            owner="OrderService",
            location=at(7),
        ),
        Element(
            identity="N-001",
            kind="Need",
            name="trackOrders",
            qualified_name="OrderService::trackOrders",
            short_name="N-001",
            owner="OrderService",
            doc="The shop owner must see the status of each order.",
            location=at(9),
            attributes=(status, priority, Attribute("title", StringValue("Track orders"))),
        ),
        Element(
            identity="R-002",
            kind="Requirement",
            name="orderDataSafe",
            qualified_name="OrderService::orderDataSafe",
            short_name="R-002",
            owner="OrderService",
            doc="In prod, the order database must continue to operate after the loss of one "
            "availability zone.",
            location=at(27),
            attributes=(status, priority),
        ),
        Element(
            identity="OrderService::Order::total",
            kind="Field",
            name="total",
            qualified_name="OrderService::Order::total",
            owner="OrderService::Order",
            multiplicity=Multiplicity(1, 1),
            types=("DSML::Decimal",),
            location=at(44, 9),
            annotations=(
                Annotation("FieldRules", (Attribute("minValue", RealValue(0.5)),), at(44, 43)),
            ),
        ),
        Element(
            identity="OrderService::Order::id",
            kind="Field",
            name="id",
            qualified_name="OrderService::Order::id",
            owner="OrderService::Order",
            multiplicity=Multiplicity(1, 1),
            types=("DSML::Uuid",),
            location=at(42, 9),
            annotations=(Annotation("Key", (), at(42, 9)),),
        ),
        Element(
            identity="OrderService::CancelOrder::orderId",
            kind="Parameter",
            name="orderId",
            qualified_name="OrderService::CancelOrder::orderId",
            owner="OrderService::CancelOrder",
            direction="in",
            types=("DSML::Uuid",),
            location=at(48, 9),
        ),
        Element(
            identity="OrderService::orderApi::orders",
            kind="Exposed",
            name="orders",
            qualified_name="OrderService::orderApi::orders",
            owner="OrderService::orderApi",
            multiplicity=Multiplicity(0, None),
            types=("OrderService::Order",),
            location=at(57, 9),
            attributes=(
                Attribute(
                    "crud",
                    ListValue(
                        (
                            EnumValue("DSML::CrudKind", "create"),
                            EnumValue("DSML::CrudKind", "read"),
                            EnumValue("DSML::CrudKind", "list"),
                        )
                    ),
                ),
                Attribute("public", BooleanValue(False)),
                Attribute("entity", ReferenceValue("OrderService::Order")),
            ),
        ),
        Element(
            identity="V-001",
            kind="Verification",
            name="orderStatusTest",
            qualified_name="OrderService::orderStatusTest",
            short_name="V-001",
            owner="OrderService",
            location=at(98),
            attributes=(
                Attribute(
                    "testFiles",
                    ListValue((StringValue("app/features/order/read_order/test_endpoint.py"),)),
                ),
            ),
        ),
    )
    links = (
        Link("verify", "V-001", "R-001", at(102, 21)),
        Link("frame", "R-002", "N-001", at(32, 9)),
        Link("stakeholder", "N-001", "OrderService::ShopOwner", at(15, 9)),
        Link("allocate", "OrderService::orderApi", "OrderService::apiService", at(73)),
        Link("frame", "R-001", "N-001", at(23, 9)),
    )
    constraint_results = (
        ConstraintResult("R-002", 1, "OrderService::staging", "false", at(33, 9)),
        ConstraintResult("R-002", 1, "OrderService::prod", "true", at(33, 9)),
        ConstraintResult(
            "R-002",
            1,
            "OrderService::dev",
            "unknown",
            at(33, 9),
            missing_features=("orderDbDev.multiAz", "orderDb.storage"),
        ),
    )
    findings = (
        Finding("SYN-002", "warning", "A warning on a later line.", at(90, 1)),
        Finding("SYN-001", "error", "The name cannot be resolved.", at(40, 3), "N-001"),
        Finding("SYN-001", "error", "A finding with no location."),
        Finding("SYN-001", "error", "The text is not correct.", at(40, 3)),
    )
    return Ir(
        files=(MODEL_FILE, "docs/model/examples/b.sysml"),
        elements=elements,
        links=links,
        constraint_results=constraint_results,
        findings=findings,
    )


def reversed_lists[N: Node](node: N) -> N:
    """Give a copy with the reverse order in each sorted list, at each level."""
    changes: dict[str, object] = {}
    for field in dataclasses.fields(node):
        value: object = getattr(node, field.name)
        if isinstance(value, tuple):
            items = tuple(
                reversed_lists(item) if isinstance(item, Node) else item
                for item in cast(tuple[object, ...], value)
            )
            changes[field.name] = items[::-1] if field.metadata[ORDER] == SORTED else items
        elif isinstance(value, Node):
            changes[field.name] = reversed_lists(value)
    return dataclasses.replace(node, **changes)


def validator() -> Validator:
    schema = load_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


# trace: PRD-CORE-022
def test_written_ir_passes_the_schema() -> None:
    data = json.loads(write_ir(sample_ir()).decode("utf-8"))
    validator().validate(data)


# trace: PRD-CORE-022
def test_empty_ir_passes_the_schema() -> None:
    data = json.loads(write_ir(Ir()).decode("utf-8"))
    validator().validate(data)
    assert data == {
        "constraintResults": [],
        "elements": [],
        "files": [],
        "findings": [],
        "irVersion": IR_VERSION,
        "links": [],
    }


# trace: PRD-CORE-022
@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["irVersion"], "2.0.0"),
        (["files", 0], "/home/user/model.sysml"),
        (["files", 0], "C:/model.sysml"),
        (["files", 0], "docs\\model.sysml"),
        (["files", 0], "docs/../model.sysml"),
        (["elements", 0, "kind"], "Widget"),
        (["elements", 0, "location", "line"], 0),
        (["links", 0, "type"], "trace"),
        (["constraintResults", 0, "value"], "maybe"),
        (["findings", 0, "severity"], "fatal"),
        (["elements", 0, "unknownKey"], 1),
    ],
)
def test_schema_rejects_bad_data(path: list[str | int], value: object) -> None:
    data: Any = json.loads(write_ir(sample_ir()).decode("utf-8"))
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(jsonschema.ValidationError):
        validator().validate(data)


# trace: PRD-CORE-022, PRD-CORE-023
@pytest.mark.parametrize("node_type", list(SCHEMA_DEFINITIONS))
def test_schema_and_models_agree(node_type: type[Node]) -> None:
    schema = load_schema()
    name = SCHEMA_DEFINITIONS[node_type]
    definition = schema["$defs"][name] if name else schema
    keys = {json_key(field.name) for field in dataclasses.fields(node_type)}
    if issubclass(node_type, Value):
        keys.add("type")
        assert definition["properties"]["type"] == {"const": node_type.TYPE}
    assert set(definition["properties"]) == keys
    assert set(definition["required"]) == keys
    assert definition["additionalProperties"] is False


def test_schema_has_a_definition_of_each_model() -> None:
    node_types = {
        item
        for item in vars(model).values()
        if isinstance(item, type) and issubclass(item, Node) and item not in (Node, Value)
    }
    assert node_types == set(SCHEMA_DEFINITIONS)
    value_types = {item for item in node_types if issubclass(item, Value)}
    value_refs = {ref["$ref"] for ref in load_schema()["$defs"]["Value"]["oneOf"]}
    assert value_refs == {f"#/$defs/{SCHEMA_DEFINITIONS[item]}" for item in value_types}


# trace: PRD-CORE-023
@pytest.mark.parametrize(
    ("alias", "pointer"),
    [
        (model.ElementKind, ("$defs", "Element", "properties", "kind", "enum")),
        (model.LinkType, ("$defs", "Link", "properties", "type", "enum")),
        (model.ConstraintValue, ("$defs", "ConstraintResult", "properties", "value", "enum")),
        (model.Severity, ("$defs", "Finding", "properties", "severity", "enum")),
    ],
)
def test_schema_enumerations_and_models_agree(
    alias: typing.TypeAliasType, pointer: tuple[str, ...]
) -> None:
    node: Any = load_schema()
    for key in pointer:
        node = node[key]
    assert node == list(typing.get_args(alias.__value__))


# trace: PRD-CORE-023
def test_schema_version_agrees_with_the_ir_version() -> None:
    schema = load_schema()
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", IR_VERSION)
    assert schema["properties"]["irVersion"] == {
        "description": "The semantic version of the IR (PRD-CORE-023).",
        "const": IR_VERSION,
    }
    assert schema["$id"] == f"urn:dsml:ir:{IR_VERSION}"
    assert schema["title"] == f"DSML IR {IR_VERSION}"


@pytest.mark.parametrize("node_type", list(SCHEMA_DEFINITIONS))
def test_each_list_field_gives_its_order(node_type: type[Node]) -> None:
    for field in dataclasses.fields(node_type):
        if str(field.type).startswith("tuple["):
            assert field.metadata.get(ORDER) in (SORTED, MODEL), field.name


# trace: PRD-CORE-031, PRD-CORE-032
def test_same_data_in_a_different_order_gives_the_same_bytes() -> None:
    ir = sample_ir()
    shuffled = reversed_lists(ir)
    assert shuffled != ir
    assert write_ir(shuffled) == write_ir(ir)


# trace: PRD-CORE-031
def test_lists_are_in_canonical_order() -> None:
    data = to_data(sample_ir())
    elements = cast(list[dict[str, Any]], data["elements"])
    identities = [element["identity"] for element in elements]
    assert identities == sorted(identities)
    links = cast(list[dict[str, Any]], data["links"])
    assert [(link["source"], link["type"], link["target"]) for link in links] == [
        ("N-001", "stakeholder", "OrderService::ShopOwner"),
        ("OrderService::orderApi", "allocate", "OrderService::apiService"),
        ("R-001", "frame", "N-001"),
        ("R-002", "frame", "N-001"),
        ("V-001", "verify", "R-001"),
    ]
    results = cast(list[dict[str, Any]], data["constraintResults"])
    assert [result["environment"] for result in results] == [
        "OrderService::dev",
        "OrderService::prod",
        "OrderService::staging",
    ]
    assert results[0]["missingFeatures"] == ["orderDb.storage", "orderDbDev.multiAz"]
    findings = cast(list[dict[str, Any]], data["findings"])
    assert [(finding["rule"], finding["message"]) for finding in findings] == [
        ("SYN-001", "A finding with no location."),
        ("SYN-001", "The name cannot be resolved."),
        ("SYN-001", "The text is not correct."),
        ("SYN-002", "A warning on a later line."),
    ]
    assert data["files"] == ["docs/model/examples/b.sysml", MODEL_FILE]
    need = next(element for element in elements if element["identity"] == "N-001")
    assert [item["name"] for item in need["attributes"]] == ["priority", "status", "title"]


# trace: PRD-CORE-031
def test_list_values_keep_the_order_of_the_model() -> None:
    def crud(*literals: str) -> bytes:
        values = tuple(EnumValue("DSML::CrudKind", literal) for literal in literals)
        element = Element(
            identity="A::b",
            kind="Exposed",
            name="b",
            qualified_name="A::b",
            location=at(1),
            attributes=(Attribute("crud", ListValue(values)),),
        )
        return write_ir(Ir(elements=(element,)))

    first = crud("create", "read")
    second = crud("read", "create")
    assert first != second
    assert first.index(b'"create"') < first.index(b'"read"')
    assert second.index(b'"read"') < second.index(b'"create"')


# trace: PRD-CORE-034
def test_byte_form() -> None:
    element = Element(
        identity="A",
        kind="Package",
        name="A",
        qualified_name="A",
        location=at(1),
        doc="Grüße\r\nline two \u00e9",
    )
    output = write_ir(Ir(elements=(element,)))
    assert not output.startswith(b"\xef\xbb\xbf")
    text = output.decode("utf-8")
    assert "\r" not in text
    assert text.endswith("}\n")
    assert not text.endswith("\n\n")
    assert "Grüße" in text
    assert "\\u00e9" not in text
    assert "é" in text
    assert json.loads(text)["elements"][0]["doc"] == "Grüße\r\nline two é"


# trace: PRD-CORE-034
def test_canonical_json_sorts_keys_and_indents() -> None:
    assert canonical_json({"b": [1, {"d": True, "c": None}], "a": "x"}) == (
        b'{\n  "a": "x",\n  "b": [\n    1,\n    {\n      "c": null,\n      "d": true\n'
        b"    }\n  ]\n}\n"
    )


# trace: PRD-CORE-028
def test_two_writes_give_the_same_bytes() -> None:
    assert write_ir(sample_ir()) == write_ir(sample_ir())


# trace: PRD-CORE-033
def test_output_has_no_timestamp_and_no_machine_data() -> None:
    text = write_ir(sample_ir()).decode("utf-8")
    assert not re.search(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text)
    assert not re.search(r"[0-9]{2}:[0-9]{2}:[0-9]{2}", text)
    assert str(ROOT) not in text
    assert os.getcwd() not in text
    assert f'"{getpass.getuser()}' not in text
    assert socket.gethostname() not in text
    for value in re.findall(r'"file": "([^"]*)"', text):
        assert not value.startswith("/")


# trace: PRD-CORE-033
@pytest.mark.parametrize(
    "path",
    ["/abs/model.sysml", "C:/model.sysml", "c:model.sysml", "a\\b.sysml", "../a.sysml", "a/../b"],
)
def test_models_reject_a_path_that_is_not_relative(path: str) -> None:
    with pytest.raises(ValueError, match="relative POSIX path"):
        Location(path, 1, 1)
    with pytest.raises(ValueError, match="relative POSIX path"):
        Ir(files=(path,))


def test_location_rejects_line_zero() -> None:
    with pytest.raises(ValueError, match="start at 1"):
        Location("a.sysml", 0, 1)


def test_writer_rejects_a_real_value_that_is_not_finite() -> None:
    element = Element(
        identity="A",
        kind="Package",
        name="A",
        qualified_name="A",
        location=at(1),
        attributes=(Attribute("x", RealValue(float("nan"))),),
    )
    with pytest.raises(ValueError, match="real value"):
        write_ir(Ir(elements=(element,)))


def test_writer_keeps_booleans_and_integers_apart() -> None:
    values = to_data(ListValue((BooleanValue(True), IntegerValue(1), RealValue(1.0))))
    assert canonical_json(values) == (
        b'{\n  "items": [\n    {\n      "type": "boolean",\n      "value": true\n    },\n'
        b'    {\n      "type": "integer",\n      "value": 1\n    },\n'
        b'    {\n      "type": "real",\n      "value": 1.0\n    }\n  ],\n  "type": "list"\n}\n'
    )


class ForeignObject:
    """An object that is not an IR model, for example an OpenSysML element."""

    id = "8c1e5b4e-3f0a-4f7c-9a59-0d7c5c1f2b6e"


# trace: PRD-CORE-025
def test_writer_rejects_an_object_that_is_not_an_ir_model() -> None:
    element = Element(
        identity="A",
        kind="Package",
        name="A",
        qualified_name="A",
        location=at(1),
        doc=cast(str, ForeignObject()),
    )
    with pytest.raises(TypeError, match="ForeignObject"):
        write_ir(Ir(elements=(element,)))
    with pytest.raises(TypeError, match="ForeignObject"):
        write_ir(Ir(elements=cast(tuple[Element, ...], (ForeignObject(),))))


# trace: PRD-CORE-020, PRD-CORE-025
@pytest.mark.parametrize("source", sorted(IR_PACKAGE.glob("*.py")), ids=lambda path: path.name)
def test_ir_package_does_not_import_opensysml(source: Path) -> None:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    for name in modules:
        assert not name.startswith(("opensysml", "dsml.adapter")), name


# trace: PRD-CORE-025
def test_ir_package_loads_no_opensysml_module() -> None:
    code = (
        "import sys, dsml.ir.model, dsml.ir.schema, dsml.ir.writer\n"
        "print(sorted(name for name in sys.modules if name.startswith('opensysml')))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout == "[]\n"


# trace: PRD-CORE-025
def test_ir_holds_no_opensysml_internal_id() -> None:
    text = write_ir(sample_ir()).decode("utf-8")
    uuid = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    assert not re.search(uuid, text, re.IGNORECASE)
    assert "opensysml" not in text.lower()


def test_schema_file_is_canonical_utf8() -> None:
    raw = (IR_PACKAGE / SCHEMA_FILE).read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    assert raw.endswith(b"}\n")
    assert schema_text() == raw.decode("utf-8")


# trace: PRD-CORE-022
def test_wheel_contains_the_schema(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None, "The test must have uv to build the wheel."
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(tmp_path), "--quiet"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    (wheel,) = tmp_path.glob("dsml-*.whl")
    with zipfile.ZipFile(wheel) as archive:
        packaged = archive.read(f"dsml/ir/{SCHEMA_FILE}").decode("utf-8")
    assert packaged == schema_text()
