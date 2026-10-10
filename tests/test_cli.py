"""Tests of the command `dsml`."""

import subprocess
import sys
from importlib import metadata

import pytest

from dsml.cli import main


def test_version_writes_the_versions(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == 0
    captured = capsys.readouterr()
    assert captured.out == f"toolchain: {metadata.version('dsml')}\nOpenSysML: 0.9.2\n"
    assert captured.err == ""


@pytest.mark.parametrize("argv", [[], ["unknown"], ["version", "--unknown"], ["vers"]])
def test_usage_error_gives_exit_code_2(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(argv)
    assert error.value.code == 2


def test_python_module_runs_the_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "dsml", "version"],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.startswith("toolchain: ")
