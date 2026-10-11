"""Tests of the command `dsml` (stories #2, #34 and #38)."""

import argparse
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import pytest

from dsml import cli
from dsml.cli import Outcome, main
from dsml.errors import NOT_AVAILABLE, ToolchainError

SUBCOMMANDS = ("init", "validate", "generate", "trace", "ir", "check-output", "version")
NOT_AVAILABLE_ARGV = [
    ["validate"],
    ["validate", "--format", "sarif", "--baseline", "v1.0.0"],
    ["trace", "coverage"],
    ["trace", "impact", "--format", "csv", "--baseline", "v1.0.0"],
    ["check-output"],
    ["check-output", "--application", "orders", "--infrastructure"],
]
VERSION_TEXT = (
    f"toolchain: {metadata.version('dsml')}\n"
    "DSML library: 1.0.0\n"
    "OpenSysML: 0.9.2\n"
    "IR schema: 1.0.0\n"
)


def test_version_writes_the_versions(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == 0
    captured = capsys.readouterr()
    assert captured.out == VERSION_TEXT
    assert captured.err == ""


def test_help_lists_the_seven_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        main(["--help"])
    assert stop.value.code == 0
    out = capsys.readouterr().out
    listed = [line.split()[0] for line in out.splitlines() if re.match(r"    \S", line)]
    assert sorted(listed) == sorted(SUBCOMMANDS)


@pytest.mark.parametrize("command", SUBCOMMANDS)
def test_each_subcommand_has_the_common_options(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as stop:
        main([command, "--help"])
    assert stop.value.code == 0
    out = capsys.readouterr().out
    for option in ("--config", "--output", "--verbose"):
        assert option in out


@pytest.mark.parametrize("argv", NOT_AVAILABLE_ARGV)
def test_subcommand_with_no_implementation_gives_exit_code_2(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"dsml: error: {NOT_AVAILABLE}\n"


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["unknown"],
        ["vers"],
        ["version", "--unknown"],
        ["validate", "--format", "xml"],
        ["trace"],
        ["trace", "unknown"],
        ["init", "--target"],
        ["init", "--target", "react"],
    ],
)
def test_usage_error_gives_exit_code_2(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("usage: dsml")
    assert "\ndsml: error: " in captured.err
    assert "Traceback" not in captured.err


def test_toolchain_error_gives_exit_code_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(args: argparse.Namespace) -> Outcome:
        raise ToolchainError("The model has no file.")

    monkeypatch.setitem(cli.HANDLERS, "validate", fail)
    assert main(["validate"]) == 2
    assert capsys.readouterr().err == "dsml: error: The model has no file.\n"


def test_internal_error_gives_exit_code_2_and_no_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(args: argparse.Namespace) -> Outcome:
        raise RuntimeError("The data is not correct")

    monkeypatch.setitem(cli.HANDLERS, "validate", fail)
    assert main(["validate"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "dsml: error: An internal error occurred: RuntimeError: The data is not correct\n"
    )


def test_verbose_internal_error_writes_the_traceback_as_debug_messages(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(args: argparse.Namespace) -> Outcome:
        raise RuntimeError("The data is not correct")

    monkeypatch.setitem(cli.HANDLERS, "validate", fail)
    assert main(["validate", "--verbose"]) == 2
    err = capsys.readouterr().err
    assert "dsml: debug: Traceback of the internal error:\nTraceback " in err
    assert err.endswith(
        "dsml: error: An internal error occurred: RuntimeError: The data is not correct\n"
    )


@pytest.mark.parametrize("outcome", list(Outcome))
def test_outcome_gives_its_exit_code(outcome: Outcome, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(cli.HANDLERS, "validate", lambda args: outcome)
    assert main(["validate"]) == outcome.value


def test_exit_codes_agree_with_prd_core_002() -> None:
    assert [Outcome.SUCCESS, Outcome.ERROR_FINDING, Outcome.FAILURE] == [0, 1, 2]


def test_output_writes_the_report_to_a_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "versions.txt"
    assert main(["version", "--output", str(report)]) == 0
    assert capsys.readouterr().out == ""
    assert report.read_bytes() == VERSION_TEXT.encode("utf-8")


def test_output_that_cannot_be_written_gives_exit_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "missing" / "versions.txt"
    assert main(["version", "--output", str(report)]) == 2
    err = capsys.readouterr().err
    assert err.startswith(f"dsml: error: Cannot write the file {report}: ")


def test_verbose_writes_debug_messages_to_standard_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["version", "--verbose", "--config", "other.toml"]) == 0
    captured = capsys.readouterr()
    assert captured.out == VERSION_TEXT
    assert captured.err == (
        "dsml: debug: Subcommand: version.\ndsml: debug: Configuration file: other.toml.\n"
    )


def test_no_verbose_writes_no_debug_messages(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == 0
    assert main(["version", "--verbose"]) == 0
    assert main(["version"]) == 0
    err = capsys.readouterr().err
    assert err.count("dsml: debug: Subcommand: version.") == 1


def test_config_default_is_dsml_toml(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version", "--verbose"]) == 0
    assert "dsml: debug: Configuration file: dsml.toml.\n" in capsys.readouterr().err


def test_python_module_runs_the_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "dsml", "version"],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout == VERSION_TEXT


@pytest.mark.parametrize("command", SUBCOMMANDS)
def test_no_subcommand_waits_for_terminal_input(command: str, tmp_path: Path) -> None:
    """Standard input stays open and gets no data.

    A subcommand that reads standard input waits until the timeout, and the
    test fails.
    """
    argv = [command, "coverage"] if command == "trace" else [command]
    if command == "ir":
        (tmp_path / "model.sysml").write_text("package Model;\n", encoding="utf-8")
        argv = [command, "model.sysml"]
    if command == "init":
        argv = [command]
    if command == "generate":
        (tmp_path / "model.sysml").write_text("package Model;\n", encoding="utf-8")
        (tmp_path / "dsml.toml").write_text(
            'schema = 1\n\n[model]\npaths = ["model.sysml"]\n', encoding="utf-8"
        )
    with subprocess.Popen(
        [sys.executable, "-m", "dsml", *argv],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
    ) as process:
        try:
            returncode = process.wait(timeout=60)
        finally:
            process.kill()
        assert process.stdout is not None
        assert process.stderr is not None
        out = process.stdout.read().decode("utf-8")
        err = process.stderr.read().decode("utf-8")
    if command == "version":
        assert (returncode, out, err) == (0, VERSION_TEXT, "")
    elif command == "ir":
        assert (returncode, err) == (0, "")
        assert '"files": [\n    "model.sysml"\n  ]' in out
    elif command == "generate":
        manifests = "add .dsml/generated.json\nadd .dsml/trace.gen.json\n"
        assert (returncode, out, err) == (0, manifests, "")
    elif command == "init":
        assert (returncode, out, err) == (0, "add dsml.toml\nadd model/model.sysml\n", "")
    else:
        assert (returncode, out, err) == (2, "", f"dsml: error: {NOT_AVAILABLE}\n")
