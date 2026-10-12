"""Tests of the widgets layer of the React generator (story #173).

The golden files in `tests/golden/react/order-portal/src/widgets/` are the
widget slices of the order portal model. Write them again with
`uv run python scripts/write_golden_react.py`.

The Vitest file `tests/react/widgets/widgets.test.tsx` renders the widgets
of the golden project in the CI job "React golden project". It examines the
column headers, the change to the next page, the keyboard access and the
problem details errors.
"""

import dataclasses
from pathlib import Path

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Configuration, parse_configuration
from dsml.errors import ToolchainError
from dsml.generate.generators import collect
from dsml.generate.react import ReactGenerator
from dsml.generate.react_common import ReactContext
from dsml.generate.react_widgets import widget_slices, widgets_files
from dsml.generate.templates import TemplateEngine
from dsml.generate.trace import SymbolKind
from dsml.generate.writer import Kind, application_part
from dsml.ir.model import (
    Attribute,
    Element,
    EnumValue,
    Ir,
    Link,
    ListValue,
    Location,
    ReferenceValue,
)

ROOT = Path(__file__).resolve().parent.parent
PORTAL_MODEL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
SHOP_MODEL = ROOT / "tests" / "models" / "fastapi" / "shop.sysml"
GOLDEN = ROOT / "tests" / "golden" / "react" / "order-portal"
WIDGETS = "src/widgets/"
CONFIGURATION = '[applications.orderPortal]\noutput = "."\n'
LOCATION = Location(file="model.sysml", line=1, column=1)
PORTAL = "Shop::shopPortal"


def configuration() -> Configuration:
    return parse_configuration(f"schema = 1\n\n{CONFIGURATION}", Path("dsml.toml"))


def view(name: str, kind: str, entity: str) -> Element:
    return Element(
        identity=f"{PORTAL}::{name}",
        kind="View",
        name=name,
        qualified_name=f"{PORTAL}::{name}",
        location=LOCATION,
        owner=PORTAL,
        attributes=(
            Attribute("kind", EnumValue("DSML::ViewKind", kind), LOCATION),
            Attribute("entity", ReferenceValue(entity), LOCATION),
        ),
    )


def with_portal(ir: Ir, *views: Element) -> Ir:
    """Add a React application `shopPortal` with the views. It calls `shopApi`."""
    api = next(item for item in ir.elements if item.name == "shopApi")
    portal = Element(
        identity=PORTAL,
        kind="Application",
        name="shopPortal",
        qualified_name=PORTAL,
        location=LOCATION,
        attributes=(Attribute("target", EnumValue("DSML::Target", "react"), LOCATION),),
    )
    link = Link(type="calls", source=portal.identity, target=api.identity, location=LOCATION)
    return dataclasses.replace(ir, elements=(*ir.elements, portal, *views), links=(*ir.links, link))


@pytest.fixture(scope="module")
def portal_ir() -> Ir:
    return make_ir([PORTAL_MODEL], ROOT)


@pytest.fixture(scope="module")
def shop_base() -> Ir:
    return make_ir([SHOP_MODEL], ROOT)


@pytest.fixture(scope="module")
def shop_ir(shop_base: Ir) -> Ir:
    """The shop model with a React application that has a list view and a detail view."""
    return with_portal(
        shop_base,
        view("customerList", "list", "Shop::Customer"),
        view("customers", "list", "Shop::Customer"),
        view("customerDetail", "detail", "Shop::Customer"),
        view("supplierDetail", "detail", "Shop::Supplier"),
    )


def application(ir: Ir, name: str) -> Element:
    return next(item for item in ir.elements if item.kind == "Application" and item.name == name)


def context(ir: Ir, name: str) -> ReactContext:
    item = application(ir, name)
    return ReactContext(
        TemplateEngine(), ir, item, configuration(), "", application_part(item.name)
    )


def widget_files(files: dict[str, bytes]) -> dict[str, bytes]:
    return {path: content for path, content in files.items() if path.startswith(WIDGETS)}


def golden_files() -> dict[str, bytes]:
    return {
        path.relative_to(GOLDEN).as_posix(): path.read_bytes()
        for path in sorted(GOLDEN.rglob("*"))
        if path.is_file()
    }


def shop_text(ir: Ir, path: str) -> str:
    files = {file.path: file for file in widgets_files(context(ir, "shopPortal"))}
    return files[path].content.decode()


# trace: PRD-CORE-030, PRD-APP-210
def test_widget_files_of_the_order_portal_agree_with_the_golden_files(portal_ir: Ir) -> None:
    files = collect([ReactGenerator()], portal_ir, configuration(), None)
    output = widget_files({file.path: file.content for file in files})
    assert output == widget_files(golden_files()), (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_react.py and examine the differences."
    )
    assert sorted(output) == [
        "src/widgets/order-details/index.gen.ts",
        "src/widgets/order-details/index.ts",
        "src/widgets/order-details/ui/order-details.gen.tsx",
        "src/widgets/order-list/index.gen.ts",
        "src/widgets/order-list/index.ts",
        "src/widgets/order-list/ui/order-table.gen.tsx",
    ]


# trace: PRD-APP-204, PRD-CORE-044
def test_public_api_of_a_widget_slice(portal_ir: Ir) -> None:
    files = {file.path: file for file in widgets_files(context(portal_ir, "orderPortal"))}
    assert files["src/widgets/order-list/index.ts"].kind is Kind.CREATE_ONCE
    generated = files["src/widgets/order-list/index.gen.ts"]
    assert generated.kind is Kind.GENERATED
    assert generated.content.decode().splitlines() == [
        "// Generated by dsml 0. Do not edit.",
        "// Elements: OrderPortal::Order, OrderPortal::orderApi::orders, "
        "OrderPortal::orderPortal::orderList",
        'export * from "./ui/order-table.gen";',
    ]


# trace: PRD-APP-206, PRD-APP-210
def test_each_entity_of_a_list_or_detail_view_gives_one_slice(shop_ir: Ir) -> None:
    found = {
        item.slice: (item.kind, item.ui_module, item.component, item.views)
        for item in widget_slices(shop_ir, application(shop_ir, "shopPortal"))
    }
    # Two list views of one entity give one slice.
    assert found == {
        "customer-details": (
            "detail",
            "ui/customer-details.gen",
            "CustomerDetails",
            ("Shop::shopPortal::customerDetail",),
        ),
        "customer-list": (
            "list",
            "ui/customer-table.gen",
            "CustomerTable",
            ("Shop::shopPortal::customerList", "Shop::shopPortal::customers"),
        ),
        "supplier-details": (
            "detail",
            "ui/supplier-details.gen",
            "SupplierDetails",
            ("Shop::shopPortal::supplierDetail",),
        ),
    }


# trace: PRD-APP-114, PRD-APP-210, PRD-APP-228
def test_table_has_column_headers_and_paging(shop_ir: Ir) -> None:
    text = shop_text(shop_ir, "src/widgets/customer-list/ui/customer-table.gen.tsx")
    headers = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith('<TableHead scope="col">')
    ]
    assert headers == [
        '<TableHead scope="col">Id</TableHead>',
        '<TableHead scope="col">Birth date</TableHead>',
        '<TableHead scope="col">Email</TableHead>',
        '<TableHead scope="col">Name</TableHead>',
        '<TableHead scope="col">Vip</TableHead>',
        '<TableHead scope="col">Actions</TableHead>',
    ]
    assert "export function CustomerTable({ pageSize = 50, actions }: CustomerTableProps) {" in (
        text
    )
    assert "    ...listCustomerQueryOptions({ limit: pageSize, offset }),\n" in text
    assert "    placeholderData: keepPreviousData,\n" in text
    assert "setOffset(offset + pageSize);" in text
    assert "setOffset(Math.max(0, offset - pageSize));" in text
    # A Boolean value gives a text, and a null value gives an empty text.
    assert "<TableCell>{yesNo(item.vip)}</TableCell>" in text
    assert '<TableCell>{item.birth_date ?? ""}</TableCell>' in text
    assert "<TableRow key={item.id}>" in text
    assert "<TableCell colSpan={actions === undefined ? 5 : 6}>" in text
    # The paging controls are native buttons (PRD-APP-228).
    assert text.count('<Button\n            type="button"') == 2


# trace: PRD-APP-210
def test_details_show_each_field_of_the_entity(shop_ir: Ir) -> None:
    text = shop_text(shop_ir, "src/widgets/customer-details/ui/customer-details.gen.tsx")
    assert "export function CustomerDetails({ id }: CustomerDetailsProps) {" in text
    assert "  id: number;" in text
    assert "  const query = useQuery(readCustomerQueryOptions(id));" in text
    assert '<dt className="font-medium">Birth date</dt>' in text
    assert "<dd>{yesNo(item.vip)}</dd>" in text
    supplier = shop_text(shop_ir, "src/widgets/supplier-details/ui/supplier-details.gen.tsx")
    assert "yesNo" not in supplier
    assert "  id: string;" in supplier


# trace: PRD-APP-203
def test_widgets_import_only_from_lower_layers(portal_ir: Ir) -> None:
    for file in widgets_files(context(portal_ir, "orderPortal")):
        for line in file.content.decode().splitlines():
            if " from " in line and "@/" in line:
                source = line.rsplit(" from ", 1)[1].strip('";')
                assert source in ("@/entities/order", "@/shared/api", "@/shared/ui"), line


# trace: PRD-APP-017, PRD-TRACE-006
def test_widget_files_have_trace_symbols(portal_ir: Ir) -> None:
    files = {file.path: file for file in widgets_files(context(portal_ir, "orderPortal"))}
    symbols = {
        (item.name, item.kind)
        for item in files["src/widgets/order-list/ui/order-table.gen.tsx"].symbols
    }
    assert ("OrderTable", SymbolKind.FUNCTION) in symbols
    assert ("OrderTableProps", SymbolKind.CLASS) in symbols


def test_long_names_get_the_prettier_line_breaks(shop_base: Ir) -> None:
    ir = with_portal(
        shop_base,
        view("customerDetail", "detail", "Shop::Customer"),
        view("customerList", "list", "Shop::Customer"),
    )
    elements = tuple(
        dataclasses.replace(item, name="CustomerLoyaltyProgramMembershipRecord")
        if item.identity == "Shop::Customer"
        else item
        for item in ir.elements
    )
    ir = dataclasses.replace(ir, elements=elements)
    folder = "src/widgets/customer-loyalty-program-membership-record"
    table = shop_text(
        ir, f"{folder}-list/ui/customer-loyalty-program-membership-record-table.gen.tsx"
    )
    assert "export function CustomerLoyaltyProgramMembershipRecordTable({\n" in table
    assert "    ...listCustomerLoyaltyProgramMembershipRecordQueryOptions({\n" in table
    details = shop_text(
        ir, f"{folder}-details/ui/customer-loyalty-program-membership-record-details.gen.tsx"
    )
    assert "  const query = useQuery(\n" in details
    # Prettier keeps an import of one name on one line.
    assert "import { readCustomerLoyaltyProgramMembershipRecordQueryOptions } from" in details


def test_view_of_an_entity_with_no_slice_gives_an_error(shop_base: Ir) -> None:
    ir = with_portal(shop_base, view("orphans", "list", "Shop::Missing"))
    with pytest.raises(ToolchainError, match="No application that shopPortal calls exposes"):
        widgets_files(context(ir, "shopPortal"))


def _without_list(value: object) -> bool:
    """Tell if an item of `crud` or `crudDefaults` is not the operation list."""
    if isinstance(value, ListValue):
        value = value.items[0]
    return not (isinstance(value, EnumValue) and value.literal == "list")


def test_view_with_no_operation_of_the_widget_gives_an_error(shop_base: Ir) -> None:
    exposed = next(item for item in shop_base.elements if item.name == "suppliers")
    attributes = tuple(
        dataclasses.replace(
            attribute,
            value=ListValue(tuple(filter(_without_list, attribute.value.items))),
        )
        if isinstance(attribute.value, ListValue)
        else attribute
        for attribute in exposed.attributes
    )
    elements = tuple(
        dataclasses.replace(item, attributes=attributes) if item is exposed else item
        for item in shop_base.elements
    )
    ir = with_portal(
        dataclasses.replace(shop_base, elements=elements),
        view("supplierList", "list", "Shop::Supplier"),
    )
    with pytest.raises(ToolchainError, match="needs the operation list of the entity Supplier"):
        widgets_files(context(ir, "shopPortal"))
