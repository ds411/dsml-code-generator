# trace: PRD-AI-016
"""MCP prompts for the tasks of the AI agent.

The module is empty. Story #234 adds the contents.
"""

from typing import Any

from mcp.server.mcpserver import MCPServer

from dsml.mcp.project import Project


# trace: PRD-AI-016
def register(server: MCPServer[Any], project: Project) -> None:
    """Add the contents of this module to the server. The server operates in `project`."""
