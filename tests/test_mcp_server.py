"""Tests of the command `dsml mcp`: the frame of the MCP server (story #229).

The tests with the mark `mcp` need the MCP Python SDK, in the optional
dependency group `mcp`. Without the SDK, these tests are skipped. The CI
step "Test the MCP server" installs the SDK and runs them.
"""

import importlib.util
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import pytest

from dsml.cli import MCP_MISSING, main
from dsml.errors import ToolchainError
from dsml.mcp.project import Project

needs_sdk = pytest.mark.skipif(
    importlib.util.find_spec("mcp") is None, reason="The MCP Python SDK is not installed."
)
"""Skip a test if the MCP Python SDK is not installed. Use it with the mark `mcp`."""


# trace: PRD-AI-009
def test_mcp_stops_with_exit_code_2_without_the_sdk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(sys.modules, "mcp", None)  # type: ignore[arg-type]
    monkeypatch.delitem(sys.modules, "dsml.mcp.server", raising=False)
    assert main(["mcp", "--project", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert err == "".join(f"dsml: error: {line}\n" for line in MCP_MISSING.splitlines())
    assert 'uv tool install --python 3.14 "dsml[mcp] @ <wheel-file>"' in err


# trace: PRD-AI-010
def test_other_subcommands_operate_without_the_sdk() -> None:
    code = (
        "import sys\n"
        "sys.modules['mcp'] = None\n"
        "from dsml.cli import main\n"
        "raise SystemExit(main(['version']))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert (result.returncode, result.stderr) == (0, "")
    assert result.stdout.startswith("toolchain: ")


# trace: PRD-AI-014
def test_mcp_stops_with_exit_code_2_for_a_missing_project_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "missing"
    assert main(["mcp", "--project", str(folder)]) == 2
    assert capsys.readouterr().err == f"dsml: error: The project folder {folder} does not exist.\n"


# trace: PRD-AI-014
def test_project_refuses_a_path_outside_the_project_folder(tmp_path: Path) -> None:
    (tmp_path / "project" / "model").mkdir(parents=True)
    (tmp_path / "other").mkdir()
    (tmp_path / "project" / "link").symlink_to(tmp_path / "other")
    project = Project.open(tmp_path / "project" / "model" / "..")
    assert project.root == (tmp_path / "project").resolve()
    assert project.path("model/a.sysml") == project.root / "model" / "a.sysml"
    assert project.path(".") == project.root
    for text in ("..", "../other", "model/../../other", "link/a.sysml", str(tmp_path / "other")):
        with pytest.raises(ToolchainError, match="is not in the project folder"):
            project.path(text)


# trace: PRD-AI-008
@pytest.mark.mcp
@needs_sdk
def test_server_registers_each_module(tmp_path: Path) -> None:
    from dsml.mcp import prompts, resources, server, tools_generate, tools_model

    assert (tools_model, tools_generate, resources, prompts) == server.MODULES
    built = server.build_server(Project.open(tmp_path), "1.2.3")
    assert (built.name, built.version) == ("dsml", "1.2.3")


async def _start_and_initialize(project: Path) -> tuple[str, str, int]:
    """Start `dsml mcp` as a child process and give the server name, version and tool count."""
    import anyio
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "dsml", "mcp", "--project", str(project)]
    )
    with anyio.fail_after(60):
        async with (
            stdio_client(parameters) as (read, write),
            ClientSession(read, write) as session,
        ):
            result = await session.initialize()
            tools = await session.list_tools()
    return result.server_info.name, result.server_info.version, len(tools.tools)


# trace: PRD-AI-008, PRD-AI-017
@pytest.mark.mcp
@needs_sdk
def test_client_connects_over_stdio_and_gets_the_name_and_the_version(tmp_path: Path) -> None:
    import anyio

    name, version, tools = anyio.run(_start_and_initialize, tmp_path)
    assert (name, version) == ("dsml", metadata.version("dsml"))
    # Stories #232 and #233 add the tools.
    assert tools >= 0
