# trace: PRD-AI-008, PRD-AI-014, PRD-AI-017
"""The command `dsml mcp`: the local MCP server with the stdio transport.

The server uses the official MCP Python SDK (Q69). It gets the messages of
the AI agent on standard input and writes its messages to standard output.
It opens no network socket (PRD-AI-017).

Each module of `MODULES` adds its MCP tools, MCP resources or MCP prompts
to the server with its function `register`. A later story changes only its
own module.
"""

import os
from typing import Any, Final

from mcp.server.mcpserver import MCPServer

from dsml.mcp import prompts, resources, tools_generate, tools_model
from dsml.mcp.project import Project

NAME: Final = "dsml"
"""The name of the server, which the server gives to the client at the start."""

INSTRUCTIONS: Final = (
    "This server gives the functions of the DSML toolchain. "
    "It operates only in the project folder that the user gave when the server started."
)
"""The instructions that the server gives to the client at the start."""

MODULES: Final = (tools_model, tools_generate, resources, prompts)
"""The modules that add MCP tools, MCP resources and MCP prompts to the server."""


# trace: PRD-AI-008
def build_server(project: Project, version: str) -> MCPServer[Any]:
    """Make the MCP server of the project, with the contents of each module."""
    server: MCPServer[Any] = MCPServer(
        name=NAME, version=version, instructions=INSTRUCTIONS, log_level="WARNING"
    )
    for module in MODULES:
        module.register(server, project)
    return server


# trace: PRD-AI-008, PRD-AI-014, PRD-AI-017
def serve(project: Project, version: str) -> None:
    """Run the server with the stdio transport until the client closes standard input.

    The current folder of the server is the project folder. Thus the MCP
    tools read the same relative paths as the subcommands in that folder.
    """
    server = build_server(project, version)
    os.chdir(project.root)
    server.run("stdio")
