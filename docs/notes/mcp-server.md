# Command `dsml mcp`: local MCP server

Story #229 added the frame of the local MCP server (PRD-AI-008 to PRD-AI-010, PRD-AI-014, Q69). The server has no MCP tool, MCP resource or MCP prompt yet. The stories of steps 3 and 4 of M12 (#226) add them.

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
