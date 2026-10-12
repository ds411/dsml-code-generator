# trace: PRD-AI-015
"""MCP resources: the DSML reference, the rule catalog and the example models.

The module is empty. Story #234 adds the contents.
"""

from typing import Any

from mcp.server.mcpserver import MCPServer

from dsml.mcp.project import Project


# trace: PRD-AI-015
def register(server: MCPServer[Any], project: Project) -> None:
    """Add the contents of this module to the server. The server operates in `project`."""
