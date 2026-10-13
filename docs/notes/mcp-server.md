# Command `dsml mcp`: local MCP server

Story #229 added the frame of the local MCP server (PRD-AI-008 to PRD-AI-010, PRD-AI-014, Q69). Stories #232, #233 and #234 added the MCP tools, the MCP resources and the MCP prompts. Story #236 added the end-to-end test.

## Use

```text
dsml mcp [--project <folder>] [--verbose]
```

- An AI agent starts the server as a child process. The server gets the messages of the agent on standard input and writes its messages to standard output (the stdio transport).
- The server uses no other transport and opens no network socket (PRD-AI-017).
- The option `--project` gives the project folder. The default is the current folder. The folder must exist, or the command stops with exit code 2.
- The server stops when the agent closes standard input.
- With `--verbose`, the toolchain writes debug messages to standard error, not to standard output.

An example configuration of an MCP client:

```json
{
  "mcpServers": {
    "dsml": {
      "command": "dsml",
      "args": ["mcp", "--project", "."]
    }
  }
}
```

## Optional dependency group `mcp`

The server uses the official MCP Python SDK, the PyPI package `mcp` (Q69). The SDK is in the optional dependency group `mcp` of `pyproject.toml`. Thus the core installation keeps its two run-time dependencies, `jinja2` and `opensysml` (PRD-TOP-002).

- To install the toolchain with the group: `uv tool install --python 3.14 "dsml[mcp] @ <wheel-file>"`.
- In this repository: `uv sync --extra mcp`.
- Without the group, `dsml mcp` stops with exit code 2 and a message that gives the install command (PRD-AI-009).
- All other subcommands operate without the group (PRD-AI-010). Only `src/dsml/mcp/server.py` and the modules that it registers import the SDK. The CLI imports the server module only when the subcommand `mcp` runs.

## Modules

| Module | Contents | Story |
| --- | --- | --- |
| `src/dsml/mcp/server.py` | The server and the stdio transport. It calls the function `register` of each module below. | #229 |
| `src/dsml/mcp/project.py` | The project folder. `Project.path` refuses a path outside the folder (PRD-AI-014). | #229 |
| `src/dsml/mcp/tools_model.py` | The MCP tools `init`, `validate` and `ir`. | #232 |
| `src/dsml/mcp/tools_generate.py` | The MCP tools `generate`, `check_output`, `trace` and `version`. | #233 |
| `src/dsml/mcp/resources.py` | The MCP resources. | #234 |
| `src/dsml/mcp/prompts.py` | The MCP prompts. | #234 |

Each module has the function `register(server, project)`. A later story changes only its own module. Each MCP tool must get each path through `Project.path`. The current folder of the server is the project folder, so the tools read the same relative paths as the subcommands in that folder.

The server gives the name `dsml` and the version of the toolchain package to the client at the start.

## Tests

- `tests/test_mcp_server.py` starts `dsml mcp` as a child process. A test client connects over stdio and gets the server name and the version.
- The tests that need the SDK have the mark `mcp`. Without the SDK, these tests are skipped.
- In CI, the step "Test" runs without the group `mcp`. Then the step "Install the MCP SDK" installs the group, and the step "Test the MCP server" runs `pytest -m mcp`. A later MCP test file needs only the mark `mcp`, and no change to the CI workflow.
- The step "Check the types" runs after the step "Install the MCP SDK", because pyright must find the SDK.

### End-to-end test

`tests/test_mcp_end_to_end.py` (story #236) does the full work cycle of an AI agent through the stdio transport. The CI job "MCP end to end" runs it. The step "Test the MCP server" of the job "Check" does not run it.

1. The test starts `dsml mcp` as a child process in an empty temporary project folder.
2. An MCP client calls `init`. The CLI runs `dsml init` in a second folder. The two folders must have the same files.
3. The test replaces the starter model with the order service model and writes its configuration in the two folders.
4. The client calls `validate`, `ir`, `generate`, `generate` with `check`, `trace` and `version`. The test compares each result with the result of the CLI. For `generate`, the CLI writes into the second folder, and the two folders must have the same bytes.

A small launcher starts the server with a Python audit hook (`sys.addaudithook`). The hook records each socket event and each file write of the server process. On Linux, a thread of the test also reads the sockets of the server process from `/proc` while the cycle runs. The `/proc` check also finds the sockets of the gRPC library, which the audit hook does not see. The tests then make sure of these conditions:

- The Python code of the server makes only Unix domain sockets, for example the socket pair of the event loop. It binds no socket.
- The server has no listening socket. Its only internet socket is the connection to the private OpenSysML child process on the loopback interface (PRD-TOP-005, PRD-AI-017). This connection does not leave the computer.
- The server writes no file outside the project folder (PRD-AI-014). There are two permitted items outside the folder: `os.devnull`, and the lock file of the OpenSysML client in its binary cache folder. Each subcommand also locks this file before it starts `sysml-grpc`. The lock does not change the cache.

The job "MCP end to end" also installs the skills two times into empty folders with `dsml skills install`, and compares the two folders with `diff -r`. `tests/test_skills_command.py` does the same check with the skills of the package.

## Versions and licenses

The SDK is pinned to the newest release on 12 October 2026: `mcp==2.3.0`. `uv.lock` pins its dependencies. The source of each license is the package metadata on PyPI (PRD-TOP-007).

| Package | Version | License |
| --- | --- | --- |
| `mcp` | 2.3.0 | MIT |
| `mcp-types` | 2.3.0 | MIT |
| `anyio` | 4.15.1 | MIT |
| `attrs` | 26.1.0 | MIT |
| `click` | 8.5.0 | BSD-3-Clause |
| `h11` | 0.16.0 | MIT |
| `httpcore2` | 2.13.1 | BSD-3-Clause |
| `httpx2` | 2.13.1 | BSD-3-Clause |
| `httpx2-jsfetch` (Emscripten only) | 1.0 | BSD-3-Clause |
| `jsonschema` | 4.26.0 | MIT |
| `jsonschema-specifications` | 2025.9.1 | MIT |
| `opentelemetry-api` | 1.45.1 | Apache-2.0 |
| `python-multipart` | 0.0.32 | Apache-2.0 |
| `pywin32` (Windows only) | 312 | PSF-2.0 |
| `referencing` | 0.37.0 | MIT |
| `rpds-py` | 2026.9.1 | MIT |
| `sse-starlette` | 3.5.0 | BSD-3-Clause |
| `starlette` | 1.7.0 | BSD-3-Clause |
| `truststore` | 0.10.5 | MIT |
| `uvicorn` | 0.54.0 | BSD-3-Clause |

The table gives the packages that the group `mcp` adds to the core installation. The core installation already has the other dependencies of the SDK, for example `pydantic` and `pyjwt`. MIT, Apache-2.0, BSD-3-Clause and PSF-2.0 are permissive licenses. The company accepts them for internal software (PRD-TOP-007).

The SDK also contains the HTTP transports and their dependencies, for example `uvicorn` and `starlette`. The server does not use them.
