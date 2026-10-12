# trace: PRD-AI-011
"""MCP tools for the model: `init`, `validate` and `ir`.

The module is empty. Story #232 adds the contents.
"""

from typing import Any

from mcp.server.mcpserver import MCPServer

from dsml.mcp.project import Project


# trace: PRD-AI-011
def register(server: MCPServer[Any], project: Project) -> None:
    """Add the contents of this module to the server. The server operates in `project`."""
