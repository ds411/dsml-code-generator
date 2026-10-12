"""Tests of the CRUD slices of the FastAPI generator (story #84).

The golden files in `tests/golden/fastapi/shop/` are the output of the
FastAPI generator for the test model `tests/models/fastapi/shop.sysml`. The
model has the five CRUD operations, the field rules, a unique rule and two
relations. Write the golden files again with
`uv run python scripts/write_golden_fastapi.py`. The CI job "FastAPI golden
project" runs ruff, pyright and pytest on each golden project, with the HTTP
tests against PostgreSQL 18.
"""

import ast
import json
import re
from pathlib import Path

import pytest

from dsml.config import Configuration, parse_configuration
from dsml.errors import ToolchainError
from dsml.generate.fastapi import FastApiGenerator
from dsml.generate.fastapi_examples import Rules, invalid_values, pattern_example, sample
from dsml.generate.generators import collect
from dsml.generate.header import FileType, header
from dsml.generate.writer import apply_plan, make_plan
from dsml.ir.model import (
    Annotation,
    Attribute,
    BooleanValue,
    Element,
    EnumValue,
    IntegerValue,
    Ir,
    ListValue,
    Location,
    Multiplicity,
    StringValue,
)

ROOT = Path(__file__).resolve().parent.parent
SHOP_MODEL = ROOT / "tests" / "models" / "fastapi" / "shop.sysml"
GOLDENS = ROOT / "tests" / "golden" / "fastapi"
SHOP = GOLDENS / "shop"
PROJECT = "services/shop-api"
CACHES = frozenset({".pytest_cache", ".ruff_cache", ".venv", "__pycache__"})
SHOP_CONFIGURATION = '[applications.shopApi]\noutput = "services/shop-api"\n'
FEATURES = SHOP / PROJECT / "app" / "features"
LOCATION = Location(file="model.sysml", line=1, column=1)
ONE = Multiplicity(1, 1)
OPTIONAL = Multiplicity(0, 1)


def configuration(text: str = SHOP_CONFIGURATION) -> Configuration:
    return parse_configuration(f"schema = 1\n\n{text}", Path("dsml.toml"))


def files_in(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file() and not CACHES.intersection(path.parts)
    }


@pytest.fixture(scope="module")
def shop_ir() -> Ir:
    """Make the IR of the shop model one time for the tests of this module."""
    from dsml.adapter.convert import make_ir

    return make_ir([SHOP_MODEL], ROOT)


# trace: PRD-CORE-030, PRD-APP-102
def test_output_of_the_shop_model_agrees_with_the_golden_files(shop_ir: Ir, tmp_path: Path) -> None:
    files = collect([FastApiGenerator()], shop_ir, configuration(), None)
    apply_plan(tmp_path, make_plan(tmp_path, files, None))
    assert files_in(tmp_path) == files_in(SHOP), (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_fastapi.py and examine the differences."
    )


# trace: PRD-APP-102, PRD-APP-103
def test_each_crud_operation_has_a_slice_with_three_generated_files() -> None:
    slices = sorted(
        path.relative_to(FEATURES).as_posix()
        for path in FEATURES.glob("*/*")
        if path.is_dir() and not (path / "handler.py").exists()
    )
    assert slices == [
        "customer/create_customer",
        "customer/delete_customer",
        "customer/list_customer",
        "customer/read_customer",
        "customer/update_customer",
        "product/create_product",
        "product/delete_product",
        "product/list_product",
        "product/read_product",
        "product/update_product",
        "supplier/create_supplier",
        "supplier/list_supplier",
        "supplier/read_supplier",
    ]
    for item in slices:
        assert sorted(path.name for path in (FEATURES / item).iterdir()) == [
            "__init__.py",
            "endpoint_gen.py",
            "handler_gen.py",
            "schemas_gen.py",
        ]


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return modules


# trace: PRD-APP-106
@pytest.mark.parametrize("golden", ["order-service", "shop"])
def test_a_slice_file_imports_only_from_its_slice_and_from_app_shared(golden: str) -> None:
    features = next((GOLDENS / golden).glob("services/*/app/features"))
    paths = sorted(features.glob("*/*/*.py"))
    assert paths
    for path in paths:
        package = "app." + path.parent.relative_to(features.parent.parent).as_posix().replace(
            "/", "."
        ).removeprefix("app.")
        for module in _imported_modules(path):
            if module == "app" or module.startswith("app."):
                assert module.startswith((f"{package}.", "app.shared.")), (path, module)


# trace: PRD-APP-106
def test_the_import_test_finds_an_import_from_an_other_slice(tmp_path: Path) -> None:
    path = tmp_path / "endpoint_gen.py"
    path.write_text("from app.features.order.read_order.schemas_gen import ReadOrderOutput\n")
    assert _imported_modules(path) == ["app.features.order.read_order.schemas_gen"]
    assert not "app.features.order.read_order.schemas_gen".startswith(
        ("app.features.order.create_order.", "app.shared.")
    )


# trace: PRD-APP-110, PRD-TRACE-006
def test_each_endpoint_has_the_method_and_the_path_of_the_crud_table() -> None:
    data = json.loads((SHOP / ".dsml" / "trace.gen.json").read_bytes())
    routes = {
        (file["path"].removeprefix(f"{PROJECT}/app/features/"), symbol["name"])
        for element in data["elements"]
        for file in element["files"]
        for symbol in file["symbols"]
        if symbol["kind"] == "route"
    }
    assert routes == {
        ("customer/create_customer/endpoint_gen.py", "POST /customers"),
        ("customer/read_customer/endpoint_gen.py", "GET /customers/{id}"),
        ("customer/update_customer/endpoint_gen.py", "PATCH /customers/{id}"),
        ("customer/delete_customer/endpoint_gen.py", "DELETE /customers/{id}"),
        ("customer/list_customer/endpoint_gen.py", "GET /customers"),
        ("product/create_product/endpoint_gen.py", "POST /products"),
        ("product/read_product/endpoint_gen.py", "GET /products/{id}"),
        ("product/update_product/endpoint_gen.py", "PATCH /products/{id}"),
        ("product/delete_product/endpoint_gen.py", "DELETE /products/{id}"),
        ("product/list_product/endpoint_gen.py", "GET /products"),
        ("supplier/create_supplier/endpoint_gen.py", "POST /suppliers"),
        ("supplier/read_supplier/endpoint_gen.py", "GET /suppliers/{id}"),
        ("supplier/list_supplier/endpoint_gen.py", "GET /suppliers"),
        ("product/restock_product/endpoint_gen.py", "POST /products/{productId}/restock"),
        ("product/find_products/endpoint_gen.py", "GET /product-search"),
        ("count_customers/count_customers/endpoint_gen.py", "GET /customer-count"),
        ("supplier/archive_supplier/endpoint_gen.py", "POST /suppliers/{supplier}/archive"),
        (f"{PROJECT}/app/main_gen.py", "GET /healthz"),
    }


# trace: PRD-APP-017, PRD-TRACE-005
def test_slice_files_have_the_exposed_element_and_the_entity_in_the_header() -> None:
    text = (FEATURES / "product" / "read_product" / "handler_gen.py").read_text()
    assert text.startswith(header(FileType.PYTHON, ["Shop::Product", "Shop::shopApi::products"]))


# trace: PRD-APP-105
def test_main_registers_the_router_of_each_slice_in_sorted_order() -> None:
    text = (SHOP / PROJECT / "app" / "main_gen.py").read_text()
    registered = re.findall(r"app\.include_router\((\w+)\)", text)
    assert registered[0] == "health_router"
    imports = re.findall(r"from (app\.features\.\S+) import \(?\s*router as (\w+)", text)
    assert len(imports) == 17
    assert [module for module, _ in imports] == sorted(module for module, _ in imports)
    assert registered[1:] == [router for _, router in imports]
    assert (
        "from app.features.product.update_product.endpoint_gen import "
        "router as update_product_router\n"
    ) in text


# trace: PRD-APP-008
def test_endpoints_check_the_roles_and_a_public_operation_needs_no_token() -> None:
    product = (FEATURES / "product" / "create_product" / "endpoint_gen.py").read_text()
    assert 'ALLOWED_ROLES = ("admin", "clerk")\n' in product
    assert "dependencies=[Depends(require_roles(*ALLOWED_ROLES))]" in product
    supplier = (FEATURES / "supplier" / "create_supplier" / "endpoint_gen.py").read_text()
    assert "require_roles" not in supplier


# trace: PRD-APP-111, PRD-APP-112
def test_create_input_has_no_key_and_the_field_rules_as_constraints() -> None:
    text = (FEATURES / "product" / "create_product" / "schemas_gen.py").read_text()
    create_input = text.split("class CreateProductInput(BaseModel):")[1].split("\nclass ")[0]
    assert "    id:" not in create_input
    assert 'extra="forbid"' in create_input
    for line in (
        '    code: str = Field(pattern="^[A-Z]{3}-[0-9]{4}$")\n',
        "    price: Decimal = Field(ge=0, le=10000, max_digits=10, decimal_places=2)\n",
        "    stock: int = Field(ge=0, le=1000000)\n",
        "    weight: float | None = Field(default=None, ge=0.1)\n",
        "    kind: KindValue\n",
    ):
        assert line in create_input
    customer = (FEATURES / "customer" / "create_customer" / "schemas_gen.py").read_text()
    assert "    name: str = Field(min_length=2, max_length=80)\n" in customer


# trace: PRD-APP-111
def test_each_field_of_the_update_input_is_optional() -> None:
    text = (FEATURES / "product" / "update_product" / "schemas_gen.py").read_text()
    update_input = text.split("class UpdateProductInput(BaseModel):")[1].split("\nclass ")[0]
    fields = re.findall(r"^    (\w+): (.+)$", update_input, re.MULTILINE)
    assert [name for name, _ in fields if name != "model_config"] == [
        "added_at",
        "buyer_id",
        "code",
        "kind",
        "note",
        "price",
        "stock",
        "supplier_id",
        "weight",
    ]
    for name, annotation in fields:
        if name != "model_config":
            assert "| None = " in annotation, name
    assert '@field_validator("code", "kind", "price", "stock", "supplier_id")' in update_input


# trace: PRD-APP-115
def test_output_gives_a_related_entity_as_its_key() -> None:
    text = (FEATURES / "product" / "read_product" / "schemas_gen.py").read_text()
    assert "    supplier_id: UUID\n" in text
    assert "    buyer_id: int | None\n" in text


# trace: PRD-APP-113
def test_unique_rule_gives_a_unique_column_and_the_commit_gives_409() -> None:
    model = (SHOP / PROJECT / "app" / "shared" / "db" / "models" / "customer_gen.py").read_text()
    assert "    email: Mapped[str] = mapped_column(String(120), unique=True)\n" in model
    commit = (SHOP / PROJECT / "app" / "shared" / "db" / "commit_gen.py").read_text()
    assert "errors.UniqueViolation" in commit
    assert "HTTPStatus.CONFLICT" in commit


# trace: PRD-APP-114
def test_list_has_the_limits_and_sorts_by_key() -> None:
    endpoint = (FEATURES / "product" / "list_product" / "endpoint_gen.py").read_text()
    assert "LIMIT_DEFAULT = 50\n" in endpoint
    assert "LIMIT_MAX = 200\n" in endpoint
    assert "limit: Annotated[int, Query(ge=1, le=LIMIT_MAX)] = LIMIT_DEFAULT" in endpoint
    assert "offset: Annotated[int, Query(ge=0)] = 0" in endpoint
    handler = (FEATURES / "product" / "list_product" / "handler_gen.py").read_text()
    assert "select(Product).order_by(Product.id)" in handler


# trace: PRD-APP-113, PRD-APP-114, PRD-APP-135
def test_http_tests_cover_the_status_codes_of_the_fastapi_prd() -> None:
    text = (SHOP / PROJECT / "tests" / "test_products_http_gen.py").read_text()
    for name in (
        "test_operation_without_a_token_returns_401",
        "test_operation_without_a_permitted_role_returns_403",
        "test_create_returns_201_with_the_new_entity",
        "test_create_with_a_value_that_breaks_a_rule_returns_422",
        "test_create_with_the_code_of_a_different_entity_returns_409",
        "test_read_of_an_unknown_key_returns_404",
        "test_update_returns_200_with_the_changed_entity",
        "test_update_with_the_code_of_a_different_entity_returns_409",
        "test_delete_returns_204_and_deletes_the_entity",
        "test_list_returns_the_entities_sorted_by_key_and_the_total",
        "test_list_gives_the_page_of_limit_and_offset",
        "test_list_limit_has_the_default_50_and_the_maximum_200",
    ):
        assert f"def {name}(" in text, name
    supplier = (SHOP / PROJECT / "tests" / "test_suppliers_http_gen.py").read_text()
    assert "returns_401" not in supplier


# Unit tests of the test values.


@pytest.mark.parametrize(
    ("pattern", "examples"),
    [
        ("^[A-Z]{3}-[0-9]{4}$", ["AAA-0000", "BBB-1111", "CCC-2222"]),
        ("^[a-z]+@[a-z]+[.]com$", ["a@a.com", "b@b.com", "c@c.com"]),
        (r"(?:ab)+c\d", ["abc0", "abc1", "abc2"]),
        ("^x|y$", ["x", "x", "x"]),
        ("[^abc]{2}", ["dd", "ee", "ff"]),
    ],
)
def test_pattern_example_agrees_with_the_pattern(pattern: str, examples: list[str]) -> None:
    assert [pattern_example(pattern, variant) for variant in range(3)] == examples
    for example in examples:
        assert re.search(pattern, example)


@pytest.mark.parametrize("pattern", ["x(?=y)", r"(a)\1", "[", "a{2,", "(?i)a"])
def test_pattern_example_of_an_unknown_syntax_is_none(pattern: str) -> None:
    assert pattern_example(pattern) is None


# trace: PRD-APP-112
def test_sample_values_agree_with_the_field_rules() -> None:
    assert [sample(Rules("Decimal", min_value=0, max_value=100, scale=2), i) for i in range(3)] == [
        "25.00",
        "50.00",
        "75.00",
    ]
    assert [sample(Rules("Integer", min_value=5), i) for i in range(3)] == [5, 6, 7]
    assert [sample(Rules("Integer", max_value=5), i) for i in range(3)] == [5, 4, 3]
    assert sample(Rules("Integer", min_value=1, max_value=1), 1) is None
    assert [sample(Rules("String", min_length=4, max_length=8), i) for i in range(2)] == [
        "v0xx",
        "v1xx",
    ]
    assert sample(Rules("Uuid"), 0) == "00000000-0000-4000-8000-000000000001"
    assert sample(Rules("DateTime"), 25) == "2026-01-02T01:00:00Z"
    assert sample(Rules("Enumeration", values=("a", "b")), 3) == "b"


# trace: PRD-APP-112, PRD-APP-113
def test_invalid_values_break_each_field_rule() -> None:
    rules = Rules("String", min_length=2, max_length=30, pattern="^a")
    assert [(item.rule, item.expression) for item in invalid_values(rules)] == [
        ("minLength", '"x"'),
        ("maxLength", '"x" * 31'),
        ("pattern", '""'),
    ]
    assert [
        (item.rule, item.expression)
        for item in invalid_values(Rules("Integer", min_value=0.5, max_value=9.5))
    ] == [("minValue", "0"), ("maxValue", "10")]
    assert invalid_values(Rules("String", pattern="a*")) == []


# Tests of the generator with a small IR.


def element(
    identity: str,
    kind: str,
    *,
    types: tuple[str, ...] = (),
    multiplicity: Multiplicity | None = None,
    attributes: tuple[Attribute, ...] = (),
    annotations: tuple[Annotation, ...] = (),
) -> Element:
    owner, _, name = identity.rpartition("::")
    return Element(
        identity=identity,
        kind=kind,  # type: ignore[arg-type]
        name=name,
        qualified_name=identity,
        location=LOCATION,
        owner=owner or None,
        multiplicity=multiplicity,
        types=types,
        attributes=attributes,
        annotations=annotations,
    )


def crud_defaults(*items: tuple[str, str, str]) -> Attribute:
    return Attribute(
        "crudDefaults",
        ListValue(
            tuple(
                ListValue(
                    (
                        EnumValue("DSML::CrudKind", kind),
                        EnumValue("DSML::HttpMethod", method),
                        StringValue(path),
                    )
                )
                for kind, method, path in items
            )
        ),
    )


def small_ir(
    key_type: str = "DSML::Uuid",
    defaults: tuple[tuple[str, str, str], ...] = (("create", "post", "/{entities}"),),
    exposures: tuple[str, ...] = ("items",),
    pattern: str = "^[a-z]+$",
) -> Ir:
    """Give an IR with one entity Item, exposed with the CRUD operations of `defaults`."""
    rules = Annotation(
        "FieldRules",
        (
            Attribute("pattern", StringValue(pattern)),
            Attribute("unique", BooleanValue(True)),
            Attribute("maxLength", IntegerValue(40)),
        ),
    )
    return Ir(
        elements=(
            element(
                "Shop::shopApi",
                "Application",
                attributes=(Attribute("target", EnumValue("DSML::Target", "fastapi")),),
            ),
            *(
                element(
                    f"Shop::shopApi::{name}",
                    "Exposed",
                    types=("Shop::Item",),
                    attributes=(
                        crud_defaults(*defaults),
                        Attribute("public", BooleanValue(True)),
                    ),
                )
                for name in exposures
            ),
            element("Shop::Item", "Entity"),
            element(
                "Shop::Item::id",
                "Field",
                types=(key_type,),
                multiplicity=ONE,
                annotations=(Annotation("Key"),),
            ),
            element(
                "Shop::Item::class",
                "Field",
                types=("ScalarValues::String",),
                multiplicity=ONE,
                annotations=(rules,),
            ),
        )
    )


def generate(ir: Ir) -> dict[str, str]:
    files = FastApiGenerator().generate(ir, configuration(), None)
    return {file.path: file.content.decode() for file in files}


# trace: PRD-APP-111
def test_field_with_a_python_keyword_has_an_alias() -> None:
    files = generate(small_ir())
    text = files[f"{PROJECT}/app/features/item/create_item/schemas_gen.py"]
    assert '    class_: str = Field(max_length=40, pattern="^[a-z]+$", alias="class")\n' in text
    assert '    class_: str = Field(serialization_alias="class")\n' in text
    for path, content in files.items():
        if path.endswith(".py"):
            ast.parse(content)


# trace: PRD-APP-111
def test_create_with_a_key_that_the_application_cannot_make_is_an_error() -> None:
    with pytest.raises(ToolchainError, match="key of the type String"):
        generate(small_ir(key_type="ScalarValues::String"))


def test_two_exposures_of_one_entity_with_one_operation_are_an_error() -> None:
    with pytest.raises(ToolchainError, match="two create operations of the entity Item"):
        generate(small_ir(exposures=("items", "things")))


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/{entities}", "must have one path parameter"),
        ("/{entities}/{class}", "is not a correct Python name"),
    ],
)
def test_read_path_must_have_one_parameter_with_a_python_name(path: str, message: str) -> None:
    with pytest.raises(ToolchainError, match=message):
        generate(small_ir(defaults=(("read", "get", path),)))


# trace: PRD-APP-110
def test_crud_operation_uses_the_method_and_the_path_of_the_model() -> None:
    files = generate(small_ir(defaults=(("read", "get", "/shop/{entities}/{itemId}"),)))
    text = files[f"{PROJECT}/app/features/item/read_item/endpoint_gen.py"]
    assert '@router.get("/shop/items/{itemId}", responses=problem_responses(404, 422))\n' in text
    assert "    return await handle(itemId, session)\n" in text


def test_http_tests_skip_if_the_generator_cannot_make_the_values() -> None:
    files = generate(small_ir(pattern="(?=a)"))
    text = files[f"{PROJECT}/tests/test_items_http_gen.py"]
    assert (
        'pytest.skip("The generator cannot make a value of the field class.", '
        "allow_module_level=True)"
    ) in text
