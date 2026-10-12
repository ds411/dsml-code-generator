"""Tests of the infrastructure of a `nextjs` application (story #181).

The golden files in `tests/golden/infrastructure/order-web/` hold the full
output of the phase 3 reference model. These tests examine the values that
the requirements give. If a change of the output is correct, run
`uv run python scripts/write_golden_infrastructure.py`.
"""

import importlib.util
import re
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Configuration
from dsml.generate.infrastructure.generator import InfrastructureGenerator
from dsml.ir.model import Ir

ROOT = Path(__file__).resolve().parent.parent
ORDER_WEB = ROOT / "docs" / "model" / "examples" / "order-web" / "order-web.sysml"
ORDER_SERVICE = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
DOMAINS = {
    "dev": "web.dev.example.com",
    "prod": "web.example.com",
    "staging": "web.staging.example.com",
}
RUNTIME_VARIABLES = {
    "APP_ENVIRONMENT": "local.environment",
    "AWS_REGION": "local.aws_region",
    "COGNITO_APP_CLIENT_ID": 'module.users.app_client_ids["order_web"]',
    "COGNITO_LOGIN_DOMAIN": "module.users.login_domain",
    "COGNITO_USER_POOL_ID": "module.users.user_pool_id",
}
"""The environment variables of the root layout (PRD-APP-325) and of PRD-APP-010."""


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "write_golden_infrastructure", ROOT / "scripts/write_golden_infrastructure.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


write_golden: Any = _load_script()


def _generate(ir: Ir) -> dict[str, str]:
    output = InfrastructureGenerator().generate(
        ir, Configuration(infrastructure=PurePosixPath("infra")), None
    )
    return {file.path: file.content.decode("utf-8") for file in output}


@pytest.fixture(scope="module")
def files() -> dict[str, str]:
    return _generate(make_ir([ORDER_WEB], ROOT))


def _block(text: str, start: str) -> str:
    """Give the top-level block that starts with the line `start`."""
    lines = text.split("\n")
    first = lines.index(start)
    last = lines.index("}", first)
    return "\n".join(lines[first : last + 1])


def _flat(text: str) -> str:
    """Give the text with one space before each "="."""
    return re.sub(r" +=", " =", text)


def _call(files: dict[str, str], environment: str, address: str) -> str:
    text = files[f"infra/envs/{environment}/main.gen.tf"]
    return _flat(_block(text, f'module "{address}" {{'))


# trace: PRD-CORE-030, PRD-IAC-001, PRD-IAC-012
def test_output_of_the_order_web_agrees_with_the_golden_files(tmp_path: Path) -> None:
    output = write_golden.generate("order-web", tmp_path)
    golden = write_golden.read_tree(write_golden.golden_folder("order-web"))
    assert sorted(output) == sorted(golden)
    for path, content in golden.items():
        assert output[path] == content, path


# trace: PRD-IAC-012, PRD-IAC-014, PRD-APP-333
@pytest.mark.parametrize("environment", sorted(DOMAINS))
def test_service_of_a_nextjs_application_listens_on_port_3000(
    files: dict[str, str], environment: str
) -> None:
    call = _call(files, environment, "web_service")
    assert "  container_port = 3000\n" in call
    assert f'  domain_name = "order-web.{DOMAINS[environment]}"\n' in call


# trace: PRD-IAC-016, PRD-APP-332
@pytest.mark.parametrize("environment", sorted(DOMAINS))
def test_migration_command_of_a_nextjs_application_is_node_migrate(
    files: dict[str, str], environment: str
) -> None:
    call = _call(files, environment, "web_service")
    assert '  migration_command = ["node", "migrate.gen.mjs"]\n' in call
    assert f'migration_family = "order-web-{environment}-web-service-migrate"' in call


# trace: PRD-IAC-015, PRD-APP-010, PRD-APP-325
@pytest.mark.parametrize("environment", sorted(DOMAINS))
def test_service_of_a_nextjs_application_gets_the_public_runtime_values(
    files: dict[str, str], environment: str
) -> None:
    call = _call(files, environment, "web_service")
    for name, value in RUNTIME_VARIABLES.items():
        assert f"    {name} = {value}\n" in call, name
    assert "NEXT_PUBLIC_" not in call


# trace: PRD-IAC-015, PRD-APP-010
def test_service_of_a_fastapi_application_gets_no_login_domain() -> None:
    files = _generate(make_ir([ORDER_SERVICE], ROOT))
    for environment in DOMAINS:
        assert "COGNITO_LOGIN_DOMAIN" not in files[f"infra/envs/{environment}/main.gen.tf"]


# trace: PRD-IAC-019
@pytest.mark.parametrize("environment", sorted(DOMAINS))
def test_app_client_of_a_nextjs_application_is_on_its_application_domain(
    files: dict[str, str], environment: str
) -> None:
    call = _call(files, environment, "users")
    host = f"https://order-web.{DOMAINS[environment]}"
    assert f'callback_urls = ["{host}/auth/callback"]' in call
    assert f'logout_urls = ["{host}/"]' in call


# trace: PRD-IAC-009, PRD-IAC-022
def test_tooling_root_module_has_the_ecr_repository_of_the_application(
    files: dict[str, str],
) -> None:
    tooling = _flat(files["infra/tooling/main.gen.tf"])
    assert 'resource "aws_ecr_repository" "order_web" {' in tooling
    assert 'name = "order-web-tooling-order-web"' in tooling
    for environment in DOMAINS:
        variables = files[f"infra/envs/{environment}/variables.gen.tf"]
        assert 'variable "order_web_image_digest" {' in variables
