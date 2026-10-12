"""Tests of the toolchain package and of its release (story #141).

The tests build the wheel and the sdist with `uv build`, or use the files in
the folder of the environment variable `DSML_PACKAGE_DIR`. The release
workflow `.github/workflows/release.yml` sets this variable, so the tests
examine the files that the release attaches. The installation test uses the
network to get the dependencies from PyPI.
"""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from dsml.generate.pipelines.generator import ACTIONS
from dsml.generate.pipelines.workflow import pinned_action
from dsml.versions import load_baseline

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "dsml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_DOCUMENT = ROOT / "docs" / "release.md"
CHANGELOG = ROOT / "CHANGELOG.md"
EXAMPLE_CONFIG = ROOT / "docs" / "model" / "examples" / "dsml.toml"

VERSION: str = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
    "version"
]
WHEEL_NAME = f"dsml-{VERSION}-py3-none-any.whl"
SDIST_NAME = f"dsml-{VERSION}.tar.gz"
_USES = re.compile(r"^ +(?:- )?uses: (.+)$", flags=re.MULTILINE)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "release_notes", ROOT / "scripts" / "release_notes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release_notes: Any = _load_script()


def _uv() -> str:
    uv = shutil.which("uv")
    assert uv is not None, "The package tests need uv on PATH."
    return uv


def _environment(**values: str) -> dict[str, str]:
    """Give the environment of a uv command, without the project environment."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH"}
    }
    environment.update(values)
    return environment


@pytest.fixture(scope="module")
def package_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Give the folder with the wheel and the sdist."""
    given = os.environ.get("DSML_PACKAGE_DIR")
    if given:
        return Path(given)
    folder = tmp_path_factory.mktemp("dist")
    subprocess.run(
        [_uv(), "build", "--quiet", "--out-dir", str(folder)],
        cwd=ROOT,
        env=_environment(),
        check=True,
    )
    return folder


@pytest.fixture(scope="module")
def wheel_files(package_dir: Path) -> Iterator[set[str]]:
    with zipfile.ZipFile(package_dir / WHEEL_NAME) as wheel:
        yield set(wheel.namelist())


def _package_files(folder: Path, pattern: str) -> set[str]:
    """Give the files of `src/dsml/<folder>` with the names in the wheel."""
    return {
        path.relative_to(PACKAGE.parent).as_posix()
        for path in folder.rglob(pattern)
        if path.is_file() and "__pycache__" not in path.parts
    }


# trace: PRD-CORE-047, PRD-CORE-052
def test_build_gives_the_wheel_and_the_sdist_of_the_version(package_dir: Path) -> None:
    names = {path.name for path in package_dir.iterdir()}
    assert {WHEEL_NAME, SDIST_NAME} <= names
    assert release_notes.SEMANTIC_VERSION.fullmatch(VERSION)


# trace: PRD-CORE-048, PRD-DSML-006
def test_wheel_contains_the_dsml_library(wheel_files: set[str]) -> None:
    assert "dsml/library/DSML.sysml" in wheel_files
    assert _package_files(PACKAGE / "library", "*.sysml") <= wheel_files


# trace: PRD-CORE-048
def test_wheel_contains_the_ir_schema(wheel_files: set[str]) -> None:
    assert "dsml/ir/ir.schema.json" in wheel_files


# trace: PRD-CORE-048
def test_wheel_contains_the_templates(wheel_files: set[str]) -> None:
    templates = _package_files(PACKAGE / "templates", "*")
    assert templates, "src/dsml/templates has no file."
    assert templates <= wheel_files
    assert _package_files(PACKAGE / "starter", "*") <= wheel_files


# trace: PRD-CORE-047
def test_wheel_gives_the_command_dsml(package_dir: Path) -> None:
    with zipfile.ZipFile(package_dir / WHEEL_NAME) as wheel:
        entry_points = wheel.read(f"dsml-{VERSION}.dist-info/entry_points.txt").decode()
        metadata = wheel.read(f"dsml-{VERSION}.dist-info/METADATA").decode()
    assert "dsml = dsml.cli:main" in entry_points
    assert f"\nVersion: {VERSION}\n" in metadata


# trace: PRD-CORE-048, PRD-DSML-006
def test_sdist_contains_the_dsml_library_and_the_templates(package_dir: Path) -> None:
    with tarfile.open(package_dir / SDIST_NAME) as sdist:
        names = {name.removeprefix(f"dsml-{VERSION}/") for name in sdist.getnames()}
    assert "src/dsml/library/DSML.sysml" in names
    assert "src/dsml/ir/ir.schema.json" in names
    assert {f"src/{name}" for name in _package_files(PACKAGE / "templates", "*")} <= names


# trace: PRD-CORE-047, PRD-CORE-049, PRD-DSML-006
def test_uv_tool_install_gives_a_toolchain_that_validates_the_example(
    package_dir: Path, tmp_path: Path
) -> None:
    tools = tmp_path / "tools"
    bin_dir = tmp_path / "bin"
    environment = _environment(UV_TOOL_DIR=str(tools), UV_TOOL_BIN_DIR=str(bin_dir))
    subprocess.run(
        [_uv(), "tool", "install", "--quiet", "--python", "3.14", str(package_dir / WHEEL_NAME)],
        cwd=tmp_path,
        env=environment,
        check=True,
    )
    python = tools / "dsml" / "bin" / "python"
    dsml = bin_dir / "dsml"
    assert dsml.is_file()

    def run(*command: str | Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(part) for part in command],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )

    # Get sysml-grpc and check its SHA-256 hash (PRD-CORE-049).
    binary = run(python, "-m", "dsml.adapter.binary")
    assert binary.returncode == 0, binary.stderr
    assert "sysml-grpc: " in binary.stdout

    version = run(dsml, "version")
    assert version.returncode == 0, version.stderr
    assert f"toolchain: {VERSION}\n" in version.stdout

    # The library comes from the installed package, not from src/.
    location = run(python, "-c", "import dsml; print(dsml.__file__)")
    assert location.returncode == 0, location.stderr
    assert Path(location.stdout.strip()).is_relative_to(tools)

    validate = run(dsml, "validate", "--config", EXAMPLE_CONFIG)
    assert validate.returncode == 0, validate.stdout + validate.stderr


# trace: PRD-CORE-052
def test_changelog_has_notes_for_the_version() -> None:
    notes = release_notes.release_notes(CHANGELOG.read_text(encoding="utf-8"), VERSION)
    assert "### Changes to the generated output" in notes
    assert "ds411/dsml-code-generator@v<version>" in notes
    assert not notes.startswith("#")


# trace: PRD-CORE-052
def test_release_notes_stop_at_the_next_section() -> None:
    text = "# Changelog\n\n## 1.1.0\n\n- New.\n\n## 1.0.0\n\n- Old.\n"
    assert release_notes.release_notes(text, "1.1.0") == "- New.\n"
    assert release_notes.release_notes(text, "1.0.0") == "- Old.\n"


# trace: PRD-CORE-052
@pytest.mark.parametrize(
    ("text", "version", "message"),
    [
        ("## 1.0.0\n\n- Old.\n", "1.0", "not a semantic version"),
        ("## 1.0.0\n\n- Old.\n", "01.0.0", "not a semantic version"),
        ("## 1.0.0\n\n- Old.\n", "1.1.0", "no section"),
        ("## 1.0.0 (draft)\n\n- Old.\n", "1.0.0", "no section"),
        ("## 1.1.0\n\n## 1.0.0\n\n- Old.\n", "1.1.0", "is empty"),
    ],
)
def test_release_notes_reject_a_bad_version_or_section(
    text: str, version: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        release_notes.release_notes(text, version)


# trace: PRD-CORE-052
def test_release_notes_script_gives_exit_code_2_for_a_missing_section(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert release_notes.main(["99.0.0"]) == 2
    assert "no section '## 99.0.0'" in capsys.readouterr().err


# trace: PRD-CORE-047, PRD-CORE-052
def test_release_workflow_starts_on_a_semantic_version_tag() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert 'tags: ["v[0-9]+.[0-9]+.[0-9]+"]' in text
    assert "uv version --short" in text
    assert '"$TAG" != "v${version}"' in text
    assert "scripts/release_notes.py" in text


# trace: PRD-CORE-047
def test_release_workflow_attaches_the_wheel_and_the_sdist() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "uv build" in text
    assert "uv run pytest tests/test_package.py" in text
    assert "gh release create" in text
    assert '"$RUNNER_TEMP/dist/dsml-${VERSION}-py3-none-any.whl"' in text
    assert '"$RUNNER_TEMP/dist/dsml-${VERSION}.tar.gz"' in text
    # Q63: there is no package index.
    assert "--index" not in text
    assert "pypi" not in text.lower()


# trace: PRD-CICD-014
def test_release_workflow_pins_each_action_with_the_sha_of_the_baseline() -> None:
    baseline = load_baseline()
    pinned = {pinned_action(item, baseline).uses for item in ACTIONS.values()}
    uses = _USES.findall(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    assert {value.split("@")[0] for value in uses} == {"actions/checkout", "astral-sh/setup-uv"}
    for value in uses:
        assert value in pinned, value


def test_ci_runs_actionlint_on_the_release_workflow() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert '"$RUNNER_TEMP/actionlint" -color .github/workflows/release.yml' in text


def test_release_document_gives_the_steps_from_the_tag_to_the_installation() -> None:
    text = RELEASE_DOCUMENT.read_text(encoding="utf-8")
    assert "git tag" in text
    url = "https://github.com/ds411/dsml-code-generator/releases/download/v<version>/"
    assert f"uv tool install --python 3.14 {url}dsml-<version>-py3-none-any.whl" in text
    assert '"$(uv tool dir)/dsml/bin/python" -m dsml.adapter.binary' in text
