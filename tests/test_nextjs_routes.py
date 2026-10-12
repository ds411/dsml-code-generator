"""Tests of the route handlers and server functions of the Next.js generator (story #186).

The golden files in `tests/golden/nextjs/order-web/` hold the route files of
the order web: `src/_app/api-routes/`, `app/api/`, `src/shared/http/` and
the server files of `src/features/`. Write them again with
`uv run python scripts/write_golden_nextjs.py`.

The Vitest tests in `tests/nextjs/routes/` send HTTP requests to the route
handlers of the golden project with a PostgreSQL database. The CI job
"Next.js golden project" runs them.
"""

import re
from dataclasses import replace
from pathlib import Path

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import parse_configuration
from dsml.errors import ToolchainError
from dsml.generate.generators import collect
from dsml.generate.nextjs import NextjsGenerator
from dsml.generate.nextjs_routes import Operation, check_names, path_slugs
from dsml.generate.writer import Kind, OutputFile, apply_plan, make_plan, read_manifest
from dsml.ir.model import Ir

ROOT = Path(__file__).resolve().parent.parent
WEB_MODEL = ROOT / "docs" / "model" / "examples" / "order-web" / "order-web.sysml"
SHOP_MODEL = ROOT / "tests" / "models" / "fastapi" / "shop.sysml"
GOLDEN = ROOT / "tests" / "golden" / "nextjs" / "order-web"
CONFIGURATION = 'schema = 1\n\n[applications.orderWeb]\noutput = "order-web"\n'
STUB = "src/features/cancel-order/api/cancel-order.server.ts"

OPERATIONS = {
    "cancel-order": ("POST", "app/api/orders/[id]/cancel/route.ts"),
    "create-order": ("POST", "app/api/orders/route.ts"),
    "delete-order": ("DELETE", "app/api/orders/[id]/route.ts"),
    "list-order": ("GET", "app/api/orders/route.ts"),
    "read-order": ("GET", "app/api/orders/[id]/route.ts"),
    "update-order": ("PATCH", "app/api/orders/[id]/route.ts"),
}
"""The operations of the order web: the method and the route file of each route handler."""


def route_file(path: str) -> bool:
    """Tell if a path in the output folder is a file of the route handler part."""
    if path == "src/_app/api-routes/healthz.gen.ts":
        return False
    if path.startswith(("src/_app/api-routes/", "app/api/", "src/shared/http/")):
        return True
    return path.startswith("src/features/") and ".server" in path


@pytest.fixture(scope="module")
def web_ir() -> Ir:
    return make_ir([WEB_MODEL], ROOT)


@pytest.fixture(scope="module")
def web_files(web_ir: Ir, tmp_path_factory: pytest.TempPathFactory) -> dict[str, OutputFile]:
    """Give the output of the Next.js generator for the order web, by the path in its folder."""
    folder = tmp_path_factory.mktemp("order-web")
    configuration = parse_configuration(CONFIGURATION, folder / "dsml.toml")
    files = collect([NextjsGenerator()], web_ir, configuration, None)
    return {file.path.removeprefix("order-web/"): file for file in files}


@pytest.fixture(scope="module")
def shop_files(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Give the output files of the shop model with the target `nextjs`.

    The model has each field type, custom operations with the method GET,
    query parameters, a request body, an entity in the path and no output.
    The customers have an integer key, thus they have no create operation.
    """
    folder = tmp_path_factory.mktemp("shop")
    text = SHOP_MODEL.read_text(encoding="utf-8").replace("Target::fastapi", "Target::nextjs")
    text = text.replace(
        "#Exposed part customers : Customer [*] {\n"
        "            :>> crud = (CrudKind::create, CrudKind::read,",
        "#Exposed part customers : Customer [*] {\n            :>> crud = (CrudKind::read,",
    )
    model = folder / "shop.sysml"
    model.write_text(text, encoding="utf-8")
    configuration = parse_configuration(
        'schema = 1\n\n[applications.shopApi]\noutput = "shop"\n', folder / "dsml.toml"
    )
    files = collect([NextjsGenerator()], make_ir([model], folder), configuration, None)
    return {file.path.removeprefix("shop/"): file.content.decode("utf-8") for file in files}


# trace: PRD-APP-310, PRD-APP-313, PRD-CORE-030
def test_route_files_of_the_order_web_agree_with_the_golden_files(
    web_files: dict[str, OutputFile],
) -> None:
    output = {path: file.content for path, file in web_files.items() if route_file(path)}
    golden = {
        path.relative_to(GOLDEN).as_posix(): path.read_bytes()
        for path in sorted(GOLDEN.rglob("*"))
        if path.is_file() and route_file(path.relative_to(GOLDEN).as_posix())
    }
    assert output == golden, (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_nextjs.py and examine the differences."
    )


# trace: PRD-APP-302, PRD-APP-310, PRD-APP-311
def test_each_operation_has_a_route_handler_and_a_route_file(
    web_files: dict[str, OutputFile],
) -> None:
    handlers = sorted(
        path.removeprefix("src/_app/api-routes/").removesuffix(".gen.ts")
        for path in web_files
        if path.startswith("src/_app/api-routes/")
    )
    assert handlers == sorted([*OPERATIONS, "healthz"])
    for name, (method, route) in OPERATIONS.items():
        text = web_files[route].content.decode("utf-8")
        assert f'export {{ {method} }} from "@/_app/api-routes/{name}.gen";' in text
        handler = web_files[f"src/_app/api-routes/{name}.gen.ts"].content.decode("utf-8")
        assert f"export const {method} = routeHandler(ACCESS, handle);" in handler
        assert web_files[route].kind is Kind.GENERATED


# trace: PRD-APP-008, PRD-APP-312
def test_route_handlers_have_the_roles_of_the_model(web_files: dict[str, OutputFile]) -> None:
    for name in OPERATIONS:
        text = web_files[f"src/_app/api-routes/{name}.gen.ts"].content.decode("utf-8")
        roles = '["admin"]' if name == "cancel-order" else '["admin", "clerk"]'
        assert f"  public: false,\n  roles: {roles},\n" in text, name


# trace: PRD-APP-114, PRD-APP-311
def test_list_has_the_limits_of_the_fastapi_contract(web_files: dict[str, OutputFile]) -> None:
    text = web_files["src/_app/api-routes/list-order.gen.ts"].content.decode("utf-8")
    assert "const LIMIT_DEFAULT = 50;" in text
    assert "const LIMIT_MAX = 200;" in text
    server = web_files["src/features/list-order/api/list-order.server.gen.ts"]
    assert ".orderBy(asc(KEY))" in server.content.decode("utf-8")


# trace: PRD-APP-113, PRD-APP-313
def test_crud_server_functions_use_the_drizzle_schema(web_files: dict[str, OutputFile]) -> None:
    for name in ("create-order", "read-order", "update-order", "delete-order", "list-order"):
        file = web_files[f"src/features/{name}/api/{name}.server.gen.ts"]
        text = file.content.decode("utf-8")
        assert file.kind is Kind.GENERATED
        assert 'import "server-only";' in text
        assert "orderTable as table" in text
        server_api = web_files[f"src/features/{name}/index.server.gen.ts"].content.decode()
        assert f'export * from "./api/{name}.server.gen";' in server_api
    create = web_files["src/features/create-order/api/create-order.server.gen.ts"]
    assert "total: String(input.total)," in create.content.decode("utf-8")
    delete = web_files["src/features/delete-order/api/delete-order.server.gen.ts"]
    assert "throw databaseProblem(error, 409);" in delete.content.decode("utf-8")


# trace: PRD-APP-313, PRD-CORE-044, PRD-CORE-045
def test_custom_operation_has_a_create_once_stub_with_a_typed_function(
    web_files: dict[str, OutputFile],
) -> None:
    stub = web_files[STUB]
    assert stub.kind is Kind.CREATE_ONCE
    text = stub.content.decode("utf-8")
    assert not text.startswith("// Generated by dsml")
    assert "  input: CancelOrderInput,\n  session: Session | undefined,\n" in text
    assert ") => Promise<CancelOrderOutput>;" in text
    assert "Promise.reject(new ProblemError(501, NOT_IMPLEMENTED));" in text
    assert "// trace: OrderWeb::CancelOrder\n" in text
    handler = web_files["src/_app/api-routes/cancel-order.gen.ts"].content.decode("utf-8")
    assert "const result: Output = await handleOperation(input, session);" in handler
    assert "    order_id: params.id,\n" in handler


# trace: PRD-CORE-042, PRD-CORE-044
def test_second_run_does_not_change_a_changed_stub(web_ir: Ir, tmp_path: Path) -> None:
    configuration = parse_configuration(CONFIGURATION, tmp_path / "dsml.toml")
    files = collect([NextjsGenerator()], web_ir, configuration, None)
    apply_plan(tmp_path, make_plan(tmp_path, files, None))
    path = f"order-web/{STUB}"
    stub = tmp_path / path
    assert stub.read_bytes() == (GOLDEN / STUB).read_bytes()
    changed = b"// Hand-written logic.\n"
    stub.write_bytes(changed)
    plan = make_plan(tmp_path, files, None)
    assert path not in {item for item, _ in plan.writes}
    assert not plan.conflicts
    apply_plan(tmp_path, plan)
    assert stub.read_bytes() == changed
    assert path in [entry.path for entry in read_manifest(tmp_path).create_once]


# trace: PRD-APP-302, PRD-APP-310
def test_path_parameters_at_one_place_get_one_folder_name() -> None:
    slugs = path_slugs(["/orders/{id}", "/orders/{orderId}/cancel", "/orders", "/items/{key}"])
    assert slugs == {
        "/orders/{id}": {"id": "id"},
        "/orders/{orderId}/cancel": {"orderId": "id"},
        "/orders": {},
        "/items/{key}": {"key": "key"},
    }


def test_two_operations_with_the_same_route_is_an_error() -> None:
    first = Operation("cancelOrder", "custom", "post", "/orders/{id}", (), False, ())
    second = replace(first, name="closeOrder", path="/orders/{orderId}")
    with pytest.raises(ToolchainError, match="the same method and path POST /orders"):
        check_names("orderWeb", [first, second])
    with pytest.raises(ToolchainError, match='two operations with the name "cancel-order"'):
        check_names("orderWeb", [first, replace(first, path="/other")])


def test_create_with_an_integer_key_is_an_error(tmp_path: Path) -> None:
    text = SHOP_MODEL.read_text(encoding="utf-8").replace("Target::fastapi", "Target::nextjs")
    model = tmp_path / "shop.sysml"
    model.write_text(text, encoding="utf-8")
    configuration = parse_configuration(
        'schema = 1\n\n[applications.shopApi]\noutput = "shop"\n', tmp_path / "dsml.toml"
    )
    with pytest.raises(ToolchainError, match="entity Customer has a key of the type Integer"):
        collect([NextjsGenerator()], make_ir([model], tmp_path), configuration, None)


# trace: PRD-APP-005, PRD-APP-310, PRD-APP-312
def test_custom_operation_with_the_method_get_has_its_schemas(shop_files: dict[str, str]) -> None:
    folder = "src/features/find-products"
    assert f"{folder}/model/find-products-schemas.gen.ts" in shop_files
    schemas = shop_files[f"{folder}/model/find-products-schemas.gen.ts"]
    assert "export const findProductsInputSchema = z.strictObject({" in schemas
    stub = shop_files[f"{folder}/api/find-products.server.ts"]
    assert 'from "../model/find-products-schemas.gen";' in stub
    handler = shop_files["src/_app/api-routes/find-products.gen.ts"]
    assert '    kind: query.get("kind") ?? undefined,\n' in handler
    assert '    codes: query.getAll("codes"),\n' in handler
    assert 'parseInput(inputSchema, value, "query")' in handler


# trace: PRD-APP-110, PRD-APP-311, PRD-APP-312
def test_route_handlers_of_the_shop(shop_files: dict[str, str]) -> None:
    archive = shop_files["src/_app/api-routes/archive-supplier.gen.ts"]
    assert "    ...(await readJsonObject(request)),\n    supplier: params.id,\n" in archive
    assert "  public: true,\n  roles: [],\n" in archive
    assert "return new Response(null, { status: 204 });" in archive
    restock = shop_files["src/_app/api-routes/restock-product.gen.ts"]
    assert "product_id: params.id," in restock
    customer = shop_files["src/_app/api-routes/read-customer.gen.ts"]
    assert "  id: z.preprocess(numberParameter, z.int())," in customer
    server = shop_files["src/features/read-customer/api/read-customer.server.gen.ts"]
    assert "export async function handleReadCustomer(key: number): Promise<Entity> {" in server
    product = shop_files["src/features/create-product/api/create-product.server.gen.ts"]
    assert "price: String(input.price)," in product
    assert re.search(r"addedAt:\s+input\.added_at == null \? input\.added_at : new Date", product)
    assert "added_at: row.addedAt?.toISOString() ?? null," in product
    routes = sorted(path for path in shop_files if path.startswith("app/api/"))
    assert routes == [
        "app/api/customer-count/route.ts",
        "app/api/customers/[id]/route.ts",
        "app/api/customers/route.ts",
        "app/api/product-search/route.ts",
        "app/api/products/[id]/restock/route.ts",
        "app/api/products/[id]/route.ts",
        "app/api/products/route.ts",
        "app/api/suppliers/[id]/archive/route.ts",
        "app/api/suppliers/[id]/route.ts",
        "app/api/suppliers/route.ts",
    ]
