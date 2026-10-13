# trace: PRD-AI-016
"""MCP prompts for the tasks of the AI agent.

The server has these prompts:

- `create_model`: the modeling skill `dsml-modeling`. The argument
  `description` gives the product description of the user.
- `fix_findings`: the sections "Validate the model" and "Correct the
  findings" of the CLI skill `dsml-cli`. No argument.
- `generate_code`: the sections of the CLI skill `dsml-cli` about
  generation and `check-output`. No argument.

Each prompt reads the text of the packaged `SKILL.md` file, so the prompts and
the skills always agree. The text of a prompt is the skill text with these
changes:

- A command line `dsml <subcommand> <options>` becomes a call of the MCP tool
  with the same name, for example `validate(format="json")`.
- An option `--<option>` becomes the argument of the tool, for example `fail_on`.
- A reference file `references/<name>.md` becomes the URI of its MCP resource.
- Some sentences about the skills and the CLI change for the MCP server.

If the skill text has a command line, an option or a sentence that the
module cannot change, the module raises `ValueError`. Thus a test finds a
change of a skill that a prompt does not agree with.
"""

import json
import re
import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from typing import Annotated, Any, Final

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from dsml.mcp.project import Project
from dsml.mcp.resources import REFERENCE, reference_uri

SKILLS_PACKAGE: Final = "dsml.skills"
"""The package that contains the skill folders."""

TOOLS: Final = frozenset({"init", "validate", "ir", "generate", "check_output", "trace", "version"})
"""The MCP tools of the server, by name. A prompt names only these tools."""

VALUE_OPTIONS: Final[Mapping[str, str]] = {
    "--application": "application",
    "--baseline": "baseline",
    "--config": "config",
    "--date": "date",
    "--fail-on": "fail_on",
    "--format": "format",
    "--target": "target",
}
"""The options with a value, and the argument of the tool for each option."""

FLAG_OPTIONS: Final[Mapping[str, str]] = {
    "--check": "check",
    "--infrastructure": "infrastructure",
    "--pipelines": "pipelines",
}
"""The options with no value, and the argument of the tool for each option."""

POSITIONAL: Final[Mapping[str, tuple[str, ...]]] = {"trace": ("report",)}
"""The arguments of the tool for the positional arguments of each subcommand."""

_COMMAND_SPAN: Final = re.compile(r"`(dsml [^`]*)`")
_OPTION_SPAN: Final = re.compile(r"`(--[a-z-]+)`")
_REFERENCE_PATH: Final = re.compile(r"`references/([a-z]+)\.md`")
_SHELL_BLOCK: Final = re.compile(
    r"^(?P<indent> *)```shell\n(?P<body>.*?)^(?P=indent)```$", re.M | re.S
)


# trace: PRD-AI-016
def tool_call(command_line: str) -> str:
    """Give the call of the MCP tool for a command line `dsml <subcommand> <options>`.

    The result has the form `tool(argument=value)`. The values are JSON values.
    """
    tokens = shlex.split(command_line)
    if len(tokens) < 2 or tokens[0] != "dsml":
        raise ValueError(f'"{command_line}" is not a command line of dsml.')
    tool = tokens[1].replace("-", "_")
    if tool not in TOOLS:
        raise ValueError(f'The MCP server has no tool for "{command_line}".')
    arguments: list[str] = []
    positional = list(POSITIONAL.get(tool, ()))
    rest = tokens[2:]
    while rest:
        token = rest.pop(0)
        if token in FLAG_OPTIONS:
            arguments.append(f"{FLAG_OPTIONS[token]}=true")
        elif token in VALUE_OPTIONS and rest:
            arguments.append(f"{VALUE_OPTIONS[token]}={json.dumps(rest.pop(0))}")
        elif not token.startswith("-") and positional:
            arguments.append(f"{positional.pop(0)}={json.dumps(token)}")
        else:
            raise ValueError(
                f'The tool "{tool}" has no argument for "{token}" in "{command_line}".'
            )
    return f"{tool}({', '.join(arguments)})"


def _option(match: re.Match[str]) -> str:
    option = match[1]
    argument = VALUE_OPTIONS.get(option) or FLAG_OPTIONS.get(option)
    if argument is None:
        raise ValueError(f'The MCP tools have no argument for the option "{option}".')
    return f"`{argument}`"


def _reference(match: re.Match[str]) -> str:
    name = match[1]
    if name not in {file.name for file in REFERENCE}:
        raise ValueError(f'The MCP server has no resource for "references/{name}.md".')
    return f"`{reference_uri(name)}`"


def _shell_block(match: re.Match[str]) -> str:
    indent = match["indent"]
    lines = [
        indent + tool_call(line.strip()) if line.strip() else line
        for line in match["body"].splitlines()
    ]
    return "\n".join([f"{indent}```text", *lines, f"{indent}```"])


# trace: PRD-AI-016
def for_tools(text: str, changes: Mapping[str, str] | None = None) -> str:
    """Change the skill text for the MCP server.

    First the function replaces each key of `changes` with its value. Each
    key must be in the text. Then it replaces the command lines, the options
    and the paths of the reference files.
    """
    for old, new in (changes or {}).items():
        if old not in text:
            raise ValueError(f'The skill text does not contain "{old}".')
        text = text.replace(old, new)
    text = _SHELL_BLOCK.sub(_shell_block, text)
    text = _COMMAND_SPAN.sub(lambda match: f"`{tool_call(match[1])}`", text)
    text = _OPTION_SPAN.sub(_option, text)
    return _REFERENCE_PATH.sub(_reference, text)


# trace: PRD-AI-016
def skill_text(skill: str) -> str:
    """Give the text of the packaged `SKILL.md` file of a skill, with no front matter."""
    text = resources.files(SKILLS_PACKAGE).joinpath(skill, "SKILL.md").read_bytes()
    body = text.decode("utf-8")
    if body.startswith("---\n"):
        end = body.index("\n---\n", 4)
        body = body[end + len("\n---\n") :]
    return body.lstrip("\n")


# trace: PRD-AI-016
def sections(text: str, headings: tuple[str, ...]) -> str:
    """Give the sections of a skill text with these level-2 headings, in the order of `headings`."""
    found: dict[str, str] = {}
    for part in re.split(r"^(?=## )", text, flags=re.M):
        if part.startswith("## "):
            found[part.splitlines()[0].removeprefix("## ")] = part.rstrip("\n")
    missing = [heading for heading in headings if heading not in found]
    if missing:
        raise ValueError(f'The skill text has no section "{missing[0]}".')
    return "\n\n".join(found[heading] for heading in headings)


def introduction() -> str:
    """Give the first paragraph of each prompt. It tells how to use the tools."""
    names = ", ".join(f"`{name}`" for name in sorted(TOOLS))
    return "\n".join(
        [
            f"Use the MCP server `dsml` for this task. The server has these tools: {names}.",
            "Each tool does the work of the subcommand of the `dsml` CLI with the same name. "
            "The tool `check_output` does the work of `dsml check-output`.",
            'In this text, a tool call has the form `<tool>(<argument>="<value>")`. '
            "Give only the arguments that the call shows.",
            "Each tool gives the exit code of its subcommand in the field `exit_code`. "
            "The other fields give the output of the subcommand.",
            f"The resource `{reference_uri('commands')}` gives each subcommand and its options.",
        ]
    )


@dataclass(frozen=True)
class SkillPrompt:
    """The text of one prompt from one skill."""

    skill: str
    title: str
    headings: tuple[str, ...]
    """The sections of the skill. With no heading, the prompt has all of the skill text."""
    changes: Mapping[str, str]
    """The sentences of the skill that change for the MCP server."""

    def text(self, task: str = "") -> str:
        """Give the text of the prompt. A `task` paragraph follows the introduction."""
        body = skill_text(self.skill)
        if self.headings:
            body = f"# {self.title}\n\n" + sections(body, self.headings)
        parts = [introduction(), task, for_tools(body, self.changes).rstrip("\n")]
        return "\n\n".join(part for part in parts if part) + "\n"


# trace: PRD-AI-016
CREATE_MODEL: Final = SkillPrompt(
    skill="dsml-modeling",
    title="Write a DSML model",
    headings=(),
    changes={
        "Read these files when you need them. Do not read all files at the start.": (
            "Read these MCP resources when you need them. Do not read all resources at the start."
        ),
        "| File | Contents |": "| Resource | Contents |",
        "The toolchain writes `keywords.md`, `rules.md` and `examples.md` from the installed "
        "version. Thus these files agree with the `dsml` command of the project.": (
            "The toolchain writes the resources `keywords`, `rules` and `examples` from the "
            "installed version. Thus these resources agree with the tools of the server."
        ),
        "Run the command again until the summary gives 0 errors.": (
            "Use the tool again until the summary gives 0 errors."
        ),
        "The CLI skill `dsml-cli` tells you how to generate code from the model "
        "after validation.": (
            "The prompt `generate_code` tells you how to generate code from the model "
            "after validation."
        ),
    },
)
"""The prompt `create_model`: the modeling skill."""

# trace: PRD-AI-016
FIX_FINDINGS: Final = SkillPrompt(
    skill="dsml-cli",
    title="Correct the findings of validation",
    headings=("Validate the model", "Correct the findings"),
    changes={},
)
"""The prompt `fix_findings`: the validation procedure of the CLI skill."""

# trace: PRD-AI-016
GENERATE_CODE: Final = SkillPrompt(
    skill="dsml-cli",
    title="Generate the code and check it",
    headings=("Generate the code", "Write the business logic", "Check the generated code"),
    changes={
        "The command writes no file. It lists": "The tool writes no file. It lists",
        "5. If the command stops because a generated file changed, do not use `--overwrite`. "
        "Tell the user the changed files. Move the change into a hand-written file or into "
        "the model. Use `--overwrite` only when the user approves it.": (
            "5. If the tool stops because a generated file changed, tell the user the changed "
            "files. Move the change into a hand-written file or into the model. The tool "
            "`generate` has no option that replaces a changed generated file. Only the user "
            "can do this, with the command dsml generate --overwrite."
        ),
    },
)
"""The prompt `generate_code`: the generation and check procedure of the CLI skill."""

PROMPTS: Final[Mapping[str, SkillPrompt]] = {
    "create_model": CREATE_MODEL,
    "fix_findings": FIX_FINDINGS,
    "generate_code": GENERATE_CODE,
}
"""The prompts of the server, by name."""

Description = Annotated[
    str,
    Field(description="The description of the product, in the words of the user."),
]


# trace: PRD-AI-016
def create_model_text(description: str) -> str:
    """Give the text of the prompt `create_model` for a product description."""
    task = (
        "Write a DSML model for the product of the section "
        '"Product description" at the end of this text. Obey the procedure below.'
    )
    text = CREATE_MODEL.text(task)
    return f"{text}\n## Product description\n\n{description.strip()}\n"


# trace: PRD-AI-016
def register(server: MCPServer[Any], project: Project) -> None:
    """Add the prompts `create_model`, `fix_findings` and `generate_code` to the server.

    The prompts do not read the project folder. They are the same for each project.
    """

    @server.prompt(
        name="create_model",
        title="Write a DSML model",
        description="Write a DSML model from a product description, then validate it "
        "until the validator finds no error.",
    )
    def create_model(description: Description) -> str:
        return create_model_text(description)

    @server.prompt(
        name="fix_findings",
        title="Correct the findings of validation",
        description="Validate the model, then correct each error finding until the "
        "validator finds no error.",
    )
    def fix_findings() -> str:
        return FIX_FINDINGS.text()

    @server.prompt(
        name="generate_code",
        title="Generate the code and check it",
        description="Generate the code from a valid model, then run the language tools "
        "on the generated code.",
    )
    def generate_code() -> str:
        return GENERATE_CODE.text()
