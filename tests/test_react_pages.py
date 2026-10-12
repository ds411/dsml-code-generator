"""Tests of the pages layer and of the app layer of the React generator (story #174).

The golden files in `tests/golden/react/order-portal/src/pages/` and
`tests/golden/react/order-portal/src/app/` are the pages, the routes, the
navigation and the providers of the order portal model. Write them again
with `uv run python scripts/write_golden_react.py`.

The Vitest file `tests/react/app/app.test.tsx` renders the application of
the golden project in the CI job "React golden project". It examines the
start of the login with no session, the "not permitted" page, the route
loaders and the navigation.
"""

import dataclasses
from pathlib import Path

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Configuration, parse_configuration
from dsml.errors import ToolchainError
from dsml.generate.generators import collect
from dsml.generate.react import ReactGenerator
from dsml.generate.react_app import app_files
from dsml.generate.react_common import ReactContext
from dsml.generate.react_pages import page_slices, pages_files
from dsml.generate.templates import TemplateEngine
from dsml.generate.trace import SymbolKind
from dsml.generate.writer import Kind, application_part
from dsml.ir.model import (
    Attribute,
    BooleanValue,
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
LAYER_FOLDERS = ("src/app/", "src/pages/")
CONFIGURATION = '[applications.orderPortal]\noutput = "."\n'
LOCATION = Location(file="model.sysml", line=1, column=1)
PORTAL = "Shop::shopPortal"


def configuration() -> Configuration:
    return parse_configuration(f"schema = 1\n\n{CONFIGURATION}", Path("dsml.toml"))


def roles(*names: str) -> Attribute:
    values = tuple(EnumValue("Shop::Roles", name) for name in names)
    return Attribute("allowedRoles", ListValue(values), LOCATION)


def view(name: str, kind: str, target: str, *attributes: Attribute) -> Element:
    reference = "operation" if kind == "form" else "entity"
    return Element(
        identity=f"{PORTAL}::{name}",
        kind="View",
        name=name,
        qualified_name=f"{PORTAL}::{name}",
        location=LOCATION,
        owner=PORTAL,
        attributes=(
            Attribute("kind", EnumValue("DSML::ViewKind", kind), LOCATION),
            Attribute(reference, ReferenceValue(target), LOCATION),
            *attributes,
        ),
    )


def with_portal(ir: Ir, *views: Element, navigation: tuple[str, ...] = ()) -> Ir:
    """Add a React application `shopPortal` with the views. It calls `shopApi`."""
    api = next(item for item in ir.elements if item.name == "shopApi")
    items = tuple(ReferenceValue(f"{PORTAL}::{name}") for name in navigation)
    portal = Element(
        identity=PORTAL,
        kind="Application",
        name="shopPortal",
        qualified_name=PORTAL,
        location=LOCATION,
        attributes=(
            Attribute("target", EnumValue("DSML::Target", "react"), LOCATION),
            Attribute("navigation", ListValue(items), LOCATION),
        ),
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
    """The shop model with a React application that has a view of each kind."""
    return with_portal(
        shop_base,
        view("customerList", "list", "Shop::Customer", roles("clerk", "admin")),
        view("customerDetail", "detail", "Shop::Customer", roles("admin")),
        view("supplierList", "list", "Shop::Supplier", roles("clerk")),
        view(
            "restockForm",
            "form",
            "Shop::RestockProduct",
            Attribute("public", BooleanValue(True), LOCATION),
        ),
        navigation=("customerList", "restockForm", "supplierList"),
    )


def application(ir: Ir, name: str) -> Element:
    return next(item for item in ir.elements if item.kind == "Application" and item.name == name)


def context(ir: Ir, name: str) -> ReactContext:
    item = application(ir, name)
    return ReactContext(
        TemplateEngine(), ir, item, configuration(), "", application_part(item.name)
    )


def layer_files(files: dict[str, bytes]) -> dict[str, bytes]:
    return {path: content for path, content in files.items() if path.startswith(LAYER_FOLDERS)}


def golden_files() -> dict[str, bytes]:
    return {
        path.relative_to(GOLDEN).as_posix(): path.read_bytes()
        for path in sorted(GOLDEN.rglob("*"))
        if path.is_file()
    }


def shop_text(ir: Ir, path: str) -> str:
    output = context(ir, "shopPortal")
    files = {file.path: file for file in (*pages_files(output), *app_files(output))}
    return files[path].content.decode()


# trace: PRD-CORE-030, PRD-APP-210
def test_page_and_app_files_of_the_order_portal_agree_with_the_golden_files(
    portal_ir: Ir,
) -> None:
    files = collect([ReactGenerator()], portal_ir, configuration(), None)
    output = layer_files({file.path: file.content for file in files})
    assert output == layer_files(golden_files()), (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_react.py and examine the differences."
    )
    assert sorted(output) == [
        "src/app/layout/app-layout.gen.tsx",
        "src/app/layout/navigation.gen.tsx",
        "src/app/layout/status-pages.gen.tsx",
        "src/app/providers/app-providers.gen.tsx",
        "src/app/providers/query-client.gen.ts",
        "src/app/providers/session.gen.ts",
        "src/app/router/access.gen.ts",
        "src/app/router/router.gen.ts",
        "src/app/router/routes.gen.tsx",
        "src/app/router/views.gen.ts",
        "src/app/styles/index.css",
        "src/pages/cancel-order-form/index.gen.ts",
        "src/pages/cancel-order-form/index.ts",
        "src/pages/cancel-order-form/ui/cancel-order-form-page.gen.tsx",
        "src/pages/order-detail/index.gen.ts",
        "src/pages/order-detail/index.ts",
        "src/pages/order-detail/ui/order-detail-page.gen.tsx",
        "src/pages/order-list/index.gen.ts",
        "src/pages/order-list/index.ts",
        "src/pages/order-list/ui/order-list-page.gen.tsx",
        "src/pages/place-order-form/index.gen.ts",
        "src/pages/place-order-form/index.ts",
        "src/pages/place-order-form/ui/place-order-form-page.gen.tsx",
    ]


# trace: PRD-APP-204, PRD-CORE-044
def test_public_api_of_a_page_slice_and_the_create_once_styles(portal_ir: Ir) -> None:
    output = context(portal_ir, "orderPortal")
    files = {file.path: file for file in (*pages_files(output), *app_files(output))}
    assert files["src/pages/order-list/index.ts"].kind is Kind.CREATE_ONCE
    assert files["src/app/styles/index.css"].kind is Kind.CREATE_ONCE
    generated = files["src/pages/order-list/index.gen.ts"]
    assert generated.kind is Kind.GENERATED
    assert generated.content.decode().splitlines() == [
        "// Generated by dsml 0. Do not edit.",
        "// Elements: OrderPortal::Order, OrderPortal::orderApi::orders, "
        "OrderPortal::orderPortal::orderList",
        'export * from "./ui/order-list-page.gen";',
    ]
    # Each other file of the app layer is a generated file with a trace header.
    for path, file in files.items():
        if path.startswith("src/app/") and not path.endswith(".css"):
            assert file.kind is Kind.GENERATED, path
            assert file.content.startswith(b"// Generated by dsml"), path


# trace: PRD-APP-206, PRD-APP-210, PRD-APP-221, PRD-DSML-033
def test_each_view_gives_one_page_with_one_route_path(shop_ir: Ir) -> None:
    found = {
        item.slice: (item.kind, item.ui_module, item.component, item.path, item.roles, item.public)
        for item in page_slices(shop_ir, application(shop_ir, "shopPortal"))
    }
    assert found == {
        "customer-detail": (
            "detail",
            "ui/customer-detail-page.gen",
            "CustomerDetailPage",
            "/customers/$id",
            ("admin",),
            False,
        ),
        "customer-list": (
            "list",
            "ui/customer-list-page.gen",
            "CustomerListPage",
            "/customers",
            ("admin", "clerk"),
            False,
        ),
        "restock-form": (
            "form",
            "ui/restock-form-page.gen",
            "RestockFormPage",
            "/restock-product",
            (),
            True,
        ),
        "supplier-list": (
            "list",
            "ui/supplier-list-page.gen",
            "SupplierListPage",
            "/suppliers",
            ("clerk",),
            False,
        ),
    }


# trace: PRD-APP-210
def test_list_page_has_the_detail_link_and_the_delete_button(shop_ir: Ir) -> None:
    text = shop_text(shop_ir, "src/pages/customer-list/ui/customer-list-page.gen.tsx")
    assert 'import { DeleteCustomerButton } from "@/features/delete-customer";' in text
    assert 'import { CustomerTable } from "@/widgets/customer-list";' in text
    assert '              to="/customers/$id"\n' in text
    # The key of Customer is an integer. A path parameter is a text.
    assert "              params={{ id: String(item.id) }}\n" in text
    assert "            <DeleteCustomerButton id={item.id} />\n" in text
    # Supplier has no detail view and no delete operation, thus no actions.
    supplier = shop_text(shop_ir, "src/pages/supplier-list/ui/supplier-list-page.gen.tsx")
    assert "      <SupplierTable />\n" in supplier
    assert "@tanstack/react-router" not in supplier
    assert "DESCRIPTION" not in supplier


# trace: PRD-APP-210
def test_detail_page_and_form_page(shop_ir: Ir) -> None:
    detail = shop_text(shop_ir, "src/pages/customer-detail/ui/customer-detail-page.gen.tsx")
    assert "  id: number;" in detail
    assert "      <CustomerDetails id={id} />\n" in detail
    form = shop_text(shop_ir, "src/pages/restock-form/ui/restock-form-page.gen.tsx")
    assert 'import { RestockProductForm } from "@/features/restock-product";' in form
    assert "      <RestockProductForm\n" in form
    assert '{complete ? "The operation is complete." : ""}' in form


# trace: PRD-APP-220, PRD-APP-221, PRD-APP-222, PRD-APP-223
def test_routes_check_the_view_and_load_the_data(shop_ir: Ir) -> None:
    text = shop_text(shop_ir, "src/app/router/routes.gen.tsx")
    # Code-based routing: no file-based routing plugin (PRD-APP-220).
    assert "createFileRoute" not in text
    assert "export const rootRoute = createRootRouteWithContext<RouterContext>()({" in text
    assert "  beforeLoad: async () => ({ session: await currentSession() }),\n" in text
    assert '  path: "/auth/callback",\n' in text
    assert '  path: "/customers/$id",\n' in text
    assert "  beforeLoad: requireView(VIEWS.customerDetail),\n" in text
    assert (
        "  loader: ({ context, params }) =>\n"
        "    context.queryClient.ensureQueryData(\n"
        "      readCustomerQueryOptions(Number(params.id)),\n"
        "    ),\n"
    ) in text
    assert (
        "  loader: ({ context }) =>\n"
        "    context.queryClient.ensureQueryData(listCustomerQueryOptions()),\n"
    ) in text
    assert "  return <CustomerDetailPage id={Number(id)} />;\n" in text
    # A form route has no loader.
    form = text.split("const restockFormRoute = createRoute({", 1)[1].split("});", 1)[0]
    assert "loader" not in form
    assert "  beforeLoad: requireView(VIEWS.restockForm),\n" in form
    assert "export const routeTree = rootRoute.addChildren([\n  homeRoute,\n" in text


# trace: PRD-APP-009, PRD-APP-222, PRD-DSML-032, PRD-DSML-033
def test_views_give_the_roles_and_the_navigation(shop_ir: Ir) -> None:
    text = shop_text(shop_ir, "src/app/router/views.gen.ts")
    assert (
        "  customerDetail: {\n"
        '    path: "/customers/$id",\n'
        '    title: "Customer detail",\n'
        "    public: false,\n"
        '    roles: ["admin"],\n'
        "  },\n"
    ) in text
    assert "    public: true,\n    roles: [],\n" in text
    # The navigation keeps the order of the model.
    assert (
        "export const NAVIGATION = [\n"
        "  VIEWS.customerList,\n"
        "  VIEWS.restockForm,\n"
        "  VIEWS.supplierList,\n"
        "] as const;\n"
    ) in text
    navigation = shop_text(shop_ir, "src/app/layout/navigation.gen.tsx")
    assert "NAVIGATION.filter((view) => isPermitted(session, view))" in navigation


def test_application_with_no_views_has_the_home_route_only(shop_base: Ir) -> None:
    ir = with_portal(shop_base)
    assert pages_files(context(ir, "shopPortal")) == []
    routes = shop_text(ir, "src/app/router/routes.gen.tsx")
    assert "export const routeTree = rootRoute.addChildren([homeRoute, callbackRoute]);" in routes
    assert "requireView" not in routes
    assert "eslint-disable" not in routes
    views = shop_text(ir, "src/app/router/views.gen.ts")
    assert "export const NAVIGATION = [] as const;" in views


# trace: PRD-APP-203
def test_pages_import_only_from_lower_layers(portal_ir: Ir) -> None:
    for file in pages_files(context(portal_ir, "orderPortal")):
        for line in file.content.decode().splitlines():
            if " from " in line and "@/" in line:
                source = line.rsplit(" from ", 1)[1].strip('";')
                assert source.startswith(("@/widgets/", "@/features/")), line


# trace: PRD-APP-017, PRD-TRACE-006
def test_page_and_app_files_have_trace_symbols(portal_ir: Ir) -> None:
    output = context(portal_ir, "orderPortal")
    files = {file.path: file for file in (*pages_files(output), *app_files(output))}
    page = {
        (item.name, item.kind)
        for item in files["src/pages/order-list/ui/order-list-page.gen.tsx"].symbols
    }
    assert ("OrderListPage", SymbolKind.FUNCTION) in page
    routes = {(item.name, item.kind) for item in files["src/app/router/routes.gen.tsx"].symbols}
    assert ("routeTree", SymbolKind.CLASS) in routes
    navigation = files["src/app/layout/navigation.gen.tsx"]
    assert ("Navigation", SymbolKind.FUNCTION) in {
        (item.name, item.kind) for item in navigation.symbols
    }
    assert navigation.content.decode().splitlines()[1] == (
        "// Elements: OrderPortal::orderPortal, OrderPortal::orderPortal::orderList, "
        "OrderPortal::orderPortal::placeOrderForm"
    )


def test_form_view_of_an_operation_with_no_change_gives_an_error(shop_base: Ir) -> None:
    ir = with_portal(shop_base, view("search", "form", "Shop::FindProducts"))
    with pytest.raises(ToolchainError, match="no called application exposes this operation"):
        pages_files(context(ir, "shopPortal"))


def test_two_views_with_one_route_path_give_an_error(shop_base: Ir) -> None:
    ir = with_portal(
        shop_base,
        view("customerList", "list", "Shop::Customer"),
        view("customers", "list", "Shop::Customer"),
    )
    with pytest.raises(ToolchainError, match='have the same route path "/customers"'):
        pages_files(context(ir, "shopPortal"))


def test_detail_view_in_the_navigation_gives_an_error(shop_base: Ir) -> None:
    ir = with_portal(
        shop_base,
        view("customerDetail", "detail", "Shop::Customer"),
        navigation=("customerDetail",),
    )
    with pytest.raises(ToolchainError, match="contains the detail view customerDetail"):
        app_files(context(ir, "shopPortal"))
