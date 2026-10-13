"""Tests of the MCP tools `init`, `validate` and `ir` (story #232).

An MCP client in the test process connects to the server and calls the
tools. Each test compares the result of a tool with the report of its
subcommand. The tests need the MCP Python SDK, so they have the mark `mcp`.
Some tests start a private `sysml-grpc` child process.
"""

import json
import shutil
from pathlib import Path
from typing import Any, get_args

import pytest

pytest.importorskip("mcp", reason="The MCP Python SDK is not installed.")

import anyio
from mcp import Client
from mcp_types import CallToolResult

from dsml import starter
from dsml.cli import main
from dsml.mcp import server, tools_model
from dsml.mcp.project import Project

pytestmark = pytest.mark.mcp

EXAMPLES = Path(__file__).parents[1] / "docs" / "model" / "examples"
"""The folder of the order service and its configuration file."""


def _call(root: Path, name: str, arguments: dict[str, Any]) -> CallToolResult:
    """Call one tool of a server in the project folder `root` with a client in this process."""

    async def call() -> CallToolResult:
        built = server.build_server(Project.open(root), "0.0.0")
        with anyio.fail_after(120):
            async with Client(built) as client:
                return await client.call_tool(name, arguments)

    return anyio.run(call)


def _result(root: Path, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call one tool and give its structured result. The call must not give an error."""
    result = _call(root, name, arguments)
    assert not result.is_error, result.content
    structured: dict[str, Any] = result.structured_content
    return structured


def _error(root: Path, name: str, arguments: dict[str, Any]) -> str:
    """Call one tool and give the text of its error. The call must give an error."""
    result = _call(root, name, arguments)
    assert result.is_error
    return " ".join(getattr(block, "text", "") for block in result.content)


def _cli(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    """Run the command `dsml` and give the exit code and the report."""
    capsys.readouterr()
    code = main(argv)
    return code, capsys.readouterr().out


def _files(folder: Path) -> dict[str, bytes]:
    """Give the bytes of each file in a folder and its subfolders, by relative path."""
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


@pytest.fixture
def examples(monkeypatch: pytest.MonkeyPatch) -> Path:
    """The folder of the order service as the project folder and the current folder."""
    monkeypatch.chdir(EXAMPLES)
    return EXAMPLES.resolve()


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty project folder, which is also the current folder."""
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.chdir(root)
    return root.resolve()


# trace: PRD-AI-011, PRD-AI-018
def test_server_has_the_model_tools_with_an_input_schema_and_a_description(
    tmp_path: Path,
) -> None:
    async def tools() -> dict[str, Any]:
        built = server.build_server(Project.open(tmp_path), "0.0.0")
        async with Client(built) as client:
            return {tool.name: tool for tool in (await client.list_tools()).tools}

    found = anyio.run(tools)
    assert {"init", "validate", "ir"} <= set(found)
    options = {
        "init": {"target", "config"},
        "validate": {"format", "fail_on", "baseline", "date", "config"},
        "ir": {"model", "config", "parts", "kinds", "names"},
    }
    for name, expected in options.items():
        tool = found[name]
        assert tool.description
        assert set(tool.input_schema["properties"]) == expected
        assert all("description" in schema for schema in tool.input_schema["properties"].values())
        assert tool.output_schema is not None
    assert get_args(tools_model.Target) == starter.TARGETS


# trace: PRD-AI-012, PRD-CORE-001
def test_validate_gives_the_same_findings_as_the_command(
    examples: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, report = _cli(["validate", "--format", "json"], capsys)
    result = _result(examples, "validate", {})
    assert result == {"exit_code": code, "report": json.loads(report)}
    assert result["report"]["findings"]


# trace: PRD-AI-012
@pytest.mark.parametrize(
    ("options", "arguments"),
    [
        (["--format", "text"], {"format": "text"}),
        (["--format", "sarif", "--fail-on", "warning"], {"format": "sarif", "fail_on": "warning"}),
    ],
)
def test_validate_gives_the_same_report_as_the_command_in_each_format(
    examples: Path,
    capsys: pytest.CaptureFixture[str],
    options: list[str],
    arguments: dict[str, Any],
) -> None:
    code, report = _cli(["validate", *options, "--config", "dsml.toml"], capsys)
    result = _result(examples, "validate", arguments | {"config": "dsml.toml"})
    expected = report if arguments["format"] == "text" else json.loads(report)
    assert result == {"exit_code": code, "report": expected}
    assert code == (1 if "fail_on" in arguments else 0)


# trace: PRD-AI-012, PRD-CORE-002
def test_validate_gives_an_error_for_a_usage_error_or_a_missing_file(examples: Path) -> None:
    assert '"2026-13-01" is not a date' in _error(examples, "validate", {"date": "2026-13-01"})
    assert "missing.toml" in _error(examples, "validate", {"config": "missing.toml"})


# trace: PRD-AI-012, PRD-CORE-028
def test_ir_gives_the_same_ir_as_the_command(
    examples: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, report = _cli(["ir"], capsys)
    assert _result(examples, "ir", {}) == {"exit_code": code, "report": json.loads(report)}
    code, report = _cli(["ir", "order-service.sysml"], capsys)
    result = _result(examples, "ir", {"model": ["order-service.sysml"]})
    assert result == {"exit_code": code, "report": json.loads(report)}


# trace: PRD-AI-011
def test_ir_gives_only_the_selected_parts_and_elements(
    examples: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    full = json.loads(_cli(["ir"], capsys)[1])
    report = _result(examples, "ir", {"parts": ["files"]})["report"]
    assert report == {"files": full["files"], "irVersion": full["irVersion"]}

    report = _result(examples, "ir", {"kinds": ["Need"], "parts": ["elements", "links"]})["report"]
    assert set(report) == {"elements", "irVersion", "links"}
    needs = [element for element in full["elements"] if element["kind"] == "Need"]
    assert report["elements"] == needs
    keys = {key for need in needs for key in (need["identity"], need["qualifiedName"])}
    assert report["links"]
    assert report["links"] == [
        link for link in full["links"] if link["source"] in keys or link["target"] in keys
    ]

    need = needs[0]
    for name in (need["identity"], need["name"], need["qualifiedName"]):
        assert _result(examples, "ir", {"names": [name]})["report"]["elements"] == [need]


# trace: PRD-AI-012, PRD-CORE-002
def test_ir_gives_exit_code_1_for_a_syntax_error(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (folder / "bad.sysml").write_text("package Bad {\n", encoding="utf-8")
    code, report = _cli(["ir", "bad.sysml"], capsys)
    assert code == 1
    result = _result(folder, "ir", {"model": ["bad.sysml"]})
    assert result == {"exit_code": 1, "report": json.loads(report)}


# trace: PRD-AI-012, PRD-AI-013, PRD-CORE-042, PRD-CORE-044
@pytest.mark.parametrize("target", starter.TARGETS)
def test_init_writes_the_same_files_as_the_command(
    folder: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    target: str,
) -> None:
    result = _result(folder, "init", {"target": target})
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    code, report = _cli(["init", "--target", target], capsys)
    assert result == {"exit_code": code, "report": report}
    assert report == "add dsml.toml\nadd model/model.sysml\n"
    assert _files(folder) == _files(other)


# trace: PRD-AI-013, PRD-CORE-042
def test_init_does_not_change_a_file_that_exists(folder: Path) -> None:
    (folder / "dsml.toml").write_text("# My configuration.\n", encoding="utf-8")
    result = _result(folder, "init", {})
    assert result["report"].splitlines() == [
        "keep dsml.toml: The file exists. The command did not change it.",
        "add model/model.sysml",
    ]
    files = _files(folder)
    assert files["dsml.toml"] == b"# My configuration.\n"
    assert _result(folder, "init", {})["report"].startswith("keep ")
    assert _files(folder) == files


# trace: PRD-AI-012
def test_init_writes_the_files_next_to_the_configuration_file(folder: Path) -> None:
    result = _result(folder, "init", {"config": "sub/my.toml"})
    assert result["report"] == "add sub/model/model.sysml\nadd sub/my.toml\n"
    assert set(_files(folder)) == {"sub/model/model.sysml", "sub/my.toml"}


# trace: PRD-AI-014
@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("init", {"config": "../outside/dsml.toml"}),
        ("init", {"config": "link/dsml.toml"}),
        ("validate", {"config": "../outside/dsml.toml"}),
        ("ir", {"config": "../outside/dsml.toml"}),
        ("ir", {"model": ["../outside/model.sysml"]}),
        ("ir", {"model": ["link/model.sysml"]}),
    ],
)
def test_a_path_outside_the_project_folder_gives_an_error_and_writes_no_file(
    folder: Path, name: str, arguments: dict[str, Any]
) -> None:
    outside = folder.parent / "outside"
    outside.mkdir()
    (outside / "dsml.toml").write_text('schema = 1\n[model]\npaths = ["model.sysml"]\n')
    (outside / "model.sysml").write_text("package Outside {}\n", encoding="utf-8")
    (folder / "link").symlink_to(outside)
    before = (_files(folder.parent), sorted(folder.parent.rglob("*")))
    assert "is not in the project folder" in _error(folder, name, arguments)
    assert (_files(folder.parent), sorted(folder.parent.rglob("*"))) == before


# trace: PRD-AI-014
def test_init_refuses_a_model_folder_outside_the_project_folder(folder: Path) -> None:
    outside = folder.parent / "outside"
    outside.mkdir()
    (folder / "model").symlink_to(outside)
    assert "is not in the project folder" in _error(folder, "init", {})
    assert not (folder / "dsml.toml").exists()
    assert not any(outside.iterdir())


# trace: PRD-AI-014
@pytest.mark.parametrize("name", ["validate", "ir"])
def test_a_model_path_outside_the_project_folder_gives_an_error(folder: Path, name: str) -> None:
    outside = folder.parent / "outside"
    outside.mkdir()
    shutil.copy(EXAMPLES / "order-service.sysml", outside / "order-service.sysml")
    (folder / "link").symlink_to(outside)
    (folder / "dsml.toml").write_text('schema = 1\n[model]\npaths = ["link"]\n', encoding="utf-8")
    assert "is not in the project folder" in _error(folder, name, {})


# trace: PRD-AI-014
def test_a_tool_refuses_a_current_folder_that_is_not_the_project_folder(
    folder: Path, tmp_path: Path
) -> None:
    other = tmp_path / "server"
    other.mkdir()
    assert "not the project folder" in _error(other, "init", {})
    assert not any(other.iterdir())
    assert not any(folder.iterdir())
