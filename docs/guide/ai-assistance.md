# AI assistance

An AI agent can help you write a model and use the toolchain. The toolchain gives two kinds of help to the agent:

- Two [skills](glossary.md#terms). A skill is a folder with instructions and reference files. The agent reads it when it does a task.
- A local [MCP server](glossary.md#terms). The server gives the functions of the `dsml` command to the agent as MCP tools, MCP resources and MCP prompts.

You can use the skills, the MCP server or the two together. The skills and the server use the same reference text, so they agree with the installed toolchain.

Read the [concepts page](concepts.md) before this page. It tells what a [model](concepts.md#what-the-dsml-adds), [validation](concepts.md#validation-findings-and-waivers) and [code generation](concepts.md#code-generation) are. The [glossary](glossary.md) gives a short meaning for each term.

## Install the skills

The skills are in the toolchain package. The command `dsml skills install` copies them into your project. It does not use the network.

1. Go to the root folder of your project.
2. Write the skills into the folder `.claude/skills/`:

   ```shell
   dsml skills install
   ```

3. Make sure that the report has one line for each skill:

   ```text
   install .claude/skills/dsml-cli
   install .claude/skills/dsml-modeling
   ```

4. Commit the folder `.claude/skills/` to Git. Then each person in the team gets the same skills.

Claude Code finds the skills in `.claude/skills/`. A different agent can read skills from a different folder. Use the option `--output` to write the skills into that folder, for example:

```shell
dsml skills install --output .agents/skills
```

The command replaces only the folders `dsml-cli` and `dsml-modeling` in the destination folder. It does not change a different file or folder there. Two runs with the same toolchain version write the same bytes.

### Install the skills again after an upgrade

The reference files of the skills come from the installed toolchain. They give the DSML keywords, the validation rules and the `dsml` subcommands of that version. After each upgrade of the toolchain, do these steps:

1. Run `dsml skills install` again, with the same `--output` option as before.
2. Commit the changed files.

If you do not do this, the agent can use a keyword, a rule or an option that is not correct for the installed version.

## Install the MCP server

The MCP server is in the optional dependency group `mcp` of the toolchain package. The group adds the official MCP Python SDK. The other subcommands do not need the group.

1. Install uv and the toolchain. [Install the release](../release.md#install-the-release) gives the steps.
2. Install the toolchain again, with the group `mcp`. Use the wheel of the same release:

   ```shell
   uv tool install --reinstall --python 3.14 "dsml[mcp] @ https://github.com/ds411/dsml-code-generator/releases/download/v<version>/dsml-<version>-py3-none-any.whl"
   ```

3. Make sure that the `sysml-grpc` binary is installed. Step 3 of [Install the release](../release.md#install-the-release) gives the command. The tools `validate`, `ir`, `generate` and `trace` need it.

Without the group `mcp`, the command `dsml mcp` stops with exit code 2. Its message gives the install command.

### Add the server to Claude Code

Claude Code reads the MCP servers of a project from the file `.mcp.json` in the root folder of the project.

1. Write the file `.mcp.json` in the root folder of your project:

   ```json
   {
     "mcpServers": {
       "dsml": {
         "type": "stdio",
         "command": "dsml",
         "args": ["mcp"]
       }
     }
   }
   ```

2. Commit the file to Git.
3. Start Claude Code in the root folder of the project.
4. When Claude Code asks you, let it use the server `dsml`.
5. Make sure that the server is connected. In Claude Code, type `/mcp`. The list must show the server `dsml`.

Claude Code starts the server in the root folder of the project. Thus the project folder of the server is the root folder of the project.

### Add the server to a different MCP client

Each MCP client that has the stdio transport can start the server. Give the client this command:

```shell
dsml mcp --project <folder>
```

- Replace `<folder>` with the absolute path of the root folder of your project. The client can start the server in a different folder, so do not use a relative path.
- If the client does not find the command `dsml`, give the absolute path of the command. The command `uv tool dir --bin` gives its folder.

Many clients use a JSON file with the same form as `.mcp.json`. For example:

```json
{
  "mcpServers": {
    "dsml": {
      "command": "dsml",
      "args": ["mcp", "--project", "/home/user/projects/order-service"]
    }
  }
}
```

The server writes its MCP messages to standard output and reads the messages of the client from standard input. Do not start the server in a terminal, because it then waits for MCP messages from you.

## The skills

| Skill | What it tells the agent |
| --- | --- |
| `dsml-modeling` | How to write or change a model in the five layers with the DSML keywords. Its reference files give the keywords, a short pattern for each layer, the validation rules and the starter models. |
| `dsml-cli` | How to use `dsml init`, `dsml validate`, `dsml generate`, `dsml check-output` and `dsml trace coverage`. It gives a loop that corrects the findings until `dsml validate` finds no error. Its reference files give the subcommands and the validation rules. |

The agent selects a skill from its description. For example, ask the agent: "Write a DSML model for a service that keeps a list of tasks." The agent then uses the skill `dsml-modeling`. You can also tell the agent the name of the skill.

## The MCP tools

Each MCP tool runs its `dsml` subcommand with the same functions. For the same model, configuration and toolchain version, the tool and the subcommand give the same result. Each tool accepts the options of its subcommand, but no tool has the options `--output` and `--overwrite`.

| MCP tool | Subcommand | What it does | Files that it can write |
| --- | --- | --- | --- |
| `init` | `dsml init` | Writes a starter configuration file and a starter model for a target. | Only the create-once starter files: `dsml.toml` (or the path of `config`) and `model/model.sysml` next to it. It does not change a file that exists. |
| `validate` | `dsml validate` | Validates the model and gives the findings. The default format is JSON. | None |
| `ir` | `dsml ir` | Gives the [IR](concepts.md#the-ir) of the model as JSON. The agent can select parts, kinds or names to make the IR smaller. | None |
| `generate` | `dsml generate` | Validates the model, then writes the generated files. With `check`, it writes no file and gives the changes. | The generated files, the create-once files of a generator, the manifest `.dsml/generated.json` and the trace manifest `.dsml/trace.gen.json`. It never changes a hand-written file. |
| `check_output` | `dsml check-output` | Runs the language tools of each target on the generated code. | None |
| `trace` | `dsml trace coverage` and the other reports | Gives a trace report: `coverage`, `orphans`, `impact` or `suspect`. The default format is JSON. | None |
| `version` | `dsml version` | Gives the versions of the toolchain, the DSML library, OpenSysML and the IR schema. | None |

Only the tools `init` and `generate` can write files. The agent writes and changes the model files with its own file tools.

If a generated file is different from its hash in the manifest, the tool `generate` writes no file. It gives the changed files. The tool has no overwrite option, so the agent cannot replace your changes. Move your changes into a hand-written file, or run `dsml generate --overwrite` yourself. [Generated code](generated-code.md) tells which files you can change.

Each tool gives the exit code of its subcommand:

- 0: no error finding, and no difference.
- 1: an error finding, or a difference.
- 2: a usage error or an internal error. The tool gives an MCP tool error with the message.

### The project folder

The server operates only in its project folder. Each path that the agent gives to a tool is relative to the project folder. The server refuses a path outside the project folder, and it does not write a file outside it.

## The MCP resources

The MCP resources are read-only texts. The agent reads them when it needs them. They have the same text as the reference files of the skills.

| MCP resource | Contents |
| --- | --- |
| `keywords` | Each DSML keyword with its layer, its form and its attributes, and the enumerations. |
| `rules` | Each validation rule with its ID, severity, message and correction. |
| `commands` | Each `dsml` subcommand with its options. |
| `examples` | The starter models that `dsml init` writes. |
| One resource for each example model | The text of one example model of the package. The package has a starter model for each target: `fastapi`, `react` and `nextjs`. |

## The MCP prompts

An MCP prompt is a prompt template. In most clients, you select a prompt from a list or with a slash command. The prompts have the text of the procedures of the skills. Thus an agent without the skills gets the same help.

| MCP prompt | Argument | What it tells the agent |
| --- | --- | --- |
| `create_model` | Your description of the product. | The procedure of the skill `dsml-modeling`: write a model in the five layers from the description, then validate it. |
| `fix_findings` | None | The procedure that corrects the findings of the tool `validate`, until it finds no error. |
| `generate_code` | None | The procedure of the skill `dsml-cli` for the tools `generate` and `check_output`. |

## Limits

- The toolchain does not use an AI model (PRD-TOP-004). Validation, code generation and the trace reports give the same output for the same model, configuration and toolchain version. The AI agent is a client of the toolchain, not a part of it.
- Validation, code generation and the trace reports do not use the network (PRD-TOP-005). The MCP server also does not use the network. It uses only the stdio transport and opens no network socket. It does not send the model to a different computer.
- The AI agent can use the network. Your agent and its AI model can send the text that the server gives to a different computer. Read the data rules of your agent before you give it a model.
- The tools operate only in the project folder.
- The agent can make an error. Always examine the model and the code that the agent writes. Run `dsml validate` before you commit.
