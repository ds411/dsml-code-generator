# trace: PRD-AI-001, PRD-AI-003, PRD-AI-007, PRD-AI-018
"""Tests of the CLI skill `dsml-cli` (story #231).

The skill is in `src/dsml/skills/dsml-cli/`. The test of story #228,
`tests/test_assist_reference.py`, makes sure that its reference files are
current. To write them again, run `uv run python scripts/write_skill_references.py`.
"""

import re
import shlex
from pathlib import Path

import pytest

from dsml import skills
from dsml.assist import reference
from dsml.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "src" / "dsml" / "skills" / "dsml-cli"
SKILL = FOLDER / skills.SKILL_FILE

_FENCE = re.compile(r"^\s*```(\w*)\n(.*?)^\s*```", re.DOTALL | re.MULTILINE)
_SPAN = re.compile(r"`(dsml [^`]*)`")


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict[str, str]:
    """Give the keys of the YAML frontmatter. The skill uses only plain one-line values."""
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert match is not None, "SKILL.md must start with a YAML frontmatter."
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        assert separator, f"The frontmatter line {line!r} has no key."
        fields[key.strip()] = value.strip()
    return fields


def _command_lines() -> list[str]:
    """Give each `dsml` command line of the skill: in a shell block or in a code span."""
    text = _text()
    lines: list[str] = []
    for language, block in _FENCE.findall(text):
        if language == "shell":
            lines.extend(line.strip() for line in block.splitlines() if line.strip())
    without_blocks = _FENCE.sub("", text)
    lines.extend(_SPAN.findall(without_blocks))
    return lines


def test_frontmatter_names_the_folder() -> None:
    fields = _frontmatter(_text())
    assert fields.get("name") == FOLDER.name
    assert fields.get("description")


def test_package_contains_the_skill() -> None:
    names = [skill.name for skill in skills.package_skills()]
    assert FOLDER.name in names


def test_parts_of_the_skill() -> None:
    parts = (FOLDER / "references" / reference.PARTS_FILE).read_text(encoding="utf-8")
    assert parts.split() == ["commands", "rules"]


def test_skill_has_command_lines() -> None:
    lines = _command_lines()
    commands = {shlex.split(line)[1] for line in lines}
    assert {"init", "validate", "generate", "check-output", "trace"} <= commands


# trace: PRD-AI-003, PRD-CORE-001
@pytest.mark.parametrize("line", sorted(set(_command_lines())))
def test_command_line_parses(line: str) -> None:
    words = shlex.split(line)
    assert words[0] == "dsml", f"Each line of a shell block must be a dsml command: {line}"
    parser = build_parser()
    try:
        args = parser.parse_args(words[1:])
    except SystemExit as error:
        pytest.fail(f"The parser does not accept the command line {line!r} ({error}).")
    assert args.command == words[1]


# trace: PRD-CORE-042, PRD-CORE-043
def test_skill_tells_the_agent_about_generated_files() -> None:
    text = _text()
    assert "Do not edit a generated file." in text
    assert "Do not use `dsml generate --overwrite` without the approval of the user." in text
    assert "Do not add a waiver without a reason from the user." in text


def test_skill_is_portable_text() -> None:
    data = SKILL.read_bytes()
    data.decode("utf-8")
    assert b"\r" not in data
    assert data.endswith(b"\n") and not data.endswith(b"\n\n")
