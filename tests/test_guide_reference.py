"""Tests of the reference pages of the user guide (story #240).

The script `scripts/write_guide_reference.py` writes the pages in
`docs/guide/reference/` with the module `dsml.assist.reference`. If a test
fails because a page is not current, run
`uv run python scripts/write_guide_reference.py`.
"""

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

from dsml.assist import reference
from dsml.validate.rules import registry

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "docs" / "guide" / "reference"


def _script() -> ModuleType:
    path = ROOT / "scripts" / "write_guide_reference.py"
    spec = importlib.util.spec_from_file_location("write_guide_reference", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCRIPT = _script()


# trace: PRD-TOP-013, PRD-AI-007
@pytest.mark.parametrize("name", SCRIPT.PAGES)
def test_each_reference_page_is_current(name: str) -> None:
    path = FOLDER / f"{name}.md"
    assert path.is_file(), f"The page {name}.md is missing. Run scripts/write_guide_reference.py."
    assert path.read_bytes() == SCRIPT.page(name).encode("utf-8"), (
        f"The page {name}.md is not current. Run scripts/write_guide_reference.py."
    )


# trace: PRD-TOP-013
def test_the_pages_are_the_keywords_the_rules_and_the_commands() -> None:
    assert sorted(SCRIPT.PAGES) == ["commands", "keywords", "rules"]
    assert set(SCRIPT.PAGES) <= set(reference.PARTS)


# trace: PRD-TOP-013, PRD-AI-007
def test_a_changed_page_is_not_current(tmp_path: Path) -> None:
    SCRIPT.main(["--folder", str(tmp_path)])
    pages = SCRIPT.pages(tmp_path)
    assert all(path.read_bytes() == content for path, content in pages.items())
    changed = tmp_path / "rules.md"
    changed.write_bytes(changed.read_bytes() + b"\nA change.\n")
    assert changed.read_bytes() != pages[changed]


# trace: PRD-TOP-013, PRD-CORE-028
def test_two_runs_give_the_same_bytes(tmp_path: Path) -> None:
    first = SCRIPT.pages(tmp_path)
    second = SCRIPT.pages(tmp_path)
    assert first == second
    for content in first.values():
        assert b"\r" not in content
        assert content.endswith(b"\n")
        assert str(ROOT).encode("utf-8") not in content


# trace: PRD-TOP-013
def test_each_page_has_the_note_and_the_links_to_the_index() -> None:
    for name in SCRIPT.PAGES:
        lines = SCRIPT.page(name).splitlines()
        assert lines[0] == SCRIPT.PAGE_NOTE
        assert lines[2] == SCRIPT.BACK_LINK
        assert "This part" not in "\n".join(lines[:8])


# trace: PRD-TOP-013
def test_each_rule_has_a_correction() -> None:
    text = SCRIPT.page("rules")
    checks = registry()
    assert checks
    for check in checks.values():
        rule = check.rule
        assert rule.fix_hint.strip(), f"The rule {rule.id} has no correction."
        entry = re.search(
            rf"^### `{re.escape(rule.id)}`\n(.*?)(?=^##|\Z)", text, re.MULTILINE | re.DOTALL
        )
        assert entry is not None, f"The rule {rule.id} is not on the page."
        assert f"- Correction: {rule.fix_hint}" in entry.group(1)


# trace: PRD-TOP-013
def test_the_index_page_names_each_reference_page() -> None:
    index = (FOLDER / "README.md").read_text(encoding="utf-8")
    for name in SCRIPT.PAGES:
        assert f"({name}.md)" in index
