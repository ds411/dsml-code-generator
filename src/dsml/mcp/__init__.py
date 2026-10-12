# trace: PRD-AI-008, PRD-AI-009
"""The local MCP server of the toolchain (Q69).

The command `dsml mcp` starts the server. The module `server` imports the
MCP Python SDK. The SDK is in the optional dependency group `mcp`, so this
file and the module `project` do not import it. Thus all other subcommands
operate without the SDK (PRD-AI-010).
"""
