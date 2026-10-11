"""Tests of the rule STR-013 (story #61).

Each rule has one model that it accepts and one model that it rejects
(PRD-VAL-008). The models are in `tests/models/rules/STR-013/`. The output
folders `accept/` and `reject/` hold the schema snapshot of each model.
"""

from pathlib import Path, PurePosixPath

from conftest import RULE_MODELS, RunRule

from dsml.config import Application, Configuration
from dsml.ir.model import Location

FOLDER = RULE_MODELS / "STR-013"
REJECT = "tests/models/rules/STR-013/reject.sysml"


def _configuration(output: str | None) -> Configuration:
    path = None if output is None else PurePosixPath(output)
    return Configuration(path=FOLDER / "dsml.toml", applications=(Application("shopApi", path),))


# trace: PRD-VAL-008, PRD-VAL-015
def test_str_013_accepts_its_accept_model(run_rule: RunRule) -> None:
    assert run_rule("STR-013", "accept.sysml", _configuration("accept")) == ()


# trace: PRD-VAL-008, PRD-VAL-015, PRD-APP-127
def test_str_013_rejects_its_reject_model(run_rule: RunRule) -> None:
    findings = run_rule("STR-013", "reject.sysml", _configuration("reject"))
    assert [(item.message, item.location, item.element) for item in findings] == [
        (
            'The model drops or renames the column "email" of the table "customer", '
            "with no #Destructive metadata.",
            Location(REJECT, 9, 5),
            "Shop::Customer",
        ),
        (
            'The model drops or renames the table "item" of the application shopApi, '
            "with no #Destructive metadata.",
            Location(REJECT, 20, 5),
            "Shop::shopApi",
        ),
        (
            'The model drops or renames the table "legacy" of the application shopApi, '
            "with no #Destructive metadata.",
            Location(REJECT, 20, 5),
            "Shop::shopApi",
        ),
    ]
    assert {(item.rule, item.severity) for item in findings} == {("STR-013", "error")}


def test_str_013_accepts_a_model_with_no_snapshot(run_rule: RunRule, tmp_path: Path) -> None:
    assert run_rule("STR-013", "reject.sysml", _configuration(str(tmp_path / "none"))) == ()
    assert run_rule("STR-013", "reject.sysml", _configuration(None)) == ()
    assert run_rule("STR-013", "reject.sysml") == ()


def test_str_013_reports_a_snapshot_that_is_not_correct(run_rule: RunRule, tmp_path: Path) -> None:
    (tmp_path / ".dsml").mkdir()
    (tmp_path / ".dsml" / "schema-snapshot.json").write_text("[]", encoding="utf-8")
    findings = run_rule("STR-013", "accept.sysml", _configuration(str(tmp_path)))
    assert len(findings) == 1
    assert "is not correct. The top level must be a JSON object" in findings[0].message
    assert findings[0].element == "Shop::shopApi"
