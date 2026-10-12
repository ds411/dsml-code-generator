"""Tests of the MCP tools `generate`, `check_output`, `trace` and `version` (story #233).

An MCP client in the test process calls each tool. The tests compare the
result of the tool with the result of its subcommand for the same model and
configuration (PRD-AI-012). The tests need the MCP Python SDK, in the
optional dependency group `mcp`. Without the SDK, the tests are skipped.
"""

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("mcp")

import anyio
from mcp import Client

from dsml.mcp.project import Project
from dsml.mcp.server import build_server

pytestmark = pytest.mark.mcp

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.orderApi]
output = "services/order-api"

[infrastructure]
output = "infra"

[pipelines]
output = ".github/workflows"
"""
"""The configuration of the order service: all generators of phase 1 write output."""
DATE = "2026-10-12"
"""The date of the expiry check of the waivers. It makes the runs independent of Git."""
GIT = ("git", "-c", "user.name=Test", "-c", "user.email=test@example.com")


def order_service(folder: Path) -> Path:
    """Write a project folder with the order service model and the configuration."""
    (folder / "model").mkdir(parents=True)
    shutil.copyfile(EXAMPLE_MODEL, folder / "model" / "order-service.sysml")
    (folder / "dsml.toml").write_text(CONFIGURATION, encoding="utf-8", newline="\n")
    return folder


def run_cli(project: Path, *argv: str) -> tuple[int, bytes, list[str]]:
    """Run the command `dsml` in a subprocess. Give the exit code, the output and the messages."""
    result = subprocess.run(
        [sys.executable, "-m", "dsml", *argv], cwd=project, capture_output=True, check=False
    )
    return result.returncode, result.stdout, result.stderr.decode().splitlines()


def call(project: Path, tool: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Call one MCP tool of the server of `project`. Give the structured result."""

    async def run() -> dict[str, Any]:
        server = build_server(Project.open(project), "0.0.0")
        with anyio.fail_after(120):
            async with Client(server) as client:
                result = await client.call_tool(tool, dict(arguments or {}))
        assert not result.is_error, result.content
        assert result.structured_content is not None
        return result.structured_content

    return anyio.run(run)


def call_error(project: Path, tool: str, arguments: Mapping[str, Any]) -> str:
    """Call one MCP tool that must fail. Give the text of the error."""

    async def run() -> str:
        server = build_server(Project.open(project), "0.0.0")
        async with Client(server) as client:
            result = await client.call_tool(tool, dict(arguments))
        assert result.is_error
        return "".join(getattr(item, "text", "") for item in result.content)

    return anyio.run(run)


def files_in(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(folder).parts
    }


def lines_of(changes: list[dict[str, str]]) -> bytes:
    return "".join(f"{change['action']} {change['path']}\n" for change in changes).encode()


# trace: PRD-AI-011, PRD-AI-012, PRD-CORE-004
def test_generate_check_gives_the_list_of_dsml_generate_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = order_service(tmp_path / "project")
    monkeypatch.chdir(project)
    code, out, err = run_cli(project, "generate", "--check", f"--date={DATE}")
    result = call(project, "generate", {"check": True, "date": DATE})
    assert (result["exit_code"], lines_of(result["changes"]), result["messages"]) == (
        code,
        out,
        err,
    )
    assert code == 1
    assert {"action": "add", "path": "services/order-api/app/main_gen.py"} in result["changes"]
    assert files_in(project) == files_in(order_service(tmp_path / "empty"))


# trace: PRD-AI-012, PRD-AI-013, PRD-CORE-005
def test_generate_with_an_option_gives_the_list_of_the_subcommand(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = order_service(tmp_path / "project")
    monkeypatch.chdir(project)
    code, out, err = run_cli(project, "generate", "--check", "--pipelines", f"--date={DATE}")
    result = call(project, "generate", {"check": True, "pipelines": True, "date": DATE})
    assert (result["exit_code"], lines_of(result["changes"]), result["messages"]) == (
        code,
        out,
        err,
    )
    code, out, err = run_cli(project, "generate", "--application=unknown", f"--date={DATE}")
    result = call(project, "generate", {"application": "unknown", "date": DATE})
    assert (result["exit_code"], result["changes"], result["messages"]) == (2, [], err)
    assert (code, out) == (2, b"")


# trace: PRD-AI-012, PRD-AI-013, PRD-CORE-042, PRD-CORE-043
def test_generate_writes_the_bytes_of_dsml_generate_and_stops_on_a_changed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference = order_service(tmp_path / "reference")
    code, out, _ = run_cli(reference, "generate", f"--date={DATE}")
    assert code == 0
    project = order_service(tmp_path / "project")
    monkeypatch.chdir(project)
    result = call(project, "generate", {"date": DATE})
    assert (result["exit_code"], lines_of(result["changes"]), result["messages"]) == (0, out, [])
    assert files_in(project) == files_in(reference)

    changed = project / "services" / "order-api" / "app" / "main_gen.py"
    changed.write_bytes(changed.read_bytes() + b"# A hand change.\n")
    (project / "services" / "order-api" / "notes.md").write_text("Hand-written.\n")
    before = files_in(project)
    code, out, err = run_cli(project, "generate", f"--date={DATE}")
    result = call(project, "generate", {"date": DATE})
    assert (result["exit_code"], lines_of(result["changes"]), result["messages"]) == (
        code,
        out,
        err,
    )
    assert code == 1
    assert (
        "dsml: error: services/order-api/app/main_gen.py: "
        "The file is different from its hash in the manifest."
    ) in result["messages"]
    assert files_in(project) == before


# trace: PRD-AI-011
def test_generate_has_no_overwrite_option(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def schema() -> dict[str, Any]:
        server = build_server(Project.open(tmp_path), "0.0.0")
        async with Client(server) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        return tools["generate"].input_schema

    properties = anyio.run(schema)["properties"]
    assert sorted(properties) == [
        "application",
        "check",
        "config",
        "date",
        "infrastructure",
        "pipelines",
    ]


# trace: PRD-AI-012, PRD-TRACE-010, PRD-TRACE-013, PRD-TRACE-016, PRD-TRACE-018
def test_trace_gives_the_report_of_dsml_trace_for_each_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = order_service(tmp_path / "project")
    monkeypatch.chdir(project)
    assert run_cli(project, "generate", f"--date={DATE}")[0] == 0
    subprocess.run(["git", "init", "--quiet"], cwd=project, check=True)
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run([*GIT, "commit", "--quiet", "-m", "Model"], cwd=project, check=True)
    for report in ("coverage", "orphans"):
        code, out, err = run_cli(project, "trace", report, "--format", "json")
        result = call(project, "trace", {"report": report})
        assert (result["exit_code"], result["report"].encode(), result["messages"]) == (
            code,
            out,
            err,
        )
        assert code == 0
    for report in ("impact", "suspect"):
        code, out, err = run_cli(project, "trace", report, "--format", "json", "--baseline", "HEAD")
        result = call(project, "trace", {"report": report, "baseline": "HEAD"})
        assert (result["exit_code"], result["report"].encode(), result["messages"]) == (
            code,
            out,
            err,
        )
        assert code == 0
    code, out, err = run_cli(project, "trace", "coverage", "--format", "csv")
    result = call(project, "trace", {"report": "coverage", "format": "csv"})
    assert (result["exit_code"], result["report"].encode(), result["messages"]) == (code, out, err)


# trace: PRD-AI-012, PRD-CORE-001
def test_version_gives_the_versions_of_dsml_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out, _ = run_cli(tmp_path, "version")
    result = call(tmp_path, "version")
    assert code == 0
    assert out.decode() == (
        f"toolchain: {result['toolchain']}\n"
        f"DSML library: {result['dsml_library']}\n"
        f"OpenSysML: {result['opensysml']}\n"
        f"IR schema: {result['ir_schema']}\n"
    )


FAKE_TOOL = """#!/bin/sh
name="${0##*/}-$1"
case " $FAKE_FAIL " in
  *" $name "*) printf '%s found an error\\n\\nline 3\\n' "$name"; exit 1 ;;
esac
if [ "$name" = "tofu-init" ]; then mkdir -p .terraform; fi
exit 0
"""


# trace: PRD-AI-012, PRD-CORE-011
def test_check_output_gives_each_problem_as_structured_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = order_service(tmp_path / "project")
    monkeypatch.chdir(project)
    assert run_cli(project, "generate", "--infrastructure", f"--date={DATE}")[0] == 0
    bin_folder = tmp_path / "bin"
    bin_folder.mkdir()
    for tool in ("tflint", "tofu"):
        (bin_folder / tool).write_text(FAKE_TOOL, encoding="utf-8")
        (bin_folder / tool).chmod(0o755)
    environment = {**os.environ, "PATH": str(bin_folder), "FAKE_FAIL": "tofu-init"}
    monkeypatch.setenv("PATH", environment["PATH"])
    monkeypatch.setenv("FAKE_FAIL", environment["FAKE_FAIL"])
    before = files_in(project)
    cli = subprocess.run(
        [sys.executable, "-m", "dsml", "check-output", "--infrastructure"],
        cwd=project,
        env=environment,
        capture_output=True,
        check=False,
    )
    result = call(project, "check_output", {"infrastructure": True})
    assert (result["exit_code"], result["messages"]) == (cli.returncode, [])
    assert cli.returncode == 1
    report: list[str] = []
    for step in result["steps"]:
        report.append(f"{step['status']} {step['target']}: {step['tool']}")
        report.extend(f"    {line}".rstrip() for line in step["output"])
    report.append(result["summary"])
    assert "".join(f"{line}\n" for line in report) == cli.stdout.decode()
    failed = [step for step in result["steps"] if step["status"] == "error"]
    assert failed
    assert {step["tool"] for step in failed} == {"tofu init"}
    assert failed[0]["output"] == ["tofu-init found an error", "", "line 3"]
    assert {step["status"] for step in result["steps"]} == {"pass", "error", "not run"}
    assert files_in(project) == before


# trace: PRD-AI-014
def test_tools_refuse_a_configuration_file_outside_the_project_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = order_service(tmp_path / "project")
    monkeypatch.chdir(project)
    for tool, arguments in (
        ("generate", {"config": "../dsml.toml"}),
        ("check_output", {"config": str(tmp_path / "dsml.toml")}),
        ("trace", {"report": "coverage", "config": "../other/dsml.toml"}),
    ):
        assert "is not in the project folder." in call_error(project, tool, arguments)
    assert files_in(project) == files_in(order_service(tmp_path / "empty"))


# trace: PRD-AI-014
def test_tools_operate_only_in_the_project_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = order_service(tmp_path / "project")
    monkeypatch.chdir(tmp_path)
    before = files_in(tmp_path)
    message = call_error(project, "generate", {"date": DATE})
    assert "The current folder of the server is not the project folder." in message
    assert files_in(tmp_path) == before
