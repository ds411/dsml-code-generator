"""Tests of the entities layer of the React generator (story #168).

The golden files in `tests/golden/react/order-portal/src/entities/` are the
entity slices of the order portal model. Write them again with
`uv run python scripts/write_golden_react.py`.

The file `tests/react/field-rules/order-portal.json` gives test values for
each field rule of the order portal. This module gives each value to the
Pydantic model of the golden FastAPI output. The Vitest file
`tests/react/field-rules/field-rules.test.ts` gives the same values to the
Zod schemas in the CI job "React golden project". Thus the Zod schemas and
the Pydantic models accept and refuse the same values (PRD-APP-211).
"""

import dataclasses
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import BaseModel, ValidationError

from dsml.config import Configuration, parse_configuration
from dsml.errors import ToolchainError
from dsml.generate.generators import collect
from dsml.generate.react import ReactGenerator
from dsml.generate.react_common import ReactContext
from dsml.generate.react_entities import (
    EntitySlice,
    called_applications,
    entities_files,
    entity_slices,
)
from dsml.generate.templates import TemplateEngine
from dsml.generate.trace import SymbolKind
from dsml.generate.typescript_symbols import typescript_symbols
from dsml.generate.writer import Kind, application_part
from dsml.ir.model import Attribute, Element, EnumValue, Ir, Link, Location

ROOT = Path(__file__).resolve().parent.parent
PORTAL_MODEL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
SHOP_MODEL = ROOT / "tests" / "models" / "fastapi" / "shop.sysml"
GOLDEN = ROOT / "tests" / "golden" / "react" / "order-portal"
ENTITIES = "src/entities/"
FIELD_RULES = ROOT / "tests" / "react" / "field-rules" / "order-portal.json"
API_FEATURES = (
    (ROOT / "tests" / "golden" / "fastapi" / "order-portal" / "services" / "order-api" / "app")
    / "features"
    / "order"
)
PYDANTIC_MODELS = {
    "createOrderInputSchema": ("create_order", "CreateOrderInput"),
    "orderSchema": ("read_order", "ReadOrderOutput"),
}
"""The Pydantic model of each Zod schema in the test values."""

CONFIGURATION = '[applications.orderPortal]\noutput = "."\n'
LOCATION = Location(file="model.sysml", line=1, column=1)


def configuration(text: str = CONFIGURATION) -> Configuration:
    return parse_configuration(f"schema = 1\n\n{text}", Path("dsml.toml"))


@pytest.fixture(scope="module")
def portal_ir() -> Ir:
    from dsml.adapter.convert import make_ir

    return make_ir([PORTAL_MODEL], ROOT)


@pytest.fixture(scope="module")
def shop_ir() -> Ir:
    """The shop model with a React application `shopPortal` that calls `shopApi`."""
    from dsml.adapter.convert import make_ir

    ir = make_ir([SHOP_MODEL], ROOT)
    api = next(item for item in ir.elements if item.name == "shopApi")
    portal = react_application("Shop::shopPortal")
    link = Link(type="calls", source=portal.identity, target=api.identity, location=LOCATION)
    return dataclasses.replace(ir, elements=(*ir.elements, portal), links=(*ir.links, link))


def react_application(identity: str) -> Element:
    name = identity.rpartition("::")[2]
    return Element(
        identity=identity,
        kind="Application",
        name=name,
        qualified_name=identity,
        location=LOCATION,
        attributes=(Attribute("target", EnumValue("DSML::Target", "react"), LOCATION),),
    )


def application(ir: Ir, name: str) -> Element:
    return next(item for item in ir.elements if item.kind == "Application" and item.name == name)


def context(ir: Ir, name: str) -> ReactContext:
    item = application(ir, name)
    return ReactContext(
        TemplateEngine(), ir, item, configuration(), "", application_part(item.name)
    )


def entity_files(files: dict[str, bytes]) -> dict[str, bytes]:
    return {path: content for path, content in files.items() if path.startswith(ENTITIES)}


def golden_files() -> dict[str, bytes]:
    return {
        path.relative_to(GOLDEN).as_posix(): path.read_bytes()
        for path in sorted(GOLDEN.rglob("*"))
        if path.is_file()
    }


def shop_entity(shop_ir: Ir, name: str) -> EntitySlice:
    found = entity_slices(shop_ir, application(shop_ir, "shopPortal"))
    return next(item for item in found if item.name == name)


def chains(entity: EntitySlice, mode: str) -> dict[str, str]:
    """Give the Zod schema of each field of an entity in a mode: output, create or update."""
    return {
        item.name: "".join(item.output_chain() if mode == "output" else item.input_chain(mode))
        for item in entity.fields
        if mode == "output" or not item.field.key
    }


def load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"golden_{path.parent.name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# trace: PRD-CORE-030, PRD-APP-210
def test_entity_files_of_the_order_portal_agree_with_the_golden_files(portal_ir: Ir) -> None:
    files = collect([ReactGenerator()], portal_ir, configuration(), None)
    output = entity_files({file.path: file.content for file in files})
    assert output == entity_files(golden_files()), (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_react.py and examine the differences."
    )
    assert sorted(output) == [
        "src/entities/order/api/order-queries.gen.ts",
        "src/entities/order/index.gen.ts",
        "src/entities/order/index.ts",
        "src/entities/order/model/order.gen.ts",
    ]


# trace: PRD-APP-204, PRD-CORE-044
def test_public_api_of_an_entity_slice(portal_ir: Ir) -> None:
    files = {file.path: file for file in entities_files(context(portal_ir, "orderPortal"))}
    assert files["src/entities/order/index.ts"].kind is Kind.CREATE_ONCE
    generated = files["src/entities/order/index.gen.ts"]
    assert generated.kind is Kind.GENERATED
    assert generated.content.decode().splitlines()[2:] == [
        'export * from "./api/order-queries.gen";',
        'export * from "./model/order.gen";',
    ]


# trace: PRD-APP-211, PRD-APP-112
@pytest.mark.parametrize(
    "case",
    json.loads(FIELD_RULES.read_text(encoding="utf-8"))["cases"],
    ids=lambda case: f"{case['schema']}-{case['rule']}-{case['valid']}",
)
def test_pydantic_models_accept_and_refuse_the_field_rule_values(case: dict[str, object]) -> None:
    folder, name = PYDANTIC_MODELS[str(case["schema"])]
    model = getattr(load_module(API_FEATURES / folder / "schemas_gen.py"), name)
    assert issubclass(model, BaseModel)
    try:
        model.model_validate(case["value"])
        accepted = True
    except ValidationError:
        accepted = False
    assert accepted is case["valid"]


# trace: PRD-APP-211
def test_field_rule_values_cover_each_field_rule_of_the_order_portal(portal_ir: Ir) -> None:
    cases = json.loads(FIELD_RULES.read_text(encoding="utf-8"))["cases"]
    found = {(case["rule"], case["valid"]) for case in cases}
    needed: set[str] = set()
    for entity in entity_slices(portal_ir, application(portal_ir, "orderPortal")):
        for item in entity.fields:
            rules = item.field.rules
            if item.field.key:
                continue
            names = [
                name
                for name, value in (
                    ("minLength", rules.min_length),
                    ("maxLength", rules.max_length),
                    ("minValue", rules.min_value),
                    ("maxValue", rules.max_value),
                    ("pattern", rules.pattern),
                )
                if value is not None
            ]
            if rules.kind == "Decimal":
                names += ["digits", "places", "decimal"]
            if rules.kind == "Enumeration":
                names.append("values")
            needed.update(f"{item.name} {name}" for name in names)
    assert needed == {
        "note maxLength",
        "status values",
        "total minValue",
        "total digits",
        "total places",
        "total decimal",
    }
    missing = sorted(
        f"{rule} ({valid})"
        for rule in needed
        for valid in (True, False)
        if (rule, valid) not in found
    )
    assert not missing, f"These field rules have no test value: {', '.join(missing)}."


# trace: PRD-APP-005, PRD-APP-112, PRD-APP-115, PRD-APP-211
def test_zod_schemas_of_the_shop_model(shop_ir: Ir) -> None:
    customer = shop_entity(shop_ir, "Customer")
    assert chains(customer, "create") == {
        "birth_date": "z.iso.date().nullable().optional()",
        "email": 'z.string().max(120).regex(new RegExp("^[a-z]+@[a-z]+[.]com$"))',
        "name": "z.string().min(2).max(80)",
        "vip": "z.boolean()",
    }
    assert chains(customer, "update") == {
        "birth_date": "z.iso.date().nullable().optional()",
        "email": 'z.string().max(120).regex(new RegExp("^[a-z]+@[a-z]+[.]com$")).optional()',
        "name": "z.string().min(2).max(80).optional()",
        "vip": "z.boolean().optional()",
    }
    product = shop_entity(shop_ir, "Product")
    assert chains(product, "create") == {
        "added_at": "z.iso.datetime({ offset: true, local: true }).nullable().optional()",
        "buyer_id": "z.int().nullable().optional()",
        "code": 'z.string().regex(new RegExp("^[A-Z]{3}-[0-9]{4}$"))',
        "kind": 'z.enum(["book", "music", "video"])',
        "note": "z.string().nullable().optional()",
        "price": "decimal({ whole: 8, places: 2, min: 0, max: 10000 })",
        "stock": "z.int().min(0).max(1000000)",
        "supplier_id": "z.guid()",
        "weight": "z.number().min(0.1).nullable().optional()",
    }
    assert chains(product, "output") == {
        "added_at": "z.iso.datetime({ offset: true, local: true }).nullable()",
        "buyer_id": "z.int().nullable()",
        "code": "z.string()",
        "id": "z.guid()",
        "kind": 'z.enum(["book", "music", "video"])',
        "note": "z.string().nullable()",
        "price": "z.string()",
        "stock": "z.int()",
        "supplier_id": "z.guid()",
        "weight": "z.number().nullable()",
    }


# trace: PRD-APP-210
def test_entity_slices_follow_the_crud_operations(shop_ir: Ir) -> None:
    found = {
        item.slice: (item.inputs, item.queries)
        for item in entity_slices(shop_ir, application(shop_ir, "shopPortal"))
    }
    assert found == {
        "customer": (["create", "update"], ["read", "list"]),
        "product": (["create", "update"], ["read", "list"]),
        "supplier": (["create"], ["read", "list"]),
    }
    text = shop_file(shop_ir, "src/entities/supplier/model/supplier.gen.ts")
    assert "updateSupplierInputSchema" not in text
    assert "function decimal(" not in text
    assert "function decimal(" in shop_file(shop_ir, "src/entities/product/model/product.gen.ts")


def shop_file(shop_ir: Ir, path: str) -> str:
    files = {file.path: file for file in entities_files(context(shop_ir, "shopPortal"))}
    return files[path].content.decode()


# trace: PRD-APP-224
def test_query_keys_have_the_form_entity_operation_parameters(shop_ir: Ir) -> None:
    text = shop_file(shop_ir, "src/entities/customer/api/customer-queries.gen.ts")
    assert 'export const customerQueryKey = ["customer"] as const;' in text
    assert 'return ["customer", "read", { id }] as const;' in text
    assert 'return ["customer", "list", { limit, offset }] as const;' in text
    assert "const limit = parameters.limit ?? 50;" in text
    # An integer key is a number in TypeScript and a text in the path.
    assert "export function readCustomerQueryOptions(id: number) {" in text
    assert "path: `/customers/${encodeURIComponent(String(id))}`," in text


# trace: PRD-TRACE-006
def test_symbols_of_the_entity_files(portal_ir: Ir) -> None:
    files = {file.path: file for file in entities_files(context(portal_ir, "orderPortal"))}
    model = files["src/entities/order/model/order.gen.ts"]
    elements = ("OrderPortal::Order", "OrderPortal::orderApi::orders")
    assert [(symbol.kind, symbol.name) for symbol in model.symbols] == [
        (SymbolKind.FUNCTION, "decimal"),
        (SymbolKind.CLASS, "orderSchema"),
        (SymbolKind.CLASS, "Order"),
        (SymbolKind.CLASS, "orderPageSchema"),
        (SymbolKind.CLASS, "OrderPage"),
        (SymbolKind.CLASS, "createOrderInputSchema"),
        (SymbolKind.CLASS, "CreateOrderInput"),
    ]
    assert all(symbol.elements == elements for symbol in model.symbols)
    lines = model.content.decode().split("\n")
    first = model.symbols[1]
    assert lines[first.first_line - 1] == "export const orderSchema = z.object({"
    assert lines[first.last_line - 1] == "});"
    queries = files["src/entities/order/api/order-queries.gen.ts"]
    assert [symbol.name for symbol in queries.symbols] == [
        "orderQueryKey",
        "readOrderQueryKey",
        "readOrderQueryOptions",
        "OrderListParameters",
        "listOrderQueryKey",
        "listOrderQueryOptions",
    ]
    assert not files["src/entities/order/index.ts"].symbols


# trace: PRD-TRACE-006
def test_typescript_symbols_stop_before_a_comment() -> None:
    text = (
        b"// a\nimport x from 'x';\n\n/** A. */\n"
        b"export function a() {\n  return 1;\n}\n\nconst b = 2;\n"
    )
    symbols = typescript_symbols(text, ("E",))
    assert [(item.name, item.first_line, item.last_line) for item in symbols] == [
        ("a", 5, 7),
        ("b", 9, 9),
    ]


# trace: PRD-APP-005
def test_an_application_with_no_called_application_has_no_entity_slices(shop_ir: Ir) -> None:
    alone = react_application("Shop::alonePortal")
    ir = dataclasses.replace(shop_ir, elements=(*shop_ir.elements, alone))
    assert called_applications(ir, alone) == []
    assert entity_slices(ir, alone) == []


def test_two_called_applications_with_one_entity_give_an_error(shop_ir: Ir) -> None:
    api = application(shop_ir, "shopApi")
    copy = dataclasses.replace(api, identity="Shop::shopApi2", name="shopApi2")
    copies = tuple(
        dataclasses.replace(item, owner="Shop::shopApi2", identity=f"{item.identity}2")
        for item in shop_ir.elements
        if item.owner == api.identity
    )
    portal = application(shop_ir, "shopPortal")
    link = Link(type="calls", source=portal.identity, target=copy.identity, location=LOCATION)
    ir = dataclasses.replace(
        shop_ir, elements=(*shop_ir.elements, copy, *copies), links=(*shop_ir.links, link)
    )
    with pytest.raises(ToolchainError, match="calls two applications"):
        entity_slices(ir, portal)
