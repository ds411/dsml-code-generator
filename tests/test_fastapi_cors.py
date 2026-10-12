"""Tests of the calls across domains: CORS of the FastAPI target (story #164).

A FastAPI application that `react` applications call gets the CORS
middleware. It reads the permitted origins from `CORS_ALLOWED_ORIGINS`. The
container service module sets the variable to the site origins of the
calling applications in each environment (PRD-APP-136, Q66).

The golden files in `tests/golden/fastapi/order-portal/` are the output of
the FastAPI generator for the order portal model. The CI job "FastAPI golden
project" runs ruff, pyright and pytest on them. The generated tests show the
CORS headers for a permitted origin and no CORS headers for a different
origin. Write the golden files again with
`uv run python scripts/write_golden_fastapi.py`.
"""

import dataclasses
from pathlib import Path, PurePosixPath

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Configuration, parse_configuration
from dsml.generate.fastapi import CORS_VARIABLES, FastApiGenerator, react_callers
from dsml.generate.generators import collect
from dsml.generate.infrastructure.generator import InfrastructureGenerator
from dsml.generate.writer import apply_plan, make_plan
from dsml.ir.model import Element, Ir

ROOT = Path(__file__).resolve().parent.parent
PORTAL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
GOLDEN = ROOT / "tests" / "golden" / "fastapi" / "order-portal"
PROJECT = GOLDEN / "services" / "order-api"
CACHES = frozenset({".pytest_cache", ".ruff_cache", ".venv", "__pycache__"})
CONFIGURATION = '[applications.orderApi]\noutput = "services/order-api"\n'
ENVIRONMENTS = {
    "dev": "portal.dev.example.com",
    "prod": "portal.example.com",
    "staging": "portal.staging.example.com",
}


def _configuration() -> Configuration:
    return parse_configuration(f"schema = 1\n\n{CONFIGURATION}", Path("dsml.toml"))


def _files_in(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file() and not CACHES.intersection(path.parts)
    }


def _element(ir: Ir, identity: str) -> Element:
    return next(element for element in ir.elements if element.identity == identity)


@pytest.fixture(scope="module")
def portal_ir() -> Ir:
    return make_ir([PORTAL], ROOT)


# trace: PRD-CORE-030, PRD-APP-136
def test_output_of_the_order_portal_agrees_with_the_golden_files(
    portal_ir: Ir, tmp_path: Path
) -> None:
    files = collect([FastApiGenerator()], portal_ir, _configuration(), None)
    apply_plan(tmp_path, make_plan(tmp_path, files, None))
    assert _files_in(tmp_path) == _files_in(GOLDEN), (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_fastapi.py and examine the differences."
    )


# trace: PRD-APP-136
def test_react_callers_gives_the_react_applications_that_call(portal_ir: Ir) -> None:
    api = _element(portal_ir, "OrderPortal::orderApi")
    portal = _element(portal_ir, "OrderPortal::orderPortal")
    assert react_callers(portal_ir, api) == (portal,)
    assert react_callers(portal_ir, portal) == ()


# trace: PRD-APP-136
def test_application_with_no_react_caller_has_no_cors() -> None:
    ir = make_ir([EXAMPLE_MODEL], ROOT)
    api = _element(ir, "OrderService::orderApi")
    assert react_callers(ir, api) == ()
    files = collect([FastApiGenerator()], ir, _configuration(), None)
    for file in files:
        assert b"CORS" not in file.content, file.path


# trace: PRD-APP-136
def test_calls_link_from_an_application_that_is_not_react_gives_no_cors(portal_ir: Ir) -> None:
    links = tuple(
        dataclasses.replace(link, source="OrderPortal::apiService")
        if link.type == "calls"
        else link
        for link in portal_ir.links
    )
    ir = dataclasses.replace(portal_ir, links=links)
    assert react_callers(ir, _element(ir, "OrderPortal::orderApi")) == ()


# trace: PRD-APP-010, PRD-APP-136
def test_configuration_reads_the_origins_at_start() -> None:
    config = (PROJECT / "app/shared/config_gen.py").read_text(encoding="utf-8")
    variable = CORS_VARIABLES[0]
    assert f'{variable.field}=_mandatory(values, "{variable.name}")' in config
    assert "def allowed_origins(settings: Settings) -> tuple[str, ...]:" in config


# trace: PRD-APP-136
def test_middleware_permits_authorization_and_no_credentials() -> None:
    main = (PROJECT / "app/main_gen.py").read_text(encoding="utf-8")
    assert "from fastapi.middleware.cors import CORSMiddleware" in main
    assert "allow_origins=allowed_origins(settings)," in main
    assert "allow_credentials=False," in main
    assert '"Authorization"' in main
    tests = (PROJECT / "tests/test_app_gen.py").read_text(encoding="utf-8")
    assert "def test_permitted_origin_gets_the_cors_headers() -> None:" in tests
    assert "def test_other_origin_gets_no_cors_headers() -> None:" in tests


# trace: PRD-APP-136, PRD-IAC-015
@pytest.mark.parametrize("environment", sorted(ENVIRONMENTS))
def test_container_service_sets_the_site_origins(portal_ir: Ir, environment: str) -> None:
    output = InfrastructureGenerator().generate(
        portal_ir, Configuration(infrastructure=PurePosixPath("infra")), None
    )
    main = next(
        file.content.decode("utf-8")
        for file in output
        if file.path == f"infra/envs/{environment}/main.gen.tf"
    )
    call = main[main.index('module "api_service" {') :]
    call = call[: call.index("\n}\n")]
    origin = f"https://order-portal.{ENVIRONMENTS[environment]}"
    assert f'CORS_ALLOWED_ORIGINS  = "{origin}"' in call
