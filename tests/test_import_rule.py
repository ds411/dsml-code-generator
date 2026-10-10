"""Tests of the import rule for opensysml (PRD-CORE-020)."""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

IMPORTS = [
    "import opensysml",
    "import opensysml.model",
    "from opensysml import Client",
    "from opensysml.model import Element",
]


def _ruff_check(source: str, file_name: str) -> subprocess.CompletedProcess[str]:
    """Run the lint rules of the project on one source text.

    The source text has only an import, so the check ignores F401
    (unused import).
    """
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--extend-ignore",
            "F401",
            "--stdin-filename",
            file_name,
            "-",
        ],
        input=source + "\n",
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )


# trace: PRD-CORE-020
@pytest.mark.parametrize("source", IMPORTS)
@pytest.mark.parametrize(
    "file_name", ["src/dsml/cli.py", "src/dsml/ir/model.py", "tests/test_x.py"]
)
def test_import_outside_the_adapter_fails(source: str, file_name: str) -> None:
    result = _ruff_check(source, file_name)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "TID251" in result.stdout


# trace: PRD-CORE-020
@pytest.mark.parametrize("source", IMPORTS)
@pytest.mark.parametrize("file_name", ["src/dsml/adapter/__init__.py", "src/dsml/adapter/read.py"])
def test_import_in_the_adapter_passes(source: str, file_name: str) -> None:
    result = _ruff_check(source, file_name)
    assert result.returncode == 0, result.stdout + result.stderr
