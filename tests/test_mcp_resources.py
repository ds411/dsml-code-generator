"""Tests of the MCP resources (story #234).

An MCP client in the test process connects to the server and reads the
resources. The tests need the MCP Python SDK, so they have the mark `mcp`.
"""

from pathlib import Path

import pytest

pytest.importorskip("mcp", reason="The MCP Python SDK is not installed.")

import anyio
from mcp import Client
from mcp_types import Resource, TextResourceContents

from dsml import starter
from dsml.mcp import resources, server
from dsml.mcp.project import Project

pytestmark = pytest.mark.mcp

SKILLS = Path(__file__).parents[1] / "src" / "dsml" / "skills"
"""The skill folders in the repository."""


def _read_all(root: Path) -> tuple[dict[str, Resource], dict[str, str]]:
    """Give each resource of the server by URI, and the text that the client reads for it."""

    async def read() -> tuple[dict[str, Resource], dict[str, str]]:
        built = server.build_server(Project.open(root), "0.0.0")
        with anyio.fail_after(60):
            async with Client(built) as client:
                found = {str(item.uri): item for item in (await client.list_resources()).resources}
                texts: dict[str, str] = {}
                for uri in found:
                    contents = (await client.read_resource(uri)).contents
                    assert len(contents) == 1
                    assert isinstance(contents[0], TextResourceContents)
                    texts[uri] = contents[0].text
                return found, texts

    return anyio.run(read)


# trace: PRD-AI-015
def test_server_has_one_resource_for_each_reference_part_and_each_example_model(
    tmp_path: Path,
) -> None:
    found, _ = _read_all(tmp_path)
    expected = {
        "dsml://reference/commands": "commands",
        "dsml://reference/configuration": "configuration",
        "dsml://reference/examples": "examples",
        "dsml://reference/keywords": "keywords",
        "dsml://reference/patterns": "patterns",
        "dsml://reference/rules": "rules",
        "dsml://examples/fastapi": "example-fastapi",
        "dsml://examples/nextjs": "example-nextjs",
        "dsml://examples/react": "example-react",
    }
    assert {uri: item.name for uri, item in found.items()} == expected
    assert all(item.description and item.title for item in found.values())
    assert {item.mime_type for uri, item in found.items() if "/reference/" in uri} == {
        "text/markdown"
    }


# trace: PRD-AI-015, PRD-AI-007
def test_each_reference_resource_is_byte_identical_to_the_file_in_the_skill_folder(
    tmp_path: Path,
) -> None:
    _, texts = _read_all(tmp_path)
    for file in resources.REFERENCE:
        uri = resources.reference_uri(file.name)
        expected = (SKILLS / file.skill / "references" / f"{file.name}.md").read_bytes()
        assert texts[uri].encode("utf-8") == expected, uri
    # The two skills have the same rule catalog, so the resource agrees with both.
    for skill in ("dsml-cli", "dsml-modeling"):
        rules = (SKILLS / skill / "references" / "rules.md").read_bytes()
        assert texts["dsml://reference/rules"].encode("utf-8") == rules


# trace: PRD-AI-015
def test_each_reference_file_of_a_skill_has_a_resource() -> None:
    files = {path.stem for path in SKILLS.glob("*/references/*.md")}
    assert files == {file.name for file in resources.REFERENCE}
    for file in resources.REFERENCE:
        assert (SKILLS / file.skill / "references" / f"{file.name}.md").is_file()


# trace: PRD-AI-015, PRD-CORE-001
def test_each_example_resource_is_the_starter_model_of_its_target(tmp_path: Path) -> None:
    found, texts = _read_all(tmp_path)
    for target in starter.TARGETS:
        uri = resources.example_uri(target)
        model = starter.starter_files(target)[starter.MODEL_FILE]
        assert texts[uri].encode("utf-8") == model
        assert found[uri].mime_type == "text/plain"


# trace: PRD-AI-015, PRD-CORE-028
def test_resources_do_not_depend_on_the_project_folder(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (second / "dsml.toml").write_text("[model]\n", encoding="utf-8")
    assert _read_all(first)[1] == _read_all(second)[1]
