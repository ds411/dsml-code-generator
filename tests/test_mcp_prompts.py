"""Tests of the MCP prompts (story #234).

An MCP client in the test process connects to the server and gets the
prompts. The tests need the MCP Python SDK, so they have the mark `mcp`.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

pytest.importorskip("mcp", reason="The MCP Python SDK is not installed.")

import anyio
from mcp import Client
from mcp_types import Prompt, TextContent, Tool

from dsml.mcp import prompts, server
from dsml.mcp.project import Project

pytestmark = pytest.mark.mcp

DESCRIPTION = "A small shop sells books. Customers order books, and the staff sends them."
"""A product description for the prompt `create_model`."""

ARGUMENTS: dict[str, dict[str, str]] = {
    "create_model": {"description": DESCRIPTION},
    "fix_findings": {},
    "generate_code": {},
}
"""The arguments of each prompt in the tests."""

_CALL = re.compile(r"(?<![\w.])([a-z_]+)\(([^()]*)\)")
_ARGUMENT = re.compile(r"([a-z_]+)=")
_URI = re.compile(r"dsml://[a-z]+/[a-z]+")


@dataclass
class Server:
    """The data that a client gets from the server: the tools, the resources and the prompts."""

    tools: dict[str, Tool]
    resources: set[str]
    prompts: dict[str, Prompt]
    texts: dict[str, str]
    """The text of each prompt of `ARGUMENTS`, with its arguments."""


def _server(root: Path) -> Server:
    """Connect a client in this process to a server in `root`. Give the data of the server."""

    async def get() -> Server:
        built = server.build_server(Project.open(root), "0.0.0")
        with anyio.fail_after(60):
            async with Client(built) as client:
                texts: dict[str, str] = {}
                for name, arguments in ARGUMENTS.items():
                    result = await client.get_prompt(name, arguments)
                    assert len(result.messages) == 1
                    assert result.messages[0].role == "user"
                    content = result.messages[0].content
                    assert isinstance(content, TextContent)
                    texts[name] = content.text
                return Server(
                    tools={tool.name: tool for tool in (await client.list_tools()).tools},
                    resources={str(item.uri) for item in (await client.list_resources()).resources},
                    prompts={item.name: item for item in (await client.list_prompts()).prompts},
                    texts=texts,
                )

    return anyio.run(get)


@pytest.fixture(scope="module")
def mcp_server(tmp_path_factory: pytest.TempPathFactory) -> Server:
    return _server(tmp_path_factory.mktemp("project"))


# trace: PRD-AI-016
def test_server_has_the_three_prompts_with_their_arguments(mcp_server: Server) -> None:
    assert set(mcp_server.prompts) == {"create_model", "fix_findings", "generate_code"}
    for prompt in mcp_server.prompts.values():
        assert prompt.title and prompt.description
    [argument] = mcp_server.prompts["create_model"].arguments or []
    assert (argument.name, argument.required) == ("description", True)
    assert argument.description
    assert not mcp_server.prompts["fix_findings"].arguments
    assert not mcp_server.prompts["generate_code"].arguments


# trace: PRD-AI-016
def test_the_prompt_list_of_tools_is_the_tool_list_of_the_server(mcp_server: Server) -> None:
    assert set(mcp_server.tools) == prompts.TOOLS


# trace: PRD-AI-016
@pytest.mark.parametrize("name", sorted(ARGUMENTS))
def test_each_prompt_names_only_tools_and_arguments_that_the_server_has(
    mcp_server: Server, name: str
) -> None:
    text = mcp_server.texts[name]
    calls = _CALL.findall(text)
    assert calls
    for tool, arguments in calls:
        assert tool in mcp_server.tools, tool
        schema = mcp_server.tools[tool].input_schema["properties"]
        for argument in _ARGUMENT.findall(arguments):
            assert argument in schema, f"{tool}({argument})"
    for tool in re.findall(r"[Tt]he tool `([a-z_]+)`", text):
        assert tool in mcp_server.tools, tool
    for line in text.splitlines():
        assert not line.lstrip().startswith("dsml "), line
    assert "```shell" not in text
    assert set(_URI.findall(text)) <= mcp_server.resources


# trace: PRD-AI-016
def test_create_model_gives_the_modeling_procedure_and_the_description(
    mcp_server: Server,
) -> None:
    text = mcp_server.texts["create_model"]
    assert text == prompts.create_model_text(DESCRIPTION)
    assert text.endswith(f"## Product description\n\n{DESCRIPTION}\n")
    assert "## Procedure" in text
    assert 'validate(format="json")' in text
    assert "dsml://reference/patterns" in text


# trace: PRD-AI-016
def test_fix_findings_and_generate_code_give_the_procedures_of_the_cli_skill(
    mcp_server: Server,
) -> None:
    fix = mcp_server.texts["fix_findings"]
    assert "## Correct the findings" in fix
    assert 'validate(format="json", fail_on="warning")' in fix
    generate = mcp_server.texts["generate_code"]
    assert "generate(check=true)" in generate
    assert 'check_output(application="OrderService")' in generate
    assert "--overwrite" in generate  # Only in the sentence that tells what the user can do.
    assert "`--overwrite`" not in generate


# trace: PRD-AI-016
@pytest.mark.parametrize(
    "prompt", [prompts.CREATE_MODEL, prompts.FIX_FINDINGS, prompts.GENERATE_CODE]
)
def test_each_prompt_contains_the_unchanged_lines_of_its_skill(
    prompt: prompts.SkillPrompt,
) -> None:
    body = prompts.skill_text(prompt.skill)
    if prompt.headings:
        body = prompts.sections(body, prompt.headings)
    text = prompt.text().splitlines()
    for line in body.splitlines():
        if any(old in line or line in old for old in prompt.changes):
            continue
        if prompts.for_tools(line) != line:
            continue
        if line.strip() in ("```shell", "```") or line.strip().startswith("dsml "):
            continue
        assert line in text, line


# trace: PRD-AI-016
@pytest.mark.parametrize(
    ("command", "call"),
    [
        ("dsml validate", "validate()"),
        (
            "dsml validate --format json --fail-on warning",
            'validate(format="json", fail_on="warning")',
        ),
        ("dsml init --target fastapi", 'init(target="fastapi")'),
        ("dsml generate --check", "generate(check=true)"),
        ("dsml check-output --infrastructure", "check_output(infrastructure=true)"),
        (
            "dsml trace impact --format json --baseline main",
            'trace(report="impact", format="json", baseline="main")',
        ),
    ],
)
def test_tool_call_gives_the_tool_and_the_arguments_of_a_command_line(
    command: str, call: str
) -> None:
    assert prompts.tool_call(command) == call


# trace: PRD-AI-016
@pytest.mark.parametrize(
    "text",
    [
        "Run `dsml generate --overwrite`.",
        "Run `dsml trace coverage --format html --output coverage.html`.",
        "Run `dsml skills install`.",
        "Use `--overwrite`.",
        "Read `references/missing.md`.",
        "```shell\ndsml mcp\n```",
    ],
)
def test_for_tools_refuses_a_text_with_no_tool_equivalent(text: str) -> None:
    with pytest.raises(ValueError):
        prompts.for_tools(text)


# trace: PRD-AI-016
def test_for_tools_refuses_a_change_that_is_not_in_the_text() -> None:
    with pytest.raises(ValueError, match="does not contain"):
        prompts.for_tools("The skill text.", {"A different sentence.": "New text."})


# trace: PRD-AI-016
def test_sections_refuses_a_missing_heading() -> None:
    with pytest.raises(ValueError, match="no section"):
        prompts.sections(prompts.skill_text("dsml-cli"), ("Missing section",))


# trace: PRD-AI-016, PRD-CORE-028
def test_prompts_are_deterministic(tmp_path: Path) -> None:
    first = _server(tmp_path).texts
    assert first == _server(tmp_path).texts
    assert not any("\r" in text for text in first.values())
