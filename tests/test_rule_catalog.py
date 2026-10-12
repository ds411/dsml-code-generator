"""Tests of the full rule catalog and of the golden findings (story #68).

- The registry contains each rule of the catalog in
  `docs/prd/06-validation-prd.md`, with its default severity (PRD-VAL-015).
  The catalog has two sections: the rules of phase 1 and the rules that
  phase 2 adds (PRD-VAL-016, story #163).
- Each rule has one model that it accepts and one model that it rejects in
  `tests/models/rules/<rule>/` (PRD-VAL-008). The test module of each
  category runs the rule on these models.
- The findings of the reference models agree with the golden files in
  `tests/golden/validate/` (PRD-CORE-028, PRD-CORE-030).
"""

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from conftest import RULE_MODELS

from dsml.validate.rule import RULE_ID
from dsml.validate.rules import registry

ROOT = Path(__file__).resolve().parent.parent
VALIDATION_PRD = ROOT / "docs" / "prd" / "06-validation-prd.md"
CATALOG_HEADINGS = ("## Rule catalog for phase 1", "## Rule catalog additions for phase 2")
CATALOG_ROW = re.compile(r"\| (?P<rule>[A-Z]{3}-[0-9]{3}) \| (?P<severity>error|warning|info) \|")


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "write_golden_findings", ROOT / "scripts/write_golden_findings.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


write_golden_findings: Any = _load_script()


def _catalog() -> dict[str, str]:
    """Give the default severity of each rule in the catalog tables of the validation PRD."""
    text = VALIDATION_PRD.read_text(encoding="utf-8")
    catalog: dict[str, str] = {}
    for heading in CATALOG_HEADINGS:
        section = text.split(heading, 1)[1].split("\n## ", 1)[0]
        for line in section.splitlines():
            found = CATALOG_ROW.match(line)
            if found:
                rule = found["rule"]
                assert rule not in catalog, f"The catalog has the rule {rule} twice."
                catalog[rule] = found["severity"]
    return catalog


# trace: PRD-VAL-002, PRD-VAL-015, PRD-VAL-016
def test_registry_contains_each_rule_of_the_catalog_with_its_severity() -> None:
    catalog = _catalog()
    assert len(catalog) == 46
    rules = {rule_id: check.rule.severity for rule_id, check in registry().items()}
    assert rules == catalog


# trace: PRD-VAL-002
def test_each_rule_id_has_the_form_of_prd_val_002() -> None:
    assert all(RULE_ID.fullmatch(rule_id) for rule_id in registry())


# trace: PRD-VAL-008
@pytest.mark.parametrize("rule", sorted(registry()))
def test_rule_has_an_accept_model_and_a_reject_model(rule: str) -> None:
    folder = RULE_MODELS / rule
    assert (folder / "accept.sysml").is_file(), f"{rule} has no model accept.sysml."
    assert (folder / "reject.sysml").is_file(), f"{rule} has no model reject.sysml."


# trace: PRD-VAL-008
def test_each_rule_model_folder_has_a_rule() -> None:
    folders = sorted(path.name for path in RULE_MODELS.iterdir() if path.is_dir())
    assert folders == sorted(registry())


# trace: PRD-VAL-008
@pytest.mark.parametrize("rule", sorted(registry()))
def test_a_test_module_runs_the_rule_on_its_models(rule: str) -> None:
    # A test module must name the rule. The test module of each category
    # runs the rule on accept.sysml and on reject.sysml.
    texts = [
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "tests").glob("test_*.py"))
        if path.name != Path(__file__).name
    ]
    assert any(f'"{rule}"' in text for text in texts), f"No test module names the rule {rule}."


# trace: PRD-CORE-028, PRD-CORE-030, PRD-VAL-006, PRD-VAL-007
@pytest.mark.parametrize("report_format", sorted(write_golden_findings.FORMATS))
@pytest.mark.parametrize("name", sorted(write_golden_findings.REFERENCE_MODELS))
def test_findings_of_reference_model_agree_with_golden_file(
    name: str, report_format: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(ROOT)
    output = tmp_path / "findings"
    assert write_golden_findings.validate(name, report_format, output) in (0, 1)
    golden: Path = write_golden_findings.golden_file(name, report_format)
    assert output.read_bytes() == golden.read_bytes(), (
        f"The findings of the model {name} are not the same as {golden.relative_to(ROOT)}. "
        "If the change is correct, run scripts/write_golden_findings.py."
    )


# trace: PRD-VAL-003
def test_example_model_has_no_error_finding() -> None:
    # The PRD model can have error findings until milestone M7 corrects them.
    data = json.loads(write_golden_findings.golden_file("order-service", "json").read_bytes())
    assert data["summary"]["error"] == 0
