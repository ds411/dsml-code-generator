"""Tests of the user guide in `docs/guide/` (story #237).

For each page of the guide, the tests make sure of these items:

- Each relative link goes to a file that exists.
- Each code block with the language `sysml` parses and validates with no
  error finding, together with the other `sysml` blocks of the same page.
  Each block is one model file, and the DSML library is also in the model.
- Each `dsml` command line uses a subcommand and options that the parser of
  the CLI accepts. A command line is a line that starts with `dsml ` in a
  code block with the language `shell`, or an inline code span that starts
  with `dsml `. The name of a subcommand alone, for example `dsml trace` in a
  heading of the reference, is a name and not a command line. The parser
  must know the subcommand.

The `sysml` test starts a private `sysml-grpc` child process.
"""

import argparse
import re
import shlex
from collections.abc import Iterator
from pathlib import Path

import pytest

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.cli import build_parser
from dsml.config import Configuration
from dsml.errors import UsageError
from dsml.library import library_document
from dsml.validate.engine import Validator

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "guide"
PAGES = sorted(GUIDE.rglob("*.md"))

BLOCK = re.compile(r"^```([A-Za-z0-9_-]*)[^\n]*\n(.*?)^```$", re.MULTILINE | re.DOTALL)
LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
INLINE_CODE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
EXTERNAL = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def _name(page: Path) -> str:
    return page.relative_to(ROOT).as_posix()


def _blocks(text: str, language: str) -> list[str]:
    return [match.group(2) for match in BLOCK.finditer(text) if match.group(1) == language]


def _prose(text: str) -> str:
    """Give the text of a page with no fenced code blocks."""
    return BLOCK.sub("", text)


def _command_lines(text: str) -> list[str]:
    lines = [
        line.strip()
        for block in _blocks(text, "shell")
        for line in block.splitlines()
        if line.strip().startswith("dsml ")
    ]
    lines += [span for span in INLINE_CODE.findall(_prose(text)) if span.startswith("dsml ")]
    return lines


SYSML_PAGES = [page for page in PAGES if _blocks(page.read_text(encoding="utf-8"), "sysml")]


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    with Engine() as service:
        yield service


def test_the_guide_has_the_pages_of_the_index() -> None:
    names = {page.relative_to(GUIDE).as_posix() for page in PAGES}
    expected = {
        "README.md",
        "concepts.md",
        "glossary.md",
        "modeling-tutorial.md",
        "generated-code.md",
        "reports.md",
        "reference/README.md",
        "ai-assistance.md",
    }
    assert expected <= names


# trace: PRD-TOP-013
@pytest.mark.parametrize("page", PAGES, ids=_name)
def test_each_relative_link_goes_to_a_file_that_exists(page: Path) -> None:
    missing: list[str] = []
    for target in LINK.findall(_prose(page.read_text(encoding="utf-8"))):
        if EXTERNAL.match(target) or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        if not (page.parent / path).exists():
            missing.append(target)
    assert missing == []


# trace: PRD-TOP-013
@pytest.mark.parametrize("page", SYSML_PAGES, ids=_name)
def test_the_sysml_blocks_of_a_page_validate_with_no_error(engine: Engine, page: Path) -> None:
    blocks = _blocks(page.read_text(encoding="utf-8"), "sysml")
    documents = [
        (f"{_name(page)}/block-{number}.sysml", text) for number, text in enumerate(blocks, 1)
    ]
    parsed = engine.parse_texts([library_document(), *documents])
    assert [str(item) for item in parsed.diagnostics] == []
    ir = build_ir(parsed, [name for name, _ in documents], ROOT)
    findings = Validator(Configuration()).run(ir)
    assert [f"{item.rule}: {item.message}" for item in findings if item.severity == "error"] == []


def _subcommand_names() -> set[str]:
    """Give the names of the subcommands of the parser of the CLI."""
    for action in build_parser()._actions:  # pyright: ignore[reportPrivateUsage]
        if isinstance(action, argparse._SubParsersAction):  # pyright: ignore[reportPrivateUsage]
            return set(action.choices)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    return set()


# trace: PRD-TOP-013, PRD-CORE-001
@pytest.mark.parametrize("page", PAGES, ids=_name)
def test_each_dsml_command_line_parses(page: Path) -> None:
    names = _subcommand_names()
    for line in _command_lines(page.read_text(encoding="utf-8")):
        words = shlex.split(line)[1:]
        if len(words) == 1 and words[0] in names:
            continue
        try:
            build_parser().parse_args(shlex.split(line)[1:])
        except UsageError as error:
            pytest.fail(f"{line}: {error}")


# trace: PRD-TOP-013
def test_the_glossary_has_each_term_of_the_project_dictionary() -> None:
    prd = (ROOT / "docs" / "prd" / "00-top-level-prd.md").read_text(encoding="utf-8")
    section = prd.split("## Project dictionary", 1)[1]
    terms = re.findall(r"^\| ([^|]+?) \| Technical (?:noun|verb) \|", section, re.MULTILINE)
    glossary = (GUIDE / "glossary.md").read_text(encoding="utf-8")
    entries = set(re.findall(r"^\| ([^|]+?) \|", glossary, re.MULTILINE))
    assert terms
    assert [term for term in terms if term not in entries] == []
