# trace: PRD-AI-007, PRD-CORE-028, PRD-CORE-030
"""Tests of the DSML reference for AI agents (story #228).

The module `dsml.assist.reference` writes the reference from the installed
toolchain. The golden files are in `tests/golden/assist/`. To write them
again, run `uv run python scripts/write_skill_references.py`.
"""

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from dsml import starter
from dsml.adapter import needs, solution
from dsml.assist import reference
from dsml.cli import build_parser
from dsml.library import library_text
from dsml.validate.rules import registry

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "assist"
SKILLS = ROOT / "src" / "dsml" / "skills"


def _load_script() -> ModuleType:
    path = ROOT / "scripts" / "write_skill_references.py"
    spec = importlib.util.spec_from_file_location("write_skill_references", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


script: Any = _load_script()


@pytest.mark.parametrize("name", sorted(reference.PARTS))
def test_part_agrees_with_the_golden_file(name: str) -> None:
    expected = (GOLDEN / f"{name}.md").read_bytes()
    assert reference.part(name).encode("utf-8") == expected, (
        f"The part {name} is not current. Run scripts/write_skill_references.py."
    )


@pytest.mark.parametrize("name", sorted(reference.PARTS))
def test_two_runs_give_the_same_bytes(name: str) -> None:
    assert reference.part(name) == reference.part(name)


@pytest.mark.parametrize("name", sorted(reference.PARTS))
def test_part_is_portable_text(name: str) -> None:
    text = reference.part(name)
    text.encode("utf-8")
    assert "\r" not in text
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert text.startswith(reference.GENERATED_NOTE + "\n")
    assert str(ROOT) not in text
    assert str(Path.home()) not in text


def test_unknown_part_is_an_error() -> None:
    with pytest.raises(ValueError, match='The reference part "unknown" is unknown'):
        reference.part("unknown")


# trace: PRD-AI-007
def test_each_keyword_of_the_library_is_in_the_reference() -> None:
    defined = set(re.findall(r"\bmetadata\s+def\s+(\w+)", library_text()))
    text = reference.keywords()
    listed = set(re.findall(r"^### `(\w+)`$", text, re.MULTILINE))
    assert listed == defined
    assert set(needs.KEYWORDS) | set(solution.KEYWORDS) <= listed
    assert set(reference.KEYWORD_LAYERS) == defined


def test_keyword_has_its_layer_attributes_and_doc() -> None:
    by_name = {keyword.name: keyword for keyword in reference.library_keywords()}
    requirement = by_name["Requirement"]
    assert requirement.layer == "requirements"
    assert requirement.element_kind
    assert requirement.doc == "A requirement. Use it on a requirement usage."
    assert [feature.name for feature in requirement.features] == [
        "title",
        "kind",
        "priority",
        "status",
        "rationale",
        "source",
        "owner",
    ]
    # The features of a general type are also features of the keyword.
    exposed = by_name["Exposed"]
    assert [(f.name, f.default) for f in exposed.features][-1] == ("'public'", "false")
    application = by_name["Application"].features
    assert application[1] == reference.Feature("navigation", "View", "0..*", None, True, True)
    waiver = by_name["Waiver"]
    assert waiver.layer == "all" and not waiver.element_kind
    assert [feature.multiplicity for feature in waiver.features] == ["1", "1", "1", "0..1"]


def test_keyword_with_no_layer_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    layers = dict(reference.KEYWORD_LAYERS)
    del layers["Uses"]
    monkeypatch.setattr(reference, "KEYWORD_LAYERS", layers)
    with pytest.raises(ValueError, match='The keyword "Uses" of the DSML library has no layer'):
        reference.keywords()


# trace: PRD-AI-007
def test_each_rule_of_the_catalog_is_in_the_reference() -> None:
    text = reference.rules()
    listed = re.findall(r"^### `([A-Z]{3}-[0-9]{3})`$", text, re.MULTILINE)
    assert listed == sorted(registry())
    for check in registry().values():
        rule = check.rule
        assert f"- Severity: {rule.severity}\n" in text
        assert f"- Message: {rule.message}\n" in text
        assert f"- Correction: {rule.fix_hint}\n" in text


def test_each_subcommand_is_in_the_reference() -> None:
    text = reference.commands()
    listed = re.findall(r"^## `dsml ([a-z-]+)`$", text, re.MULTILINE)
    parser_help = build_parser().format_help()
    subcommands = re.findall(r"^    ([a-z-]+) ", parser_help, re.MULTILINE)
    assert subcommands
    assert listed == sorted(subcommands)
    assert "| `--format` | `text`, `json`, `sarif` |" in text
    assert "| `--config` | `<file>` |" in text


def test_each_starter_model_is_in_the_reference() -> None:
    text = reference.examples()
    for target in starter.TARGETS:
        model = starter.starter_files(target)[starter.MODEL_FILE].decode("utf-8")
        assert f"`dsml init --target {target}`" in text
        assert model.rstrip("\n") in text


def _skill(folder: Path, name: str, parts: str) -> Path:
    references = folder / name / "references"
    references.mkdir(parents=True)
    (references / reference.PARTS_FILE).write_text(parts, encoding="utf-8")
    return references


def test_skill_reference_files_follow_parts_txt(tmp_path: Path) -> None:
    modeling = _skill(tmp_path, "dsml-modeling", "# The parts of the skill\nkeywords\n\nrules\n")
    (tmp_path / "no-references").mkdir()
    files = reference.skill_reference_files(tmp_path)
    assert list(files) == [modeling / "keywords.md", modeling / "rules.md"]
    assert files[modeling / "rules.md"] == reference.rules().encode("utf-8")


def test_missing_skills_folder_gives_no_files(tmp_path: Path) -> None:
    assert reference.skill_reference_files(tmp_path / "skills") == {}


def test_unknown_part_in_parts_txt_is_an_error(tmp_path: Path) -> None:
    _skill(tmp_path, "dsml-cli", "commands\nusage\n")
    with pytest.raises(ValueError, match='lists the unknown part "usage"'):
        reference.skill_reference_files(tmp_path)


# trace: PRD-AI-007
def test_stale_reference_file_is_found(tmp_path: Path) -> None:
    references = _skill(tmp_path, "dsml-cli", "commands\nexamples\n")
    (references / "commands.md").write_text(reference.commands(), encoding="utf-8")
    (references / "examples.md").write_text("Old text.\n", encoding="utf-8")
    assert list(reference.stale_reference_files(tmp_path)) == [references / "examples.md"]
    (references / "examples.md").unlink()
    assert list(reference.stale_reference_files(tmp_path)) == [references / "examples.md"]


# trace: PRD-AI-007
def test_reference_files_of_the_skills_are_current() -> None:
    stale = [path.relative_to(ROOT).as_posix() for path in reference.stale_reference_files(SKILLS)]
    assert stale == [], (
        f"These reference files are not current: {', '.join(stale)}. "
        "Run scripts/write_skill_references.py."
    )


def test_script_writes_byte_identical_files(tmp_path: Path) -> None:
    runs: list[dict[str, bytes]] = []
    for run in ("first", "second"):
        skills = tmp_path / run / "skills"
        _skill(skills, "dsml-modeling", "examples\nkeywords\nrules\n")
        _skill(skills, "dsml-cli", "commands\n")
        golden = tmp_path / run / "golden"
        assert script.main(["--skills", str(skills), "--golden", str(golden)]) == 0
        root = tmp_path / run
        runs.append(
            {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob("*.md"))
            }
        )
    assert runs[0] == runs[1]
    assert len(runs[0]) == 4 + 4
    assert list(reference.stale_reference_files(tmp_path / "first" / "skills")) == []
