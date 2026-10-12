"""Tests of the custom operation slices of the FastAPI generator (story #88).

The example model has the custom operation CancelOrder. The test model
`tests/models/fastapi/shop.sysml` has custom operations with a request
body, query parameters, a list output, a scalar output, no output and a
public operation. The golden files of the two models are in
`tests/golden/fastapi/`. The CI job "FastAPI golden project" runs ruff,
pyright and pytest on each golden project. Its last step shows a type
check error in a hand-written handler that does not agree with a changed
model (PRD-CORE-045).
"""

import ast
import importlib.util
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

from dsml.config import Configuration, parse_configuration
from dsml.errors import ToolchainError
from dsml.generate.fastapi import FastApiGenerator
from dsml.generate.generators import collect
from dsml.generate.writer import Kind, apply_plan, make_plan, read_manifest
from dsml.ir.model import Element, EnumValue, Ir, Location, Multiplicity, StringValue

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
GOLDENS = ROOT / "tests" / "golden" / "fastapi"
ORDER_API = GOLDENS / "order-service" / "services" / "order-api"
SHOP_API = GOLDENS / "shop" / "services" / "shop-api"
HANDLER_CHECK = GOLDENS / "handler-check"
CANCEL = "app/features/order/cancel_order"
HANDLER = f"services/order-api/{CANCEL}/handler.py"
CONFIGURATION = '[applications.orderApi]\noutput = "services/order-api"\n'
LOCATION = Location(file="model.sysml", line=1, column=1)


def configuration(text: str = CONFIGURATION) -> Configuration:
    return parse_configuration(f"schema = 1\n\n{text}", Path("dsml.toml"))


def golden_script() -> ModuleType:
    """Load scripts/write_golden_fastapi.py as a module."""
    path = ROOT / "scripts" / "write_golden_fastapi.py"
    spec = importlib.util.spec_from_file_location("write_golden_fastapi", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def example_ir() -> Ir:
    """Make the IR of the example model one time for the tests of this module."""
    from dsml.adapter.convert import make_ir

    return make_ir([EXAMPLE_MODEL], ROOT)


def generate(ir: Ir) -> dict[str, str]:
    files = FastApiGenerator().generate(ir, configuration(), None)
    return {file.path: file.content.decode() for file in files}


# trace: PRD-APP-102, PRD-APP-103
def test_each_custom_operation_has_a_slice_with_a_create_once_handler() -> None:
    folders = {
        path.parent.relative_to(api / "app" / "features").as_posix()
        for api in (ORDER_API, SHOP_API)
        for path in (api / "app" / "features").glob("*/*/handler.py")
    }
    assert folders == {
        "count_customers/count_customers",
        "order/cancel_order",
        "product/find_products",
        "product/restock_product",
        "supplier/archive_supplier",
    }
    for api in (ORDER_API, SHOP_API):
        for path in (api / "app" / "features").glob("*/*/handler.py"):
            assert sorted(item.name for item in path.parent.iterdir()) == [
                "__init__.py",
                "endpoint_gen.py",
                "handler.py",
                "schemas_gen.py",
            ]
    manifest = read_manifest(GOLDENS / "order-service")
    assert [entry.path for entry in manifest.create_once] == [HANDLER]
    assert HANDLER not in {entry.path for entry in manifest.generated}


# trace: PRD-APP-116
def test_endpoint_validates_the_input_checks_the_roles_and_calls_handle() -> None:
    text = (ORDER_API / CANCEL / "endpoint_gen.py").read_text()
    assert (
        '@router.post("/orders/{orderId}/cancel", responses=problem_responses(401, 403, 422))\n'
        in text
    )
    assert "    orderId: UUID,\n" in text
    assert "    session: Annotated[AsyncSession, Depends(get_session)],\n" in text
    assert "    user: Annotated[User, Depends(require_roles(*ALLOWED_ROLES))],\n" in text
    assert 'ALLOWED_ROLES = ("admin",)\n' in text
    assert ") -> CancelOrderOutput:\n" in text
    assert '    data = CancelOrderInput.model_validate({"order_id": orderId})\n' in text
    assert "    return await handle(data, session, user)\n" in text
    assert "from app.features.order.cancel_order.handler import handle\n" in text


# trace: PRD-APP-116
def test_body_query_list_scalar_and_no_output() -> None:
    features = SHOP_API / "app" / "features"
    restock = (features / "product" / "restock_product" / "endpoint_gen.py").read_text()
    assert "    body: RestockProductBody,\n" in restock
    assert '{"product_id": productId, **body.model_dump(by_alias=True)}' in restock
    find = (features / "product" / "find_products" / "endpoint_gen.py").read_text()
    assert "    query: Annotated[FindProductsQuery, Query()],\n" in find
    assert ") -> list[FindProductsOutput]:\n" in find
    schemas = (features / "product" / "find_products" / "schemas_gen.py").read_text()
    assert "    codes: list[str] = []\n" in schemas
    assert "    kind: KindValue\n" in schemas
    count = (features / "count_customers" / "count_customers" / "schemas_gen.py").read_text()
    assert "    vip_total: int\n" in count
    assert "    newest: date | None = None\n" in count
    archive = (features / "supplier" / "archive_supplier" / "endpoint_gen.py").read_text()
    assert "status_code=HTTPStatus.NO_CONTENT" in archive
    assert "require_roles" not in archive
    assert "    await handle(data, session, None)\n" in archive
    handler = (features / "supplier" / "archive_supplier" / "handler.py").read_text()
    assert "user: User | None) -> None:" in handler


# trace: PRD-APP-117, PRD-CORE-045
def test_stub_has_the_typed_handle_function_that_raises_not_implemented_error() -> None:
    text = (ORDER_API / CANCEL / "handler.py").read_text()
    assert not text.startswith("# Generated")
    tree = ast.parse(text)
    function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef))
    assert function.name == "handle"
    assert [
        (argument.arg, ast.unparse(argument.annotation) if argument.annotation else None)
        for argument in function.args.args
    ] == [("data", "CancelOrderInput"), ("session", "AsyncSession"), ("user", "User")]
    assert function.returns is not None
    assert ast.unparse(function.returns) == "CancelOrderOutput"
    statement = function.body[-1]
    assert isinstance(statement, ast.Raise) and statement.exc is not None
    assert "NotImplementedError" in ast.unparse(statement.exc)
    assert "# trace: OrderService::CancelOrder\n" in text


# trace: PRD-APP-117
def test_not_implemented_error_gives_http_501() -> None:
    errors = (ORDER_API / "app" / "shared" / "errors_gen.py").read_text()
    assert "app.add_exception_handler(NotImplementedError, _not_implemented)\n" in errors
    assert "HTTPStatus.NOT_IMPLEMENTED" in errors
    tests = (ORDER_API / "tests" / "test_cancel_order_http_gen.py").read_text()
    assert "def test_stub_returns_501() -> None:\n" in tests
    assert "    assert response.status_code == 501\n" in tests


# trace: PRD-CORE-042, PRD-CORE-044
def test_second_run_does_not_change_a_changed_handler(example_ir: Ir, tmp_path: Path) -> None:
    files = collect([FastApiGenerator()], example_ir, configuration(), None)
    apply_plan(tmp_path, make_plan(tmp_path, files, None))
    handler = tmp_path / HANDLER
    assert handler.read_bytes() == (ORDER_API / CANCEL / "handler.py").read_bytes()
    changed = b'"""Hand-written logic."""\n'
    handler.write_bytes(changed)
    plan = make_plan(tmp_path, files, None)
    assert HANDLER not in {path for path, _ in plan.writes}
    assert not plan.conflicts
    apply_plan(tmp_path, plan)
    assert handler.read_bytes() == changed
    assert [entry.path for entry in read_manifest(tmp_path).create_once] == [HANDLER]


# trace: PRD-CORE-045
def test_changed_model_gives_the_files_of_the_type_check(example_ir: Ir) -> None:
    script = golden_script()
    files = collect([FastApiGenerator()], script.changed_example(example_ir), configuration(), None)
    by_path = {file.path: file for file in files}
    folder = f"services/order-api/{CANCEL}"
    for name in ("endpoint_gen.py", "schemas_gen.py"):
        assert by_path[f"{folder}/{name}"].content == (HANDLER_CHECK / name).read_bytes(), (
            "The files of tests/golden/fastapi/handler-check/ are not correct. Run "
            "uv run python scripts/write_golden_fastapi.py and examine the differences."
        )
    schemas = (HANDLER_CHECK / "schemas_gen.py").read_text()
    assert "    order_key: UUID\n" in schemas
    assert "order_id" not in schemas
    assert by_path[f"{folder}/handler.py"].kind is Kind.CREATE_ONCE
    assert "data.order_id" in (HANDLER_CHECK / "handler.py").read_text()


# Tests of the generator with a changed IR of the example model.


def _replace(ir: Ir, identity: str, **changes: object) -> Ir:
    elements = tuple(
        replace(item, **changes) if item.identity == identity else item  # type: ignore[arg-type]
        for item in ir.elements
    )
    return replace(ir, elements=elements)


def _with_path(ir: Ir, path: str) -> Ir:
    operation = next(item for item in ir.elements if item.identity == "OrderService::CancelOrder")
    attributes = tuple(
        replace(item, value=StringValue(path)) if item.name == "path" else item
        for item in operation.attributes
    )
    return _replace(ir, operation.identity, attributes=attributes)


def test_path_parameter_must_be_an_in_parameter(example_ir: Ir) -> None:
    with pytest.raises(ToolchainError, match='parameter "orderKey"'):
        generate(_with_path(example_ir, "/orders/{orderKey}/cancel"))


def test_path_parameter_must_have_a_correct_python_name(example_ir: Ir) -> None:
    ir = _replace(example_ir, "OrderService::CancelOrder::orderId", name="session")
    with pytest.raises(ToolchainError, match="not a correct Python name"):
        generate(_with_path(ir, "/orders/{session}/cancel"))


def test_path_parameter_must_be_one_value(example_ir: Ir) -> None:
    ir = _replace(
        example_ir, "OrderService::CancelOrder::orderId", multiplicity=Multiplicity(0, None)
    )
    with pytest.raises(ToolchainError, match="must have the multiplicity"):
        generate(ir)


def test_parameter_with_an_unknown_type_is_an_error(example_ir: Ir) -> None:
    ir = _replace(example_ir, "OrderService::CancelOrder::orderId", types=("Other::Thing",))
    with pytest.raises(ToolchainError, match="type that the FastAPI target does not know"):
        generate(ir)


def test_custom_operation_needs_an_entity(example_ir: Ir) -> None:
    ir = replace(
        example_ir,
        elements=tuple(
            item
            for item in example_ir.elements
            if item.identity != "OrderService::orderApi::orders"
        ),
    )
    ir = _replace(ir, "OrderService::CancelOrder::order", types=("ScalarValues::Boolean",))
    with pytest.raises(ToolchainError, match="needs a database"):
        generate(ir)


def test_custom_operation_with_the_folder_of_a_crud_operation_is_an_error(
    example_ir: Ir,
) -> None:
    ir = _replace(example_ir, "OrderService::orderApi::cancelOrder", name="createOrder")
    with pytest.raises(ToolchainError, match="has the slice folder"):
        generate(ir)


def test_entity_in_parameter_gives_the_key_and_no_out_parameter_gives_204(
    example_ir: Ir,
) -> None:
    ir = _replace(example_ir, "OrderService::CancelOrder::orderId", types=("OrderService::Order",))
    ir = replace(
        ir,
        elements=tuple(
            item for item in ir.elements if item.identity != "OrderService::CancelOrder::order"
        ),
    )
    files = generate(ir)
    folder = f"services/order-api/{CANCEL}"
    assert "    order_id: UUID\n" in files[f"{folder}/schemas_gen.py"]
    assert "CancelOrderOutput" not in files[f"{folder}/schemas_gen.py"]
    endpoint = files[f"{folder}/endpoint_gen.py"]
    assert "status_code=HTTPStatus.NO_CONTENT" in endpoint
    assert ") -> None:\n" in endpoint
    for path, content in files.items():
        if path.endswith(".py"):
            ast.parse(content)


def test_enumeration_parameter_in_the_path_has_a_type_alias(example_ir: Ir) -> None:
    status = Element(
        identity="OrderService::CancelOrder::status",
        kind="Parameter",
        name="status",
        qualified_name="OrderService::CancelOrder::status",
        location=LOCATION,
        owner="OrderService::CancelOrder",
        direction="in",
        types=("OrderService::OrderStatus",),
    )
    ir = replace(example_ir, elements=(*example_ir.elements, status))
    files = generate(_with_path(ir, "/orders/{orderId}/{status}"))
    folder = f"services/order-api/{CANCEL}"
    endpoint = files[f"{folder}/endpoint_gen.py"]
    assert "    status: StatusValue,\n" in endpoint
    assert "StatusValue" in endpoint.split("router = ")[0]
    schemas = files[f"{folder}/schemas_gen.py"]
    assert schemas.count('StatusValue = Literal["open", "shipped", "cancelled"]\n') == 1


def test_attribute_value_of_the_method_gives_the_route(example_ir: Ir) -> None:
    operation = next(item for item in example_ir.elements if item.identity.endswith("CancelOrder"))
    attributes = tuple(
        replace(item, value=EnumValue("DSML::HttpMethod", "patch"))
        if item.name == "method"
        else item
        for item in operation.attributes
    )
    files = generate(_replace(example_ir, operation.identity, attributes=attributes))
    endpoint = files[f"services/order-api/{CANCEL}/endpoint_gen.py"]
    assert (
        '@router.patch("/orders/{orderId}/cancel", responses=problem_responses(401, 403, 422))\n'
        in endpoint
    )
