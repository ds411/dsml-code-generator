"""Tests of the OpenAPI document of the FastAPI generator (story #90).

The golden files `openapi.gen.json` in `tests/golden/fastapi/` are the
output of the generator for the example model and for the shop model.
Write them again with `uv run python scripts/write_golden_fastapi.py`.

The CI job "FastAPI golden project" runs the test
`test_openapi_document_agrees_with_openapi_gen_json` of each golden project.
That test starts the application and compares its OpenAPI document with
`openapi.gen.json` (PRD-APP-004).
"""

import ast
import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.protocols import Validator

from dsml.generate.fastapi_openapi import (
    OPENAPI_PATH,
    PROBLEM_SCHEMA,
    SECURITY_SCHEME,
    STATUS_PHRASES,
    openapi_document,
)
from dsml.ir.writer import canonical_json

ROOT = Path(__file__).resolve().parent.parent
GOLDENS = ROOT / "tests" / "golden" / "fastapi"
ORDER_API = GOLDENS / "order-service" / "services" / "order-api"
SHOP_API = GOLDENS / "shop" / "services" / "shop-api"
SCHEMA_FILE = ROOT / "tests" / "schemas" / "openapi-3.1-schema-2022-10-07.json"
PROBLEM = {"$ref": "#/components/schemas/Problem"}


def document(api: Path) -> Any:
    return json.loads((api / OPENAPI_PATH).read_text(encoding="utf-8"))


def problems(*statuses: int) -> dict[str, object]:
    return {
        str(status): {
            "content": {"application/problem+json": {"schema": PROBLEM}},
            "description": STATUS_PHRASES[status],
        }
        for status in statuses
    }


def validator() -> Validator:
    return jsonschema.Draft202012Validator(json.loads(SCHEMA_FILE.read_text(encoding="utf-8")))


# trace: PRD-APP-004
def test_documents_agree_with_the_openapi_3_1_schema() -> None:
    for api in (ORDER_API, SHOP_API):
        validator().validate(document(api))


# trace: PRD-CORE-028, PRD-CORE-031, PRD-CORE-034
def test_document_is_canonical_json() -> None:
    for api in (ORDER_API, SHOP_API):
        content = (api / OPENAPI_PATH).read_bytes()
        assert content == canonical_json(json.loads(content))
        assert content.endswith(b"}\n")
        assert b"\r" not in content


# trace: PRD-APP-004, PRD-APP-110
def test_document_has_the_paths_and_the_methods_of_the_operations() -> None:
    data = document(ORDER_API)
    assert data["openapi"] == "3.1.0"
    assert data["info"] == {"title": "orderApi", "version": "0.1.0"}
    assert {path: sorted(methods) for path, methods in data["paths"].items()} == {
        "/healthz": ["get"],
        "/orders": ["get", "post"],
        "/orders/{id}": ["get"],
        "/orders/{orderId}/cancel": ["post"],
    }
    create = data["paths"]["/orders"]["post"]
    assert create["operationId"] == "create_order_orders_post"
    assert create["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CreateOrderInput"
    }
    assert create["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CreateOrderOutput"
    }


# trace: PRD-APP-004, PRD-APP-111, PRD-APP-112, PRD-APP-115
def test_document_has_the_schemas_of_the_slices() -> None:
    schemas = document(SHOP_API)["components"]["schemas"]
    create = schemas["CreateProductInput"]
    assert create["additionalProperties"] is False
    assert "id" not in create["properties"]
    assert create["required"] == ["code", "kind", "price", "stock", "supplier_id"]
    assert create["properties"]["price"] == {
        "anyOf": [{"maximum": 10000, "minimum": 0, "type": "number"}, {"type": "string"}],
        "title": "Price",
    }
    assert create["properties"]["code"]["pattern"] == "^[A-Z]{3}-[0-9]{4}$"
    assert "required" not in schemas["UpdateProductInput"]
    output = schemas["ReadProductOutput"]
    assert output["properties"]["price"] == {"title": "Price", "type": "string"}
    assert output["properties"]["supplier_id"] == {
        "format": "uuid",
        "title": "Supplier Id",
        "type": "string",
    }
    assert schemas["Problem"] == PROBLEM_SCHEMA


# trace: PRD-APP-004, PRD-APP-008, PRD-APP-113
def test_document_has_the_security_scheme_and_the_problem_responses() -> None:
    data = document(SHOP_API)
    assert data["components"]["securitySchemes"] == {
        SECURITY_SCHEME: {
            "description": "The Cognito access token.",
            "scheme": "bearer",
            "type": "http",
        }
    }
    paths = data["paths"]
    delete = paths["/customers/{id}"]["delete"]
    assert delete["security"] == [{SECURITY_SCHEME: []}]
    assert delete["responses"] == {
        "204": {"description": "Successful Response"},
        **problems(401, 403, 404, 409, 422),
    }
    public = paths["/suppliers/{id}"]["get"]
    assert "security" not in public
    assert sorted(public["responses"]) == ["200", "404", "422"]
    count = paths["/customer-count"]["get"]
    assert sorted(count["responses"]) == ["200", "401", "403"]
    archive = paths["/suppliers/{supplier}/archive"]["post"]
    assert sorted(archive["responses"]) == ["204", "422"]


# trace: PRD-APP-004
def test_query_parameters_of_a_custom_operation() -> None:
    search = document(SHOP_API)["paths"]["/product-search"]["get"]
    assert search["parameters"] == [
        {
            "in": "query",
            "name": "kind",
            "required": True,
            "schema": {"enum": ["book", "music", "video"], "title": "Kind", "type": "string"},
        },
        {
            "in": "query",
            "name": "codes",
            "required": False,
            "schema": {
                "default": [],
                "items": {"type": "string"},
                "title": "Codes",
                "type": "array",
            },
        },
    ]
    assert search["responses"]["200"]["content"]["application/json"]["schema"] == {
        "items": {"$ref": "#/components/schemas/FindProductsOutput"},
        "title": "Response Find Products Product Search Get",
        "type": "array",
    }


# trace: PRD-APP-004
def test_application_with_no_operation_has_only_healthz() -> None:
    data: Any = openapi_document("emptyApi", "0.1.0", [])
    assert list(data["paths"]) == ["/healthz"]
    assert sorted(data["components"]) == ["schemas"]
    assert sorted(data["components"]["schemas"]) == ["Health", "Problem"]


# trace: PRD-APP-004, PRD-APP-014
def test_problem_schema_of_the_application_agrees_with_the_generator() -> None:
    tree = ast.parse((ORDER_API / "app" / "shared" / "errors_gen.py").read_text(encoding="utf-8"))
    value = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "PROBLEM_SCHEMA"
    )
    assert value is not None
    assert ast.literal_eval(value) == PROBLEM_SCHEMA


# trace: PRD-APP-004
def test_generated_project_compares_its_document_with_openapi_gen_json() -> None:
    for api in (ORDER_API, SHOP_API):
        text = (api / "tests" / "test_app_gen.py").read_text(encoding="utf-8")
        assert "def test_openapi_document_agrees_with_openapi_gen_json() -> None:\n" in text
        assert '    response = client.get("/openapi.json")\n' in text
        assert "    assert response.json() == expected\n" in text
