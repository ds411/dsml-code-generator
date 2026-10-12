"""Tests of the modeling skill `dsml-modeling` (story #230).

The tests make sure of these items:

- The frontmatter of `SKILL.md` has a name that agrees with the folder name,
  and a description that is not empty.
- The skill has the reference files of its parts, and `dsml skills install`
  finds the skill.
- Each model pattern in `references/patterns.md` parses and validates with
  no error finding. Each pattern is one model file, and the DSML library is
  also in the model.

The test `tests/test_assist_reference.py` makes sure that the reference files
of the skill are current (PRD-AI-007).

The pattern test starts a private `sysml-grpc` child process.
"""

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from dsml import skills
from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.config import Configuration
from dsml.library import library_document
from dsml.validate.engine import Validator

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "src" / "dsml" / "skills" / "dsml-modeling"
PATTERNS = SKILL / "references" / "patterns.md"

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
FIELD = re.compile(r"^([a-z][a-z0-9_-]*):[ \t]*(.*)$", re.MULTILINE)
BLOCK = re.compile(r"^```([A-Za-z0-9_-]*)[^\n]*\n(.*?)^```$", re.MULTILINE | re.DOTALL)
SECTION = re.compile(r"^## (.+)$", re.MULTILINE)


def _frontmatter() -> dict[str, str]:
    match = FRONTMATTER.match(SKILL.joinpath("SKILL.md").read_text(encoding="utf-8"))
    assert match is not None, "SKILL.md must start with a frontmatter block."
    return {key: value.strip() for key, value in FIELD.findall(match.group(1))}


def _patterns() -> list[tuple[str, str]]:
    """Give the title of the section and the text of each `sysml` block."""
    text = PATTERNS.read_text(encoding="utf-8")
    found: list[tuple[str, str]] = []
    for match in BLOCK.finditer(text):
        if match.group(1) != "sysml":
            continue
        titles = SECTION.findall(text, 0, match.start())
        found.append((titles[-1] if titles else "patterns", match.group(2)))
    return found


PATTERN_LIST = _patterns()


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    with Engine() as service:
        yield service


# trace: PRD-AI-001
def test_frontmatter_name_agrees_with_the_folder_name() -> None:
    assert _frontmatter().get("name") == SKILL.name


# trace: PRD-AI-001
def test_frontmatter_has_a_description() -> None:
    assert _frontmatter().get("description", "") != ""


# trace: PRD-AI-001, PRD-AI-004
def test_skills_install_finds_the_modeling_skill() -> None:
    found = {skill.name: skill for skill in skills.package_skills()}
    paths = {path.as_posix() for path, _ in found[SKILL.name].files}
    assert {
        "SKILL.md",
        "references/parts.txt",
        "references/patterns.md",
        "references/keywords.md",
        "references/rules.md",
        "references/examples.md",
    } <= paths


# trace: PRD-AI-002
def test_skill_refers_to_each_reference_file() -> None:
    text = SKILL.joinpath("SKILL.md").read_text(encoding="utf-8")
    for name in ("keywords.md", "rules.md", "examples.md", "patterns.md"):
        assert f"references/{name}" in text


# trace: PRD-AI-002
def test_there_is_a_pattern_for_each_layer() -> None:
    titles = {title for title, _ in PATTERN_LIST}
    layers = {"Needs layer", "Requirements layer", "Application layer"}
    layers |= {"Infrastructure layer", "Verification layer"}
    assert layers <= titles


# trace: PRD-AI-002
@pytest.mark.parametrize(
    "pattern", [text for _, text in PATTERN_LIST], ids=[title for title, _ in PATTERN_LIST]
)
def test_each_pattern_validates_with_no_error(engine: Engine, pattern: str) -> None:
    name = "src/dsml/skills/dsml-modeling/references/pattern.sysml"
    parsed = engine.parse_texts([library_document(), (name, pattern)])
    assert [str(item) for item in parsed.diagnostics] == []
    ir = build_ir(parsed, [name], ROOT)
    findings = Validator(Configuration()).run(ir)
    assert [f"{item.rule}: {item.message}" for item in findings if item.severity == "error"] == []
