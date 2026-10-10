"""Tests of the DSML model of the PRD set (story #15).

These tests start a private `sysml-grpc` child process. If the binary is not
in the cache, the `opensysml` client downloads it one time.
"""

import csv
from collections.abc import Iterator
from pathlib import Path

import pytest

from dsml.adapter.engine import Engine, ModelElement, ParsedModel
from dsml.library import library_document

ROOT = Path(__file__).resolve().parent.parent
PRD_MODEL = ROOT / "docs" / "model" / "prd"
REQUIREMENTS_CSV = ROOT / "docs" / "index" / "requirements.csv"


def _prd_documents() -> list[tuple[str, str]]:
    """Give each PRD model file as a (name, text) pair, with a name relative to the root."""
    return [
        (path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8"))
        for path in sorted(PRD_MODEL.glob("*.sysml"))
    ]


@pytest.fixture(scope="module")
def prd_model() -> Iterator[ParsedModel]:
    with Engine() as engine:
        yield engine.parse_texts([library_document(), *_prd_documents()])


def _packages() -> list[str]:
    """Give the qualified names of the top-level packages of the PRD model files."""
    names: list[str] = []
    for _, text in _prd_documents():
        first = text.lstrip().split(maxsplit=2)
        assert first[0] == "package", "Each PRD model file must start with a package."
        names.append(first[1].rstrip("{"))
    return sorted(names)


def _requirements(model: ParsedModel) -> dict[str, list[ModelElement]]:
    """Give the requirement usages of the PRD model, grouped by short name."""
    result: dict[str, list[ModelElement]] = {}
    for package in _packages():
        for element in model.owned_elements(package, kinds={"RequirementUsage"}):
            result.setdefault(element.short_name, []).append(element)
    return result


def _csv_rows() -> dict[str, str]:
    """Give the requirement text of each row of the requirement index, by ID."""
    with REQUIREMENTS_CSV.open(encoding="utf-8", newline="") as file:
        return {row["id"]: row["requirement"] for row in csv.DictReader(file)}


def _plain(text: str) -> str:
    """Remove the code formatting (back quotes) from a Markdown text."""
    return text.replace("`", "")


# trace: PRD-DSML-004, PRD-TOP-011
def test_prd_model_parses_and_resolves(prd_model: ParsedModel) -> None:
    assert [str(item) for item in prd_model.diagnostics] == []


# trace: PRD-TOP-011
def test_each_requirement_of_the_index_has_one_model_element(prd_model: ParsedModel) -> None:
    requirements = _requirements(prd_model)
    missing = sorted(set(_csv_rows()) - set(requirements))
    duplicates = sorted(key for key, items in requirements.items() if len(items) > 1)
    assert missing == []
    assert duplicates == []


# trace: PRD-TOP-011
def test_each_model_requirement_is_in_the_index(prd_model: ParsedModel) -> None:
    assert sorted(set(_requirements(prd_model)) - set(_csv_rows())) == []


# trace: PRD-TOP-011
def test_model_text_agrees_with_the_index(prd_model: ParsedModel) -> None:
    requirements = _requirements(prd_model)
    differences = [
        f"{key}: index {_plain(text)!r}, model {requirements[key][0].documentation!r}"
        for key, text in sorted(_csv_rows().items())
        if key in requirements and requirements[key][0].documentation != _plain(text)
    ]
    assert differences == []
