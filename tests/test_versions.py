"""Tests of the version baseline."""

from importlib import metadata

import pytest

from dsml.versions import BaselineError, Pin, load_baseline, pinned_version


def test_package_baseline_pins_opensysml() -> None:
    baseline = load_baseline()
    assert baseline["opensysml"] == Pin(name="opensysml", line="0.9", version="0.9.2")
    assert pinned_version("opensysml") == "0.9.2"


def test_package_baseline_has_the_phase_1_items() -> None:
    assert set(load_baseline()) == {
        "alb-tls-policy",
        "alembic",
        "aws-provider",
        "checkov",
        "fastapi",
        "github-runner",
        "hcl-required-version",
        "httpx2",
        "jinja2",
        "opensysml",
        "opentofu",
        "pilot-kernel",
        "pilot-kernel-release",
        "pilot-kernel-sha256",
        "postgresql",
        "psycopg",
        "pydantic",
        "pyright",
        "pytest",
        "python",
        "python-image",
        "ruff",
        "sqlalchemy",
        "terraform",
        "uv",
        "uv-image",
        "uvicorn",
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
