"""Tests of the FastAPI generator: project files and shared code (story #75).

The golden files in `tests/golden/fastapi/order-service/` are the output of
the FastAPI generator for the example model. Write them again with
`uv run python scripts/write_golden_fastapi.py`. The CI job "FastAPI golden
project" runs ruff, pyright and pytest on the golden project, and starts its
container.
"""

import json
import tomllib
from pathlib import Path

import pytest

from dsml.config import Configuration, parse_configuration
from dsml.database.snapshot import SNAPSHOT_PATH
from dsml.errors import ToolchainError
from dsml.generate import generators
from dsml.generate.fastapi import DATABASE_VARIABLES, FIXED_NAMES, VARIABLES, FastApiGenerator
from dsml.generate.generators import collect
from dsml.generate.header import FileType, file_type_of, header
from dsml.generate.python_symbols import python_symbols
from dsml.generate.trace import Symbol, SymbolKind
from dsml.generate.writer import INFRASTRUCTURE, LOCKFILES, Kind, apply_plan, make_plan
from dsml.ir.model import Attribute, Element, EnumValue, Ir, Location
from dsml.versions import load_baseline, pinned_version

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
GOLDEN = ROOT / "tests" / "golden" / "fastapi" / "order-service"
PROJECT = "services/order-api"
APP = "OrderService::orderApi"
ORDER = "OrderService::Order"
ORDERS = "OrderService::orderApi::orders"
CANCEL = "OrderService::CancelOrder"
CANCEL_ORDER = "OrderService::orderApi::cancelOrder"
CUSTOM = "app/features/order/cancel_order/"
HANDLER = f"{CUSTOM}handler.py"
MODEL = "app/shared/db/models/order_gen.py"
MIGRATION = "migrations/versions/0001_create_order_gen.py"
CACHES = frozenset({".pytest_cache", ".ruff_cache", ".venv", "__pycache__"})
"""The folders that the tools make in the golden project. The tests ignore them."""
CONFIGURATION = '[applications.orderApi]\noutput = "services/order-api"\n'


def configuration(text: str = CONFIGURATION) -> Configuration:
    return parse_configuration(f"schema = 1\n\n{text}", Path("dsml.toml"))


def files_in(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file() and not CACHES.intersection(path.parts)
    }


def application(name: str = "orderApi", target: str = "fastapi") -> Element:
    location = Location(file="model.sysml", line=1, column=1)
    return Element(
        identity=f"Shop::{name}",
        kind="Application",
        name=name,
        qualified_name=f"Shop::{name}",
        location=location,
        attributes=(Attribute("target", EnumValue("DSML::Target", target), location),),
    )


@pytest.fixture(scope="module")
def example_ir() -> Ir:
    """Make the IR of the example model one time for the tests of this module."""
    from dsml.adapter.convert import make_ir

    return make_ir([EXAMPLE_MODEL], ROOT)


# trace: PRD-CORE-030, PRD-APP-002, PRD-TRACE-006
def test_output_of_the_example_model_agrees_with_the_golden_files(
    example_ir: Ir, tmp_path: Path
) -> None:
    files = collect([FastApiGenerator()], example_ir, configuration(), None)
    apply_plan(tmp_path, make_plan(tmp_path, files, None))
    assert files_in(tmp_path) == files_in(GOLDEN), (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_fastapi.py and examine the differences."
    )


# trace: PRD-CORE-028
def test_output_is_the_same_at_each_run(example_ir: Ir) -> None:
    first = collect([FastApiGenerator()], example_ir, configuration(), None)
    second = collect([FastApiGenerator()], example_ir, configuration(), None)
    assert first == second


def test_fastapi_generator_is_in_the_list_of_generators() -> None:
    assert any(isinstance(generator, FastApiGenerator) for generator in generators.GENERATORS)


# trace: PRD-APP-002, PRD-APP-104, PRD-APP-105, PRD-APP-134
def test_project_has_the_files_of_the_target() -> None:
    assert sorted(path for path in files_in(GOLDEN / PROJECT)) == [
        ".dockerignore",
        SNAPSHOT_PATH,
        "Dockerfile",
        "alembic.ini",
        "app/__init__.py",
        "app/features/__init__.py",
        "app/features/order/__init__.py",
        *(
            f"app/features/order/cancel_order/{name}"
            for name in ("__init__.py", "endpoint_gen.py", "handler.py", "schemas_gen.py")
        ),
        *(
            f"app/features/order/{operation}_order/{name}"
            for operation in ("create", "list", "read")
            for name in ("__init__.py", "endpoint_gen.py", "handler_gen.py", "schemas_gen.py")
        ),
        "app/main_gen.py",
        "app/migrate_gen.py",
        "app/shared/__init__.py",
        "app/shared/auth/__init__.py",
        "app/shared/auth/cognito_gen.py",
        "app/shared/config_gen.py",
        "app/shared/db/__init__.py",
        "app/shared/db/base_gen.py",
        "app/shared/db/commit_gen.py",
        "app/shared/db/models/__init__.py",
        MODEL,
        "app/shared/db/session_gen.py",
        "app/shared/errors_gen.py",
        "app/shared/logs_gen.py",
        "migrations/env.py",
        MIGRATION,
        "pyproject.toml",
        "tests/http_support_gen.py",
        "tests/test_app_gen.py",
        "tests/test_auth_gen.py",
        "tests/test_cancel_order_http_gen.py",
        "tests/test_db_gen.py",
        "tests/test_migrations_gen.py",
        "tests/test_orders_http_gen.py",
    ]


# trace: PRD-CORE-036, PRD-CORE-039, PRD-APP-134
def test_fixed_names_and_no_lockfile(example_ir: Ir) -> None:
    assert set(FIXED_NAMES) == {
        ".dockerignore",
        "Dockerfile",
        "__init__.py",
        "alembic.ini",
        "migrations/env.py",
        "pyproject.toml",
    }
    files = collect([FastApiGenerator()], example_ir, configuration(), None)
    create_once = [file.path for file in files if file.kind is not Kind.GENERATED]
    assert create_once == [f"{PROJECT}/{HANDLER}"]
    assert not [file.path for file in files if Path(file.path).name in LOCKFILES]


# trace: PRD-APP-017, PRD-TRACE-005
def test_each_source_file_has_the_trace_header() -> None:
    for path, content in files_in(GOLDEN / PROJECT).items():
        file_type = file_type_of(path)
        if path == HANDLER:
            assert not content.startswith(b"# Generated"), path
            continue
        if path == MODEL:
            elements = [ORDER]
        elif path.startswith(CUSTOM) or path == "tests/test_cancel_order_http_gen.py":
            elements = [CANCEL, ORDER, CANCEL_ORDER]
        elif path.startswith("app/features/order/") or path == "tests/test_orders_http_gen.py":
            elements = [ORDER, ORDERS]
        else:
            elements = [APP]
        assert content.decode().startswith(header(file_type, elements)), path


# trace: PRD-TRACE-006
def test_trace_manifest_gives_the_symbols_of_the_generated_files() -> None:
    data = json.loads((GOLDEN / ".dsml" / "trace.gen.json").read_bytes())
    assert [element["element"] for element in data["elements"]] == [
        CANCEL,
        ORDER,
        APP,
        CANCEL_ORDER,
        ORDERS,
    ]
    cancel, order, item, cancel_order, orders = data["elements"]
    custom_files = {
        f"{PROJECT}/{path}"
        for path in files_in(GOLDEN / PROJECT)
        if (path.startswith(CUSTOM) and path.endswith("_gen.py"))
        or path == "tests/test_cancel_order_http_gen.py"
    }
    slice_files = {
        f"{PROJECT}/{path}"
        for path in files_in(GOLDEN / PROJECT)
        if (path.startswith("app/features/") and path.endswith("_gen.py"))
        or path == "tests/test_orders_http_gen.py"
    } - custom_files
    assert {file["path"] for file in cancel["files"]} == custom_files
    assert {file["path"] for file in cancel_order["files"]} == custom_files
    assert {file["path"] for file in orders["files"]} == slice_files
    assert {file["path"] for file in order["files"]} == (
        slice_files | custom_files | {f"{PROJECT}/{MODEL}"}
    )
    assert (f"{PROJECT}/{MODEL}", "class", "Order") in {
        (file["path"], symbol["kind"], symbol["name"])
        for file in order["files"]
        for symbol in file["symbols"]
    }
    symbols = {
        (file["path"], symbol["kind"], symbol["name"])
        for file in item["files"]
        for symbol in file["symbols"]
    }
    assert {
        (f"{PROJECT}/app/main_gen.py", "route", "GET /healthz"),
        (f"{PROJECT}/app/main_gen.py", "function", "create_app"),
        (f"{PROJECT}/app/shared/auth/cognito_gen.py", "class", "TokenVerifier"),
        (f"{PROJECT}/app/shared/auth/cognito_gen.py", "function", "require_roles"),
        (f"{PROJECT}/app/shared/config_gen.py", "function", "load_settings"),
        (f"{PROJECT}/app/shared/errors_gen.py", "class", "ProblemError"),
        (f"{PROJECT}/app/shared/logs_gen.py", "function", "request_context"),
        (f"{PROJECT}/app/shared/db/session_gen.py", "function", "get_session"),
    } <= symbols
    python_files = {
        path
        for path in files_in(GOLDEN / PROJECT)
        if (
            path.endswith("_gen.py")
            and f"{PROJECT}/{path}" not in slice_files | custom_files
            and path != MODEL
        )
        or path == "migrations/env.py"
    }
    assert {file["path"] for file in item["files"]} == {
        f"{PROJECT}/{path}" for path in python_files
    }


# trace: PRD-APP-101, PRD-CORE-046
def test_pyproject_pins_the_versions_of_the_baseline() -> None:
    data = tomllib.loads((GOLDEN / PROJECT / "pyproject.toml").read_text())
    assert data["project"]["requires-python"] == "==3.14.*"
    assert data["project"]["dependencies"] == [
        f"alembic=={pinned_version('alembic')}",
        f"cryptography=={pinned_version('cryptography')}",
        f"fastapi=={pinned_version('fastapi')}",
        f"psycopg[binary]=={pinned_version('psycopg')}",
        f"pydantic=={pinned_version('pydantic')}",
        f"pyjwt=={pinned_version('pyjwt')}",
        f"sqlalchemy[asyncio]=={pinned_version('sqlalchemy')}",
        f"uvicorn=={pinned_version('uvicorn')}",
    ]
    assert data["dependency-groups"]["dev"] == [
        f"{name}=={pinned_version(name)}" for name in ("httpx2", "pyright", "pytest", "ruff")
    ]


# trace: PRD-CORE-031, PRD-CORE-046
def test_extra_dependencies_of_the_configuration_are_in_the_sorted_list(
    example_ir: Ir,
) -> None:
    text = CONFIGURATION + 'dependencies = ["structlog==25.4.0", "boto3==1.40.0"]\n'
    files = collect([FastApiGenerator()], example_ir, configuration(text), None)
    [pyproject] = [file for file in files if file.path == f"{PROJECT}/pyproject.toml"]
    data = tomllib.loads(pyproject.content.decode())
    assert data["project"]["dependencies"] == [
        f"alembic=={pinned_version('alembic')}",
        "boto3==1.40.0",
        f"cryptography=={pinned_version('cryptography')}",
        f"fastapi=={pinned_version('fastapi')}",
        f"psycopg[binary]=={pinned_version('psycopg')}",
        f"pydantic=={pinned_version('pydantic')}",
        f"pyjwt=={pinned_version('pyjwt')}",
        f"sqlalchemy[asyncio]=={pinned_version('sqlalchemy')}",
        "structlog==25.4.0",
        f"uvicorn=={pinned_version('uvicorn')}",
    ]


# trace: PRD-APP-013, PRD-APP-133
def test_dockerfile_uses_pinned_images_a_user_that_is_not_root_and_port_8000() -> None:
    text = (GOLDEN / PROJECT / "Dockerfile").read_text()
    baseline = load_baseline()
    python_image = baseline["python-image"].value
    uv_image = baseline["uv-image"].value
    assert python_image is not None and "@sha256:" in python_image
    assert uv_image is not None and "@sha256:" in uv_image
    froms = [line for line in text.splitlines() if line.startswith("FROM ")]
    assert froms == [
        f"FROM {uv_image} AS uv",
        f"FROM {python_image} AS build",
        f"FROM {python_image} AS runtime",
    ]
    assert "RUN uv sync --frozen --no-dev\n" in text
    assert "USER 10001\n" in text
    assert '"--port", "8000"' in text
    assert "EXPOSE 8000\n" in text


# trace: PRD-APP-010, PRD-APP-011, PRD-APP-132
def test_configuration_reads_each_variable_from_the_environment() -> None:
    text = (GOLDEN / PROJECT / "app" / "shared" / "config_gen.py").read_text()
    for variable in VARIABLES:
        assert f'"{variable.name}"' in text
    assert [variable.name for variable in VARIABLES if variable.mandatory] == [
        "APP_ENVIRONMENT",
        "AWS_REGION",
        "COGNITO_USER_POOL_ID",
        "COGNITO_APP_CLIENT_ID",
    ]
    for variable in DATABASE_VARIABLES:
        assert f'"{variable.name}"' in text


def test_application_with_no_output_folder_is_an_error(example_ir: Ir) -> None:
    with pytest.raises(ToolchainError, match=r"applications\.orderApi\.output"):
        collect([FastApiGenerator()], example_ir, configuration(""), None)


# trace: PRD-CORE-005
def test_run_of_an_other_part_gives_no_file_and_needs_no_output_folder(example_ir: Ir) -> None:
    assert collect([FastApiGenerator()], example_ir, configuration(""), {INFRASTRUCTURE}) == []


def test_application_of_an_other_target_gives_no_file() -> None:
    ir = Ir(elements=(application("web", "react"),))
    assert FastApiGenerator().generate(ir, configuration(""), None) == []


def test_output_folder_of_the_configuration_file() -> None:
    ir = Ir(elements=(application(),))
    files = FastApiGenerator().generate(
        ir, configuration('[applications.orderApi]\noutput = "."\n'), None
    )
    assert "app/main_gen.py" in {file.path for file in files}
    assert {file.part for file in files} == {"application/orderApi"}


# trace: PRD-TRACE-006
def test_python_symbols_give_classes_functions_and_routes() -> None:
    content = (
        b"import x\n"
        b"\n"
        b"\n"
        b"@router.get('/orders/{id}')\n"
        b"async def read_order() -> None:\n"
        b"    pass\n"
        b"\n"
        b"\n"
        b"class Order:\n"
        b"    pass\n"
        b"\n"
        b"\n"
        b"@decorator\n"
        b"def other() -> None: ...\n"
    )
    assert python_symbols(content, ("A",), {"Order": ("B",)}) == (
        Symbol(SymbolKind.ROUTE, "GET /orders/{id}", 4, 6, ("A",)),
        Symbol(SymbolKind.FUNCTION, "read_order", 4, 6, ("A",)),
        Symbol(SymbolKind.CLASS, "Order", 9, 10, ("B",)),
        Symbol(SymbolKind.FUNCTION, "other", 13, 14, ("A",)),
    )


def test_ignore_file_has_a_comment_header() -> None:
    assert file_type_of("services/a/.dockerignore") is FileType.IGNORE
    assert header(FileType.IGNORE, ["A"], "1.0.0") == (
        "# Generated by dsml 1. Do not edit.\n# Elements: A\n"
    )
