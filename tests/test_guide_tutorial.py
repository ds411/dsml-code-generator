"""Tests of the modeling tutorial of the user guide (story #238).

The tutorial page is `docs/guide/modeling-tutorial.md`. Its full model is in
`docs/guide/examples/tutorial/`. The tests make sure of these items:

- The `sysml` blocks of the page are the model files of the tutorial, in the
  order of the layers. The `toml` block of the page is its `dsml.toml`.
- The tutorial model validates with no error finding.
- `dsml generate` writes the files of the model. After the run,
  `dsml generate --check` finds no change, and the model has no finding.
- The paths of generated files that the page names exist after the run.
- The page shows the real output of `dsml validate` for the model without
  its `allocate` line.

`tests/test_user_guide.py` also validates the `sysml` blocks of the page.
These tests start a private `sysml-grpc` child process.
"""

import json
import re
import shutil
from pathlib import Path

import pytest

from dsml.cli import main

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "guide" / "modeling-tutorial.md"
TUTORIAL = ROOT / "docs" / "guide" / "examples" / "tutorial"
LAYERS = ("needs", "requirements", "application", "infrastructure", "verification")
"""The model files of the tutorial, in the order of the page."""

BLOCK = re.compile(r"^```([A-Za-z0-9_-]*)[^\n]*\n(.*?)^```$", re.MULTILINE | re.DOTALL)
OUTPUT_PATH = re.compile(r"`((?:services/loan-api|infra|\.dsml)/[^`<>\s]+)`")
ALLOCATE = "    allocate loanApi to apiService;\n"


def _blocks(language: str) -> list[str]:
    text = PAGE.read_text(encoding="utf-8")
    return [match.group(2) for match in BLOCK.finditer(text) if match.group(1) == language]


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Give a copy of the tutorial project, and make it the current folder."""
    folder = tmp_path / "library"
    shutil.copytree(TUTORIAL, folder)
    monkeypatch.chdir(folder)
    return folder


# trace: PRD-TOP-013
def test_the_sysml_blocks_of_the_page_are_the_files_of_the_tutorial_model() -> None:
    files = [(TUTORIAL / "model" / f"{name}.sysml").read_text(encoding="utf-8") for name in LAYERS]
    assert _blocks("sysml") == files
    assert sorted(path.name for path in (TUTORIAL / "model").iterdir()) == sorted(
        f"{name}.sysml" for name in LAYERS
    )


# trace: PRD-TOP-013
def test_the_toml_block_of_the_page_is_the_configuration_of_the_tutorial() -> None:
    assert _blocks("toml") == [(TUTORIAL / "dsml.toml").read_text(encoding="utf-8")]


# trace: PRD-TOP-013, PRD-TOP-011
def test_the_tutorial_model_validates_with_no_error_finding(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", "--format", "json"]) == 0
    findings = json.loads(capsys.readouterr().out)["findings"]
    # The test file of V-001 comes from `dsml generate`. Part 7 of the page tells about it.
    assert [(item["rule"], item["severity"]) for item in findings] == [("COV-006", "warning")]


# trace: PRD-TOP-013, PRD-CORE-042
def test_generate_and_generate_check_operate_on_the_tutorial_model(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = sorted(path for path in project.rglob("*"))
    assert main(["generate", "--check"]) == 1
    assert sorted(path for path in project.rglob("*")) == before

    assert main(["generate"]) == 0
    assert main(["generate", "--check"]) == 0
    capsys.readouterr()
    assert main(["validate", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["findings"] == []

    manifest = json.loads((project / ".dsml" / "generated.json").read_text(encoding="utf-8"))
    assert [item["path"] for item in manifest["createOnce"]] == [
        "services/loan-api/app/features/loan/return_book/handler.py"
    ]
    named = sorted(set(OUTPUT_PATH.findall(PAGE.read_text(encoding="utf-8"))))
    assert named
    assert [path for path in named if not (project / path).exists()] == []


# trace: PRD-TOP-013
def test_the_page_shows_the_finding_of_the_model_without_its_allocation(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    infrastructure = project / "model" / "infrastructure.sysml"
    text = infrastructure.read_text(encoding="utf-8")
    assert ALLOCATE in text
    infrastructure.write_text(text.replace(ALLOCATE, ""), encoding="utf-8")

    assert main(["validate"]) == 1
    output = capsys.readouterr().out
    shown = [block for block in _blocks("text") if " error: " in block]
    assert len(shown) == 1
    assert shown[0] in output
