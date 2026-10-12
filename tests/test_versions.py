"""Tests of the version baseline."""

import json
from importlib import metadata
from pathlib import Path

import pytest

from dsml.versions import BaselineError, Pin, load_baseline, pinned_version


def test_package_baseline_pins_opensysml() -> None:
    baseline = load_baseline()
    assert baseline["opensysml"] == Pin(name="opensysml", line="0.9", version="0.9.2")
    assert pinned_version("opensysml") == "0.9.2"


def test_package_baseline_has_the_items_of_phases_1_and_2() -> None:
    assert set(load_baseline()) == {
        "action-checkout",
        "action-configure-aws-credentials",
        "action-setup-opentofu",
        "action-setup-uv",
        "action-upload-sarif",
        "actionlint",
        "actionlint-sha256",
        "alb-tls-policy",
        "alembic",
        "aws-amplify",
        "aws-amplify-adapter-nextjs",
        "aws-provider",
        "checkov",
        "class-variance-authority",
        "clsx",
        "cryptography",
        "drizzle-orm",
        "eslint",
        "eslint-js",
        "fastapi",
        "feature-sliced-steiger-plugin",
        "github-runner",
        "hcl-required-version",
        "httpx2",
        "jinja2",
        "next",
        "node",
        "opensysml",
        "opentofu",
        "opentofu-sha256",
        "pg",
        "pilot-kernel",
        "pilot-kernel-release",
        "pilot-kernel-sha256",
        "pnpm",
        "postgresql",
        "prettier",
        "psycopg",
        "pydantic",
        "pyjwt",
        "pyright",
        "pytest",
        "python",
        "python-image",
        "radix-ui-react-slot",
        "react",
        "react-dom",
        "ruff",
        "shadcn-ui",
        "shadcn-ui-commit",
        "sqlalchemy",
        "steiger",
        "steiger-toolkit",
        "sysml-grpc-sha256-darwin-arm64",
        "sysml-grpc-sha256-linux-amd64",
        "sysml-grpc-sha256-linux-arm64",
        "tailwind-merge",
        "tailwindcss",
        "tailwindcss-vite",
        "tanstack-react-form",
        "tanstack-react-query",
        "tanstack-react-router",
        "terraform",
        "terraform-sha256",
        "tflint",
        "tflint-ruleset-aws",
        "tflint-ruleset-aws-sha256",
        "tflint-sha256",
        "types-pg",
        "typescript",
        "typescript-eslint",
        "uv",
        "uv-image",
        "uvicorn",
        "vite",
        "vitejs-plugin-react",
        "vitest",
        "zod",
    }


def test_package_baseline_pins_jinja2() -> None:
    assert pinned_version("jinja2") == metadata.version("jinja2")


def test_package_baseline_python_line() -> None:
    assert load_baseline()["python"].line == "3.14"


def test_items_are_sorted_by_name() -> None:
    baseline = load_baseline('schema = 1\n[b]\nline = "1"\n[a]\nline = "2"\n')
    assert list(baseline) == ["a", "b"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('[a]\nline = "1"\n', "must have schema = 1"),
        ('schema = 2\n[a]\nline = "1"\n', "must have schema = 1"),
        ("schema = 1\n[a]\n", 'Item "a" must be a table'),
        ('schema = 1\na = "1"\n', 'Item "a" must be a table'),
        ('schema = 1\n[a]\nline = "1"\nlicense = "MIT"\n', "unknown key: license"),
        ('schema = 1\n[a]\nline = ""\n', 'key "line" of item "a" must be a text'),
        ("schema = 1\n[a]\nline = 1\n", 'key "line" of item "a" must be a text'),
        ('schema = 1\n[a]\nline = "1.2"\nversion = "1.3.0"\n', "is not in the line 1.2"),
        ('schema = 1\n[a]\nline = "1.2"\nversion = "1.20.0"\n', "is not in the line 1.2"),
    ],
)
def test_baseline_errors(text: str, message: str) -> None:
    with pytest.raises(BaselineError, match=message):
        load_baseline(text)


def test_version_in_line() -> None:
    baseline = load_baseline('schema = 1\n[a]\nline = "1.2"\nversion = "1.2.7"\n')
    assert pinned_version("a", baseline) == "1.2.7"


def test_pinned_version_errors() -> None:
    baseline = load_baseline('schema = 1\n[a]\nline = "1.2"\n')
    with pytest.raises(BaselineError, match='no exact version for item "a"'):
        pinned_version("a", baseline)
    with pytest.raises(BaselineError, match='no item "b"'):
        pinned_version("b", baseline)


# trace: PRD-IAC-003
def test_tflint_config_uses_the_aws_rule_set_of_the_baseline() -> None:
    config = (Path(__file__).resolve().parent.parent / ".tflint.hcl").read_text(encoding="utf-8")
    assert f'  version = "{pinned_version("tflint-ruleset-aws")}"\n' in config


ROOT = Path(__file__).resolve().parent.parent


def _baseline_item(package: str) -> str:
    """Give the baseline item name of an npm package."""
    return package.removeprefix("@").replace("/", "-")


# trace: PRD-APP-201, PRD-APP-301
def test_typescript_is_on_the_line_of_decision_record_09() -> None:
    assert load_baseline()["typescript"].line == "6.0"


@pytest.mark.parametrize(
    ("package", "item"),
    [
        ("@tanstack/react-router", "tanstack-react-router"),
        ("@feature-sliced/steiger-plugin", "feature-sliced-steiger-plugin"),
        ("typescript-eslint", "typescript-eslint"),
    ],
)
def test_baseline_item_of_npm_package(package: str, item: str) -> None:
    assert _baseline_item(package) == item


# trace: PRD-TOP-008, PRD-CORE-011
def test_package_json_uses_the_versions_of_the_baseline() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    dev_tools: dict[str, str] = package["devDependencies"]
    assert {"eslint", "prettier", "steiger", "typescript", "typescript-eslint"} <= set(dev_tools)
    for name, version in dev_tools.items():
        assert version == pinned_version(_baseline_item(name)), name
    assert package["packageManager"] == f"pnpm@{pinned_version('pnpm')}"
    assert package["devEngines"]["runtime"]["version"] == pinned_version("node")
