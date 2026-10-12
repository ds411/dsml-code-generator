# Decision record 10: AI assistance and user guide

Status date: 12 October 2026

## Purpose and status

This record holds 4 questions, Q68 to Q71, for phase 4 (AI assistance). Decision issues #223 to #225 asked Q68 to Q70 when the milestone M12 (#226) was planned. Q71 records a request of the product owner for a user guide. Each new requirement gives its decision in the Source column.

Status: closed. On 12 October 2026, the product owner answered the three decision issues and asked for the user guide in the project thread of M12.

## AA. AI assistance

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q68 | Where do the DSML skills ship, and how does a user install them (#223)? Options: (a) the skills are in the toolchain package, and the command `dsml skills install` writes them into `.claude/skills/` of the project; (b) a Claude Code plugin in this repository; (c) option (a), and the release also attaches a plugin. | (a). The skills are in `src/dsml/skills/`. `dsml skills install` writes them into `.claude/skills/`, and the option `--output` selects a different folder for other agents. The command replaces only the skill folders that it owns. Thus the skills always agree with the installed `dsml` version, and the install uses no network. A later decision can add the plugin of option (c). New requirements: PRD-AI-001 to PRD-AI-007. | Decided |
| Q69 | Which MCP library and transport does the DSML MCP server use (#224)? Options: (a) the official MCP Python SDK in the optional dependency group `mcp`, with the stdio transport only; (b) option (a), but the SDK is a normal dependency; (c) MCP messages with the Python standard library; (d) option (a), and also the Streamable HTTP transport on `127.0.0.1`. | (a). The command `dsml mcp` starts the server with the stdio transport. The core installation keeps its two run-time dependencies. Without the group `mcp`, `dsml mcp` stops with an error that gives the install command. The stdio transport opens no network port, so the model stays on the computer. New requirements: PRD-AI-008 to PRD-AI-010, PRD-AI-015 to PRD-AI-017. Changed source: PRD-TOP-002. | Decided |
| Q70 | Which files can the DSML MCP server write (#225)? Options: (a) read tools only; (b) option (a), and the tools `init` and `generate` write files in the project folder, with no overwrite option; (c) option (b), and a tool that writes a model file. | (b). The server gives the full work cycle of the CLI skill. It operates only in the project folder that the user gives at start. The tool `generate` has no overwrite option, so it stops on a changed generated file (PRD-CORE-043). The agent writes model files with its own file tools. New requirements: PRD-AI-011 to PRD-AI-014. | Decided |
| Q71 | Which documentation tells a user with no knowledge of SysML v2, Jinja or the target tools what the model and the toolchain do? On 12 October 2026, the product owner asked for this documentation. | A user guide in `docs/guide/`. It has a concepts page, a glossary, a modeling tutorial, pages for the generated code and the reports, reference pages and a page for AI assistance. The guide uses ASD-STE100 (PRD-TOP-009). New requirement: PRD-TOP-013. | Decided |

## PRD-TOP-004 and PRD-TOP-005 stay true

The skills and the MCP server do not change PRD-TOP-004 and PRD-TOP-005. The AI agent is a client of the toolchain, not a part of it. Validation, code generation and trace reports still use no AI model and no network. The MCP server runs the same functions as the CLI, on the computer of the user.

## Effects on the milestones

- M12 (#226): #227 adds the AI assistance PRD (`docs/prd/08-ai-assistance-prd.md`) and PRD-TOP-013. #228 writes the reference files of the skills. #229 adds the frame of `dsml skills` and `dsml mcp`, and the optional dependency group `mcp`.
- M12 (#226): #230 and #231 write the two skills. #232 to #234 write the MCP tools, resources and prompts. #236 checks the full work cycle.
- M12 (#226): #237 to #240 and #235 write the user guide of Q71.
