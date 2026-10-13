"""End-to-end test of the MCP server through the stdio transport (story #236).

The test starts `dsml mcp` as a child process in a temporary project folder.
An MCP client in the test process does the full work cycle of an AI agent:

1. Call `init`.
2. Copy the order service model into the folder.
3. Call `validate`, `ir`, `generate`, `trace` and `version`.

The test compares each result with the result of the CLI for the same folder
(PRD-AI-012). A write step (`init`, `generate`) runs the CLI in a second
folder with the same files, and the test compares the two folders.

A small launcher starts the server with a Python audit hook. The hook
records each socket event and each file write of the server process. On
Linux, a thread of the test also reads the sockets of the server process
from `/proc`. The tests then make sure that the server opens no network
socket and writes no file outside the project folder (PRD-AI-014,
PRD-AI-017). The OpenSysML child process is permitted: the toolchain
connects to it through the loopback interface (PRD-TOP-005).

The tests need the MCP Python SDK, so they have the mark `mcp`. The CI step
"Test the MCP server" runs them.
"""

import ipaddress
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("mcp", reason="The MCP Python SDK is not installed.")

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from dsml.adapter.binary import fetch_binary

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

LAUNCHER = """\
import os
import sys

log = open(sys.argv[1], "w", encoding="utf-8", buffering=1)
log.write(f"pid {os.getpid()}\\n")
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC


def hook(event, args):
    if event == "socket.getaddrinfo":
        log.write(f"{event} {args!r}\\n")
    elif event in ("socket.__new__", "socket.bind", "socket.connect", "socket.sendto",
                   "socket.sendmsg"):
        log.write(f"{event} {args[1:]!r}\\n")
    elif event == "open":
        path, mode, flags = args
        if isinstance(path, (str, bytes)) and (
            (mode is not None and any(char in mode for char in "wax+"))
            or (mode is None and flags & WRITE_FLAGS)
        ):
            log.write(f"write {os.fsdecode(os.path.abspath(path))}\\n")
    elif event in ("os.mkdir", "os.rename", "os.remove", "os.rmdir", "os.symlink",
                   "shutil.rmtree", "shutil.copyfile", "os.truncate"):
        for path in args:
            if isinstance(path, (str, bytes)):
                log.write(f"write {os.fsdecode(os.path.abspath(path))}\\n")
                break


sys.addaudithook(hook)
from dsml.cli import main

sys.exit(main(["mcp", "--project", sys.argv[2]]))
"""
"""Start `dsml mcp` with an audit hook that records socket events and file writes.

The hook writes one line to the log file for each event. The first line
gives the process ID of the server.
"""

LOOPBACK = ("127.0.0.1", "::1", "localhost")
"""The addresses of the loopback interface. Only the OpenSysML child process listens there."""


@dataclass
class Cycle:
    """The results of the work cycle through the MCP server and through the CLI."""

    project: Path
    """The project folder of the MCP server."""
    reference: Path
    """The folder where the CLI does the write steps."""
    results: dict[str, Any] = field(default_factory=dict[str, Any])
    """The result of each MCP tool call, by step name."""
    cli: dict[str, tuple[int, str, list[str]]] = field(
        default_factory=dict[str, tuple[int, str, list[str]]]
    )
    """The exit code, the report and the messages of the CLI, by step name."""
    files: dict[str, tuple[dict[str, bytes], dict[str, bytes]]] = field(
        default_factory=dict[str, tuple[dict[str, bytes], dict[str, bytes]]]
    )
    """The files of the project folder and of the reference folder after a write step."""
    log: list[str] = field(default_factory=list[str])
    """The lines of the audit log of the server."""
    sockets: set[tuple[str, str, str]] = field(default_factory=set[tuple[str, str, str]])
    """Each internet socket of the server process: protocol, local address, remote address."""


def run_cli(folder: Path, *argv: str) -> tuple[int, str, list[str]]:
    """Run the command `dsml` in a subprocess. Give the exit code, the report and the messages."""
    result = subprocess.run(
        [sys.executable, "-m", "dsml", *argv], cwd=folder, capture_output=True, check=False
    )
    return result.returncode, result.stdout.decode(), result.stderr.decode().splitlines()


def files_in(folder: Path) -> dict[str, bytes]:
    """Give the bytes of each file in a folder and its subfolders, by relative path."""
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(folder).parts
    }


def add_order_service(folder: Path) -> None:
    """Replace the starter model with the order service, and write its configuration."""
    (folder / "model" / "model.sysml").unlink()
    shutil.copyfile(EXAMPLE_MODEL, folder / "model" / "order-service.sysml")
    (folder / "dsml.toml").write_text(CONFIGURATION, encoding="utf-8", newline="\n")


def commit(folder: Path) -> None:
    """Make a Git repository in the folder with one commit of all files."""
    subprocess.run(["git", "init", "--quiet"], cwd=folder, check=True)
    subprocess.run(["git", "add", "."], cwd=folder, check=True)
    subprocess.run([*GIT, "commit", "--quiet", "-m", "Model"], cwd=folder, check=True)


def _address(text: str) -> str:
    """Give the IP address of an address in `/proc/net/tcp` or `/proc/net/tcp6`."""
    host = text.split(":")[0]
    if len(host) == 8:
        return ".".join(str(int(host[index : index + 2], 16)) for index in (6, 4, 2, 0))
    words = [host[index : index + 8] for index in range(0, 32, 8)]
    raw = b"".join(bytes.fromhex(word)[::-1] for word in words)
    address = ipaddress.IPv6Address(raw)
    return str(address.ipv4_mapped or address)


def internet_sockets(pid: int) -> set[tuple[str, str, str]]:
    """Give each internet socket of the process `pid`, from `/proc`. Linux only.

    An item has the protocol, the local address and the remote address. A
    listening socket has the remote address "listen".
    """
    try:
        inodes = {
            os.readlink(f"/proc/{pid}/fd/{name}")[8:-1]
            for name in os.listdir(f"/proc/{pid}/fd")
            if os.readlink(f"/proc/{pid}/fd/{name}").startswith("socket:[")
        }
    except OSError:
        return set()
    found: set[tuple[str, str, str]] = set()
    for protocol in ("tcp", "tcp6", "udp", "udp6", "raw", "raw6"):
        try:
            lines = Path(f"/proc/{pid}/net/{protocol}").read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if parts[9] in inodes:
                remote = "listen" if parts[3] == "0A" else _address(parts[2])
                found.add((protocol, _address(parts[1]), remote))
    return found


async def _cycle(cycle: Cycle, log_file: Path) -> None:
    """Start the server and do the work cycle. Run the CLI after each tool call."""
    project, reference = cycle.project, cycle.reference
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-c", LAUNCHER, str(log_file), str(project)],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        cwd=project,
    )
    stop = threading.Event()

    def watch() -> None:
        """Read the sockets of the server process until the cycle stops."""
        pid = 0
        while not stop.wait(0.005):
            if not pid and log_file.is_file():
                lines = log_file.read_text(encoding="utf-8").splitlines()
                pid = int(lines[0].split()[1]) if lines else 0
            if pid:
                cycle.sockets |= internet_sockets(pid)

    watcher = threading.Thread(target=watch, daemon=True)
    if sys.platform == "linux":
        watcher.start()

    async def call(session: ClientSession, step: str, tool: str, arguments: dict[str, Any]) -> None:
        result = await session.call_tool(tool, arguments)
        assert not result.is_error, result.content
        cycle.results[step] = result.structured_content

    try:
        with anyio.fail_after(300):
            async with (
                stdio_client(parameters) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()

                await call(session, "init", "init", {"target": "fastapi"})
                cycle.cli["init"] = run_cli(reference, "init", "--target", "fastapi")
                cycle.files["init"] = (files_in(project), files_in(reference))

                add_order_service(project)
                add_order_service(reference)

                await call(session, "validate", "validate", {"format": "json", "date": DATE})
                cycle.cli["validate"] = run_cli(
                    project, "validate", "--format", "json", "--date", DATE
                )

                await call(session, "ir", "ir", {})
                cycle.cli["ir"] = run_cli(project, "ir")

                await call(session, "generate", "generate", {"date": DATE})
                cycle.cli["generate"] = run_cli(reference, "generate", f"--date={DATE}")
                cycle.files["generate"] = (files_in(project), files_in(reference))

                await call(session, "generate --check", "generate", {"check": True, "date": DATE})
                cycle.cli["generate --check"] = run_cli(
                    project, "generate", "--check", f"--date={DATE}"
                )

                commit(project)
                await call(session, "trace", "trace", {"report": "coverage"})
                cycle.cli["trace"] = run_cli(project, "trace", "coverage", "--format", "json")

                await call(session, "version", "version", {})
                cycle.cli["version"] = run_cli(project, "version")
    finally:
        stop.set()
        if watcher.is_alive():
            watcher.join()
    cycle.log = log_file.read_text(encoding="utf-8").splitlines()


@pytest.fixture(scope="module")
def cycle(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Cycle]:
    """Do the work cycle one time for all tests of this module."""
    base = tmp_path_factory.mktemp("end-to-end")
    done = Cycle(project=base / "project", reference=base / "reference")
    done.project.mkdir()
    done.reference.mkdir()
    anyio.run(_cycle, done, base / "server.log")
    yield done


def lines_of(changes: list[dict[str, str]]) -> str:
    """Give the report of `dsml generate` for the changes of the tool `generate`."""
    return "".join(f"{change['action']} {change['path']}\n" for change in changes)


# trace: PRD-AI-011, PRD-AI-012, PRD-AI-013, PRD-CORE-042
def test_init_writes_the_same_files_as_the_cli(cycle: Cycle) -> None:
    result = cycle.results["init"]
    assert (result["exit_code"], result["report"]) == cycle.cli["init"][:2]
    project, reference = cycle.files["init"]
    assert project == reference
    assert sorted(project) == ["dsml.toml", "model/model.sysml"]


# trace: PRD-AI-012, PRD-CORE-001, PRD-CORE-028
def test_validate_and_ir_give_the_same_reports_as_the_cli(cycle: Cycle) -> None:
    code, report, _ = cycle.cli["validate"]
    result = cycle.results["validate"]
    assert (result["exit_code"], result["report"]) == (code, json.loads(report))
    assert code == 0
    assert result["report"]["summary"]["error"] == 0
    code, report, _ = cycle.cli["ir"]
    result = cycle.results["ir"]
    assert (result["exit_code"], result["report"]) == (code, json.loads(report))
    assert code == 0


# trace: PRD-AI-012, PRD-AI-013, PRD-CORE-004, PRD-CORE-028, PRD-CORE-029
def test_generate_writes_the_same_bytes_as_the_cli(cycle: Cycle) -> None:
    code, report, messages = cycle.cli["generate"]
    result = cycle.results["generate"]
    assert (result["exit_code"], lines_of(result["changes"]), result["messages"]) == (
        code,
        report,
        messages,
    )
    assert code == 0
    project, reference = cycle.files["generate"]
    assert project == reference
    assert "services/order-api/app/main_gen.py" in project
    code, report, messages = cycle.cli["generate --check"]
    result = cycle.results["generate --check"]
    assert (result["exit_code"], lines_of(result["changes"]), result["messages"]) == (
        code,
        report,
        messages,
    )
    assert (code, report) == (0, "")


# trace: PRD-AI-012, PRD-TRACE-010, PRD-CORE-001
def test_trace_and_version_give_the_same_reports_as_the_cli(cycle: Cycle) -> None:
    code, report, messages = cycle.cli["trace"]
    result = cycle.results["trace"]
    assert (result["exit_code"], result["report"], result["messages"]) == (code, report, messages)
    assert code == 0
    result = cycle.results["version"]
    assert cycle.cli["version"][:2] == (
        0,
        f"toolchain: {result['toolchain']}\n"
        f"DSML library: {result['dsml_library']}\n"
        f"OpenSysML: {result['opensysml']}\n"
        f"IR schema: {result['ir_schema']}\n",
    )


# trace: PRD-AI-017, PRD-TOP-005
def test_server_opens_no_network_socket(cycle: Cycle) -> None:
    events = [line for line in cycle.log if line.startswith("socket.")]
    # The Python code of the server makes only local sockets, for example the
    # socket pair of the event loop. It binds no socket.
    for line in events:
        assert not line.startswith("socket.bind"), line
        if line.startswith("socket.__new__"):
            assert line.startswith(f"socket.__new__ ({int(socket.AF_UNIX)},"), line
        else:
            assert any(address in line for address in LOOPBACK), line
    # The server opens no listening socket. Its only internet socket is the
    # connection to the OpenSysML child process on the loopback interface.
    if sys.platform == "linux":
        assert cycle.sockets
    for protocol, local, remote in cycle.sockets:
        assert protocol.startswith("tcp"), (protocol, local, remote)
        assert (local, remote) in {("127.0.0.1", "127.0.0.1"), ("::1", "::1")}


# trace: PRD-AI-013, PRD-AI-014
def test_server_writes_no_file_outside_the_project_folder(cycle: Cycle) -> None:
    root = cycle.project.resolve()
    writes = {Path(line.removeprefix("write ")) for line in cycle.log if line.startswith("write ")}
    assert root / "services" / "order-api" / "app" / "main_gen.py" in writes
    # The OpenSysML client locks its cache folder before it starts the child
    # process, the same as for each subcommand. It does not change the cache.
    cache = fetch_binary().parent
    outside = {path for path in writes if not path.resolve().is_relative_to(root)}
    assert {
        path
        for path in outside
        if path not in (Path(os.devnull), cache)
        and not (path.parent == cache and path.suffix == ".lock")
    } == set()
