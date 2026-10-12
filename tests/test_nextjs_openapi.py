"""Tests of the OpenAPI document of the Next.js generator (story #187).

The golden file `tests/golden/nextjs/order-web/openapi.gen.json` is the
output for the order web model. Write it again with
`uv run python scripts/write_golden_nextjs.py`.

The document uses the OpenAPI writer of the FastAPI target with the path
prefix `/api` (PRD-APP-004, PRD-APP-311). The tests compare its paths and
methods with the golden route files in `app/`.
"""

import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from jsonschema.protocols import Validator

from dsml.adapter.convert import make_ir
from dsml.config import parse_configuration
from dsml.generate.fastapi_openapi import OPENAPI_PATH, openapi_document
from dsml.generate.generators import collect
from dsml.generate.nextjs import NextjsGenerator
from dsml.generate.nextjs_routes import application_operations
from dsml.generate.prettier_json import prettier_json
from dsml.generate.react_common import NEXTJS_LAYOUT, ReactContext
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import OutputFile
from dsml.ir.model import Ir

ROOT = Path(__file__).resolve().parent.parent
WEB_MODEL = ROOT / "docs" / "model" / "examples" / "order-web" / "order-web.sysml"
GOLDEN = ROOT / "tests" / "golden" / "nextjs" / "order-web"
FASTAPI_GOLDEN = ROOT / "tests" / "golden" / "fastapi" / "order-service" / "services" / "order-api"
SCHEMA_FILE = ROOT / "tests" / "schemas" / "openapi-3.1-schema-2022-10-07.json"
CONFIGURATION = 'schema = 1\n\n[applications.orderWeb]\noutput = "order-web"\n'
EXPORT = re.compile(r'^export \{ (GET|POST|PUT|PATCH|DELETE) \} from "[^"]+";$', re.MULTILINE)


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


def golden_document() -> Any:
    return json.loads((GOLDEN / OPENAPI_PATH).read_text(encoding="utf-8"))


def validator() -> Validator:
    return jsonschema.Draft202012Validator(json.loads(SCHEMA_FILE.read_text(encoding="utf-8")))


def route_folder(path: str) -> str:
    """Give a pattern for the folder of the route file of an OpenAPI path.

    A path parameter matches any dynamic segment, because the route tree
    gives one name to all the dynamic segments at one place.
    """
    parts = [re.escape(part) for part in path.strip("/").split("/")]
    segments = ["\\[[A-Za-z0-9_]+\\]" if part.startswith("\\{") else part for part in parts]
    return "app/" + "/".join(segments)


# trace: PRD-APP-004, PRD-CORE-030
def test_openapi_document_of_the_order_web_agrees_with_the_golden_file(
    web_files: dict[str, OutputFile],
) -> None:
    assert web_files[OPENAPI_PATH].content == (GOLDEN / OPENAPI_PATH).read_bytes(), (
        "The output is different from the golden file. If the change is correct, run "
        "uv run python scripts/write_golden_nextjs.py and examine the differences."
    )


# trace: PRD-APP-004
def test_document_agrees_with_the_openapi_3_1_schema() -> None:
    validator().validate(golden_document())


# trace: PRD-CORE-028, PRD-CORE-031, PRD-CORE-034
def test_document_has_the_prettier_format_with_sorted_keys() -> None:
    content = (GOLDEN / OPENAPI_PATH).read_bytes()
    assert content == prettier_json(json.loads(content))
    assert content.endswith(b"}\n")
    assert b"\r" not in content


# trace: PRD-APP-311
def test_paths_of_the_operations_have_the_prefix_api() -> None:
    data = golden_document()
    assert data["info"] == {"title": "orderWeb", "version": "0.1.0"}
    assert {path: sorted(methods) for path, methods in data["paths"].items()} == {
        "/api/orders": ["get", "post"],
        "/api/orders/{id}": ["delete", "get", "patch"],
        "/api/orders/{orderId}/cancel": ["post"],
        "/healthz": ["get"],
    }
    operation = data["paths"]["/api/orders/{orderId}/cancel"]["post"]
    assert operation["operationId"] == "cancel_order_api_orders__orderId__cancel_post"


# trace: PRD-APP-004, PRD-APP-302, PRD-APP-311
def test_each_operation_has_one_route_file_with_the_same_method_and_path() -> None:
    documented = {
        (method.upper(), path)
        for path, methods in golden_document()["paths"].items()
        for method in methods
    }
    routes: set[tuple[str, str]] = set()
    for file in sorted(GOLDEN.glob("app/**/route.ts")):
        folder = file.parent.relative_to(GOLDEN).as_posix()
        for method in EXPORT.findall(file.read_text(encoding="utf-8")):
            routes.add((method, folder))
    matched: set[tuple[str, str]] = set()
    for method, path in documented:
        folders = [
            folder
            for route_method, folder in routes
            if route_method == method and re.fullmatch(route_folder(path), folder)
        ]
        assert len(folders) == 1, f"{method} {path} has {len(folders)} route files."
        matched.add((method, folders[0]))
    assert matched == routes


# trace: PRD-APP-004, PRD-APP-311
def test_prefix_changes_only_the_paths_and_the_operation_ids(web_ir: Ir) -> None:
    application = next(
        element
        for element in web_ir.elements
        if element.kind == "Application" and element.name == "orderWeb"
    )
    configuration = parse_configuration(CONFIGURATION, ROOT / "dsml.toml")
    context = ReactContext(
        TemplateEngine(), web_ir, application, configuration, "", "", NEXTJS_LAYOUT
    )
    routers = [
        item
        for operation in application_operations(context)
        if (item := operation.crud or operation.custom) is not None
    ]
    plain = openapi_document("orderWeb", "0.1.0", routers)
    prefixed = openapi_document("orderWeb", "0.1.0", routers, "/api")
    assert prefixed == golden_document()
    renamed = json.loads(
        json.dumps(plain).replace('"/orders', '"/api/orders').replace("_orders_", "_api_orders_")
    )
    assert prefixed == renamed


# trace: PRD-APP-004
def test_fastapi_document_has_no_prefix() -> None:
    data = json.loads((FASTAPI_GOLDEN / OPENAPI_PATH).read_text(encoding="utf-8"))
    assert all(not path.startswith("/api") for path in data["paths"])
