"""Tests of the import of an external OpenAPI file into the IR (story #163).

An external API is a part usage with the keyword `#ExternalApi`. The IR
adapter converts its OpenAPI 3.1 JSON file into IR entities and operations
(PRD-DSML-058, PRD-CORE-055). A file that does not exist, and an item outside
the subset of decision Q65, each give one STR-017 finding (PRD-VAL-016).
The test models are in `tests/models/openapi/`.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import RunRule

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.adapter.openapi import import_apis
from dsml.config import Configuration
from dsml.ir.external import imported
from dsml.ir.model import (
    Attribute,
    Element,
    EnumValue,
    Finding,
    Ir,
    ListValue,
    Location,
    Multiplicity,
    StringValue,
)
from dsml.ir.writer import write_ir
from dsml.library import library_document
from dsml.validate.engine import Validator
from dsml.validate.rules import registry

ROOT = Path(__file__).resolve().parent.parent
MODELS = "tests/models/openapi"
PORTAL = f"{MODELS}/order-portal.sysml"
ORDER_API = ROOT / "tests/golden/fastapi/order-service/services/order-api/openapi.gen.json"
GOLDEN = ROOT / "tests/golden/ir/openapi.ir.json"
API = "OpenApiPortal::orderApi"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    with Engine() as started:
        yield started


def _convert(engine: Engine, file: str) -> Ir:
    parsed = engine.parse_texts(
        [library_document(), (file, (ROOT / file).read_text(encoding="utf-8"))]
    )
    assert [str(item) for item in parsed.diagnostics] == []
    return build_ir(parsed, [file], ROOT)


@pytest.fixture(scope="module")
def portal(engine: Engine) -> Ir:
    return _convert(engine, PORTAL)


def _of_kind(ir: Ir, kind: str) -> dict[str, Element]:
    return {item.identity: item for item in ir.elements if item.kind == kind}


# trace: PRD-CORE-055, PRD-DSML-058
def test_ir_has_the_operations_of_the_openapi_file(portal: Ir) -> None:
    document = json.loads(ORDER_API.read_text(encoding="utf-8"))
    expected = {
        f"{API}::{operation['operationId']}": (method, path)
        for path, item in document["paths"].items()
        for method, operation in item.items()
    }
    found = {
        identity: (
            next(a.value.literal for a in item.attributes if isinstance(a.value, EnumValue)),
            next(a.value.value for a in item.attributes if isinstance(a.value, StringValue)),
        )
        for identity, item in _of_kind(portal, "Operation").items()
    }
    assert found == expected
    assert all(item.owner == API for item in _of_kind(portal, "Operation").values())


# trace: PRD-CORE-055, PRD-DSML-058
def test_ir_has_the_entities_of_the_openapi_file(portal: Ir) -> None:
    # The schema Problem is only in the error responses, so it is not in the IR.
    document = json.loads(ORDER_API.read_text(encoding="utf-8"))
    names = sorted(name for name in document["components"]["schemas"] if name != "Problem")
    entities = _of_kind(portal, "Entity")
    assert sorted(entities) == [f"{API}::{name}" for name in names]
    assert all(item.owner == API for item in entities.values())
    fields = _of_kind(portal, "Field")
    for name in names:
        properties = document["components"]["schemas"][name]["properties"]
        owned = {
            item.name
            for item in (*fields.values(), *_of_kind(portal, "Relation").values())
            if item.owner == f"{API}::{name}"
        }
        assert owned == set(properties), name


# trace: PRD-CORE-055, PRD-DSML-023
def test_fields_have_the_scalar_types_and_multiplicities(portal: Ir) -> None:
    fields = _of_kind(portal, "Field")
    entity = f"{API}::CreateOrderInput"
    assert fields[f"{entity}::total"].types == ("DSML::Decimal",)
    assert fields[f"{entity}::total"].multiplicity == Multiplicity(1, 1)
    assert fields[f"{entity}::note"].types == ("ScalarValues::String",)
    assert fields[f"{entity}::note"].multiplicity == Multiplicity(0, 1)
    status = fields[f"{entity}::status"]
    assert status.types == ("ScalarValues::String",)
    assert status.attributes == (
        Attribute(
            "literals", ListValue(tuple(StringValue(x) for x in ("open", "shipped", "cancelled")))
        ),
    )
    assert fields[f"{API}::ReadOrderOutput::id"].types == ("DSML::Uuid",)
    items = _of_kind(portal, "Relation")[f"{API}::ListOrderPage::items"]
    assert items.types == (f"{API}::ListOrderOutput",)
    assert items.multiplicity == Multiplicity(0, None)


# trace: PRD-CORE-055, PRD-DSML-028
def test_operations_have_their_parameters(portal: Ir) -> None:
    parameters = _of_kind(portal, "Parameter")
    create = f"{API}::create_order_orders_post"
    body = parameters[f"{create}::body"]
    assert (body.direction, body.types) == ("in", (f"{API}::CreateOrderInput",))
    response = parameters[f"{create}::response"]
    assert (response.direction, response.types) == ("out", (f"{API}::CreateOrderOutput",))
    limit = parameters[f"{API}::list_order_orders_get::limit"]
    assert limit.types == ("ScalarValues::Integer",)
    assert limit.multiplicity == Multiplicity(0, 1)
    assert limit.attributes == (Attribute("in", StringValue("query")),)
    order = parameters[f"{API}::cancel_order_orders__orderId__cancel_post::orderId"]
    assert (order.types, order.multiplicity) == (("DSML::Uuid",), Multiplicity(1, 1))
    assert order.attributes == (Attribute("in", StringValue("path")),)


# trace: PRD-CORE-055, PRD-CORE-028
def test_ir_agrees_with_its_golden_file(portal: Ir) -> None:
    assert portal.findings == ()
    assert write_ir(portal) == GOLDEN.read_bytes(), (
        f"The IR of {PORTAL} is not the same as {GOLDEN.relative_to(ROOT)}. "
        "If the change is correct, run scripts/write_golden_ir.py."
    )


# trace: PRD-CORE-055, PRD-VAL-015
def test_model_rules_do_not_examine_the_imported_elements(portal: Ir) -> None:
    assert {item.identity for item in portal.elements} - imported(portal) == {
        "OpenApiPortal",
        "OpenApiPortal::orderPortal",
        API,
    }
    rules = {rule: registry()[rule] for rule in ("STR-006", "STR-007", "STR-008", "XLY-005")}
    assert Validator(Configuration(), rules).run(portal) == ()


# trace: PRD-CORE-055, PRD-VAL-016
def test_missing_file_gives_one_str_017_finding(engine: Engine) -> None:
    ir = _convert(engine, f"{MODELS}/missing-file.sysml")
    assert ir.findings == (
        Finding(
            "STR-017",
            "error",
            'The OpenAPI file "tests/models/openapi/no-such-file.json" of the external API '
            '"OpenApiMissing::orderApi" does not exist.',
            Location(f"{MODELS}/missing-file.sysml", 7, 9),
            "OpenApiMissing::orderApi",
        ),
    )
    assert imported(ir) == frozenset()


# trace: PRD-CORE-055, PRD-VAL-016
def test_item_outside_the_subset_gives_one_str_017_finding(engine: Engine) -> None:
    ir = _convert(engine, f"{MODELS}/outside-subset.sysml")
    assert ir.findings == (
        Finding(
            "STR-017",
            "error",
            'The OpenAPI file "tests/models/openapi/outside-subset.json" of the external API '
            '"OpenApiOutside::orderApi" contains an item that the toolchain cannot read at '
            '"/paths/~1orders~1{id}/get/parameters/1/in": '
            "A parameter must be in the path or in the query.",
            Location(f"{MODELS}/outside-subset.sysml", 8, 9),
            "OpenApiOutside::orderApi",
        ),
    )
    assert imported(ir) == frozenset()


# trace: PRD-VAL-008, PRD-VAL-016
def test_str_017_accepts_its_accept_model(run_rule: RunRule) -> None:
    assert run_rule("STR-017", "accept.sysml") == ()


# trace: PRD-VAL-008, PRD-VAL-016
def test_str_017_rejects_its_reject_model(run_rule: RunRule) -> None:
    findings = run_rule("STR-017", "reject.sysml")
    assert [(item.rule, item.severity, item.element) for item in findings] == [
        ("STR-017", "error", "StrReject::orderApi")
    ]


# trace: PRD-VAL-008, PRD-DSML-030, PRD-DSML-058
def test_xly_005_accepts_a_call_to_an_external_api(run_rule: RunRule) -> None:
    assert run_rule("XLY-005", "accept-external-api.sysml") == ()


# Tests of the subset with no OpenSysML service ------------------------------

_HERE = Location("model.sysml", 3, 5)


def _import(tmp_path: Path, document: Any) -> tuple[list[Element], list[Finding]]:
    (tmp_path / "api.json").write_text(json.dumps(document), encoding="utf-8")
    api = Element(
        identity="api",
        kind="ExternalApi",
        name="api",
        qualified_name="M::api",
        location=_HERE,
        attributes=(Attribute("openApiFile", StringValue("api.json"), _HERE),),
    )
    return import_apis([api], tmp_path)


def _document(
    schema: dict[str, Any] | None = None, operation: dict[str, Any] | None = None
) -> dict[str, Any]:
    thing = {"type": "object", "properties": {"id": {"type": "string"}}}
    response = {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/T"}}}}
    return {
        "openapi": "3.1.0",
        "info": {"title": "t", "version": "1"},
        "components": {"schemas": {"T": schema or thing}},
        "paths": {
            "/t": {"get": operation or {"operationId": "op", "responses": {"200": response}}}
        },
    }


# trace: PRD-CORE-055
def test_readable_forms_give_their_types(tmp_path: Path) -> None:
    schema = {
        "type": "object",
        "required": ["code", "tags", "next"],
        "properties": {
            "code": {"type": ["string", "null"], "format": "date-time"},
            "tags": {"type": "array", "items": {"type": "integer"}},
            "next": {"$ref": "#/components/schemas/T"},
            "flag": {"type": "boolean", "default": False},
        },
    }
    operation = {"operationId": "op", "responses": {"204": {"description": "No content."}}}
    elements, findings = _import(tmp_path, _document(schema))
    assert findings == []
    found = {item.name: (item.kind, item.types, item.multiplicity) for item in elements}
    assert found["code"] == ("Field", ("DSML::DateTime",), Multiplicity(0, 1))
    assert found["tags"] == ("Field", ("ScalarValues::Integer",), Multiplicity(0, None))
    assert found["next"] == ("Relation", ("api::T",), Multiplicity(1, 1))
    assert found["flag"] == ("Field", ("ScalarValues::Boolean",), Multiplicity(0, 1))
    elements, findings = _import(tmp_path, _document(operation=operation))
    assert findings == []
    assert [item.kind for item in elements] == ["Operation"]


@pytest.mark.parametrize(
    ("change", "pointer"),
    [
        ({"openapi": "3.0.3"}, "/openapi"),
        ({"webhooks": {}}, "/webhooks"),
        ({"components": {"responses": {}}}, "/components/responses"),
        ({"paths": {"/t": {"head": {}}}}, "/paths/~1t/head"),
        ({"paths": {"/t": {"get": {"responses": {"200": {}}}}}}, "/paths/~1t/get"),
        (
            {"paths": {"/t": {"get": {"operationId": "op", "responses": {"404": {}}}}}},
            "/paths/~1t/get/responses",
        ),
        (
            {
                "paths": {
                    "/t": {
                        "get": {
                            "operationId": "op",
                            "responses": {"200": {"content": {"text/plain": {}}}},
                        }
                    }
                }
            },
            "/paths/~1t/get/responses/200/content/text~1plain",
        ),
        (
            {"components": {"schemas": {"T": {"type": "object", "allOf": []}}}},
            "/components/schemas/T/allOf",
        ),
        (
            {"components": {"schemas": {"T": {"type": "array"}}}},
            "/components/schemas/T/type",
        ),
        (
            {"components": {"schemas": {"T": {"type": "object", "properties": {"x": {}}}}}},
            "/components/schemas/T/properties/x",
        ),
        (
            {
                "components": {
                    "schemas": {"T": {"type": "object", "properties": {"x": {"type": "object"}}}}
                }
            },
            "/components/schemas/T/properties/x",
        ),
        (
            {
                "components": {
                    "schemas": {
                        "T": {
                            "type": "object",
                            "properties": {
                                "x": {"anyOf": [{"type": "integer"}, {"type": "string"}]}
                            },
                        }
                    }
                }
            },
            "/components/schemas/T/properties/x/anyOf",
        ),
        (
            {
                "components": {
                    "schemas": {
                        "T": {
                            "type": "object",
                            "properties": {"x": {"$ref": "#/components/schemas/Missing"}},
                        }
                    }
                }
            },
            "/components/schemas/T/properties/x/$ref",
        ),
    ],
)
def test_item_outside_the_subset_gives_one_finding(
    tmp_path: Path, change: dict[str, Any], pointer: str
) -> None:
    document = _document()
    for key, value in change.items():
        if isinstance(value, dict) and isinstance(document.get(key), dict):
            document[key] = {**document[key], **value}
        else:
            document[key] = value
    elements, findings = _import(tmp_path, document)
    assert elements == []
    assert len(findings) == 1
    assert findings[0].rule == "STR-017"
    assert f'at "{pointer}":' in findings[0].message


# trace: PRD-CORE-033, PRD-VAL-016
@pytest.mark.parametrize("name", ["/tmp/api.json", "../api.json", ""])
def test_path_that_is_not_relative_gives_one_finding(tmp_path: Path, name: str) -> None:
    api = Element(
        identity="api",
        kind="ExternalApi",
        name="api",
        qualified_name="M::api",
        location=_HERE,
        attributes=(Attribute("openApiFile", StringValue(name), _HERE),),
    )
    elements, findings = import_apis([api], tmp_path)
    assert elements == []
    assert [(item.rule, item.location) for item in findings] == [("STR-017", _HERE)]


# trace: PRD-VAL-016
def test_file_that_is_not_json_gives_one_finding(tmp_path: Path) -> None:
    (tmp_path / "api.json").write_text("openapi: 3.1.0\n", encoding="utf-8")
    api = Element(
        identity="api",
        kind="ExternalApi",
        name="api",
        qualified_name="M::api",
        location=_HERE,
        attributes=(Attribute("openApiFile", StringValue("api.json"), _HERE),),
    )
    _, findings = import_apis([api], tmp_path)
    assert [item.message for item in findings] == [
        'The OpenAPI file "api.json" of the external API "api" is not a JSON file with UTF-8 '
        "encoding."
    ]
