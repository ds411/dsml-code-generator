"""Tests of the waivers and the rules STR-014 and STR-015 (story #67)."""

import json
import os
import shutil
import subprocess
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import jsonschema
import pytest
from conftest import PROJECT_ROOT, RULE_MODELS, RunRule
from jsonschema.protocols import Validator as SchemaValidator

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.cli import main
from dsml.config import Configuration
from dsml.ir.model import Finding, Ir, Location
from dsml.library import library_document
from dsml.validate.engine import Validation, Validator
from dsml.validate.report import json_report, text_report
from dsml.validate.rules import registry
from dsml.validate.sarif import sarif_report
from dsml.validate.waivers import Waiver, apply_waivers, check_date, commit_date

TODAY = date(2026, 6, 1)
"""The date of the expiry check in the tests."""

SARIF_SCHEMA = PROJECT_ROOT / "tests" / "schemas" / "sarif-schema-2.1.0.json"
WAIVER_RULES = ("COV-003", "STR-014", "STR-015")


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    with Engine() as service:
        yield service


def _ir(engine: Engine, rule: str, model: str) -> Ir:
    path = RULE_MODELS / rule / model
    name = path.relative_to(PROJECT_ROOT).as_posix()
    parsed = engine.parse_texts([library_document(), (name, path.read_text(encoding="utf-8"))])
    return build_ir(parsed, [name])


def _validate(engine: Engine, rule: str, model: str, today: date | None = TODAY) -> Validation:
    """Run COV-003, STR-014 and STR-015 on a rule model."""
    rules = {rule_id: registry()[rule_id] for rule_id in WAIVER_RULES}
    return Validator(Configuration(), rules).validate(_ir(engine, rule, model), today=today)


def _keys(findings: tuple[Finding, ...]) -> list[tuple[str, str | None]]:
    return [(item.rule, item.element) for item in findings]


# trace: PRD-VAL-015
def test_registry_contains_str_014_and_str_015() -> None:
    rules = registry()
    assert rules["STR-014"].rule.severity == "warning"
    assert rules["STR-015"].rule.severity == "error"


# trace: PRD-VAL-009
def test_waiver_stops_its_rule_on_its_element_only(engine: Engine) -> None:
    result = _validate(engine, "STR-014", "accept.sysml")
    assert _keys(result.findings) == [("COV-003", "R-002")]
    assert [(item.finding.rule, item.finding.element) for item in result.waived] == [
        ("COV-003", "R-001")
    ]
    waiver = result.waived[0].waiver
    assert (waiver.reason, waiver.owner, waiver.expires) == (
        "The API comes in the next release.",
        "Order team",
        "2027-01-31",
    )


# trace: PRD-VAL-009
def test_waiver_does_not_stop_a_different_rule() -> None:
    waiver = Waiver("R-001", "COV-004", "Later.", "Team", None, None)
    findings = (Finding("COV-003", "warning", "W.", None, "R-001"),)
    assert apply_waivers(findings, [waiver], TODAY) == (findings, ())


# trace: PRD-VAL-010
def test_waiver_applies_on_its_expires_date(engine: Engine) -> None:
    result = _validate(engine, "STR-014", "reject.sysml", date(2026, 1, 31))
    assert _keys(result.findings) == [("COV-003", "R-002")]
    assert len(result.waived) == 1


# trace: PRD-VAL-008, PRD-VAL-010
def test_str_014_accepts_its_accept_model(run_rule: RunRule, engine: Engine) -> None:
    assert run_rule("STR-014", "accept.sysml") == ()
    assert "STR-014" not in {
        item.rule for item in _validate(engine, "STR-014", "accept.sysml").findings
    }


# trace: PRD-VAL-008, PRD-VAL-010
def test_expired_waiver_gives_str_014_and_the_original_finding(engine: Engine) -> None:
    result = _validate(engine, "STR-014", "reject.sysml")
    assert result.waived == ()
    assert sorted(_keys(result.findings)) == [
        ("COV-003", "R-001"),
        ("COV-003", "R-002"),
        ("STR-014", "R-001"),
    ]
    [expired] = [item for item in result.findings if item.rule == "STR-014"]
    assert expired.severity == "warning"
    assert expired.message == (
        "The waiver of COV-003 on R-001 expired on 2026-01-31. The date of the check is 2026-06-01."
    )
    assert expired.location is not None
    assert expired.location.file == "tests/models/rules/STR-014/reject.sysml"


# trace: PRD-VAL-010
def test_no_date_expires_no_waiver(engine: Engine) -> None:
    result = _validate(engine, "STR-014", "reject.sysml", None)
    assert _keys(result.findings) == [("COV-003", "R-002")]


# trace: PRD-VAL-008
def test_str_015_accepts_its_accept_model(run_rule: RunRule) -> None:
    assert run_rule("STR-015", "accept.sysml") == ()


# trace: PRD-VAL-008, PRD-DSML-055
def test_str_015_rejects_its_reject_model(run_rule: RunRule) -> None:
    findings = run_rule("STR-015", "reject.sysml")
    assert [(item.element, item.message) for item in findings] == [
        ("R-001", "The waiver on R-001 has no reason."),
        ("R-002", "The waiver on R-002 has no owner."),
        ("R-003", "The waiver on R-003 names the rule COV-999. This rule does not exist."),
        (
            "R-004",
            'The waiver on R-004 has the expires value "31.01.2027". It is not a date YYYY-MM-DD.',
        ),
    ]
    assert {item.severity for item in findings} == {"error"}


# trace: PRD-VAL-009
def test_waiver_with_a_problem_stops_no_finding(engine: Engine) -> None:
    result = _validate(engine, "STR-015", "reject.sysml")
    assert result.waived == ()
    assert {key for key in _keys(result.findings) if key[0] == "COV-003"} == {
        ("COV-003", "R-001"),
        ("COV-003", "R-002"),
        ("COV-003", "R-003"),
        ("COV-003", "R-004"),
    }


# trace: PRD-VAL-009
def test_waiver_does_not_stop_str_014_or_str_015() -> None:
    waivers = [
        Waiver("R-001", "STR-014", "Later.", "Team", None, None),
        Waiver("R-001", "STR-015", "Later.", "Team", None, None),
    ]
    findings = (
        Finding("STR-014", "warning", "W.", None, "R-001"),
        Finding("STR-015", "error", "E.", None, "R-001"),
    )
    assert apply_waivers(findings, waivers, TODAY) == (findings, ())


# trace: PRD-VAL-006, PRD-VAL-009
def test_reports_list_the_waived_findings_in_a_separate_group(engine: Engine) -> None:
    result = _validate(engine, "STR-014", "accept.sysml")
    rules = registry()
    text = text_report(result.findings, rules, result.waived)
    file = "tests/models/rules/STR-014/accept.sysml"
    assert text.endswith(
        "Findings: 0 errors, 1 warning, 0 info.\n"
        "Waived findings: 1.\n"
        f"{file}:18:5: warning: COV-003: The requirement R-001 has the status "
        '"approved" but no satisfying element.\n'
        "  waiver: The API comes in the next release. (owner: Order team, expires 2027-01-31)\n"
    )
    data = json.loads(json_report(result.findings, rules, result.waived))
    assert data["summary"] == {"error": 0, "info": 0, "warning": 1, "waived": 1}
    [waived] = data["waived"]
    assert waived["element"] == "R-001"
    assert waived["waiver"] == {
        "expires": "2027-01-31",
        "owner": "Order team",
        "reason": "The API comes in the next release.",
        "rule": "COV-003",
    }


def _sarif_validator() -> SchemaValidator:
    return jsonschema.Draft4Validator(json.loads(SARIF_SCHEMA.read_text(encoding="utf-8")))


# trace: PRD-VAL-006, PRD-VAL-009
def test_sarif_gives_the_waived_finding_as_a_suppression(engine: Engine) -> None:
    result = _validate(engine, "STR-014", "accept.sysml")
    text = sarif_report(result.findings, registry(), "1.2.3", "", result.waived)
    data = json.loads(text)
    _sarif_validator().validate(data)
    results = data["runs"][0]["results"]
    assert ["suppressions" in item for item in results] == [False, True]
    assert results[1]["suppressions"] == [
        {
            "justification": "The API comes in the next release.",
            "kind": "inSource",
            "properties": {"expires": "2027-01-31", "owner": "Order team"},
        }
    ]


def _git(folder: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True)


def _commit(folder: Path, when: str) -> None:
    _git(folder, "init", "--quiet")
    _git(folder, "add", ".")
    environment = {"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when}
    subprocess.run(
        [
            "git",
            "-C",
            str(folder),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Model",
        ],
        check=True,
        capture_output=True,
        env={**os.environ, **environment},
    )


# trace: PRD-VAL-010, PRD-CORE-028
def test_check_date_is_the_commit_date_of_head(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    assert commit_date(tmp_path) is None
    _commit(tmp_path, "2026-03-04T23:30:00-02:00")
    assert commit_date(tmp_path) == date(2026, 3, 5)
    waiver_ir = Ir()
    assert check_date(waiver_ir, tmp_path) is None
    assert check_date(waiver_ir, tmp_path, TODAY) == TODAY


def _project(root: Path, model: Path) -> None:
    (root / "model").mkdir()
    shutil.copyfile(model, root / "model" / model.name)
    (root / "dsml.toml").write_text(
        'schema = 1\n\n[model]\npaths = ["model"]\n\n[rules.severity]\n"COV-004" = "off"\n',
        encoding="utf-8",
    )


# trace: PRD-VAL-009, PRD-VAL-010
def test_validate_uses_the_commit_date_or_the_date_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _project(tmp_path, RULE_MODELS / "STR-014" / "reject.sysml")
    _commit(tmp_path, "2026-01-31T12:00:00+00:00")
    monkeypatch.chdir(tmp_path)
    assert main(["validate", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [item["element"] for item in data["waived"]] == ["R-001"]
    assert main(["validate", "--format", "json", "--date", "2026-02-01"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["waived"] == []
    assert sorted((item["rule"], item["element"]) for item in data["findings"]) == [
        ("COV-003", "R-001"),
        ("COV-003", "R-002"),
        ("STR-014", "R-001"),
    ]


# trace: PRD-VAL-010
def test_date_option_must_be_a_date(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", "--date", "31.01.2027"]) == 2
    assert '"31.01.2027" is not a date. Use the form YYYY-MM-DD.' in capsys.readouterr().err


# trace: PRD-VAL-003, PRD-VAL-009
def test_waived_error_does_not_stop_generate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The requirement R-002 has the status "verified" but no verification.
    # Thus COV-005 gives an error on R-002, and the waiver of R-002 stops it.
    text = (RULE_MODELS / "STR-015" / "accept.sysml").read_text(encoding="utf-8")
    before = 'Status::approved;\n        frame seeOrders;\n        @Waiver { rule = "COV-004"'
    after = 'Status::verified;\n        frame seeOrders;\n        @Waiver { rule = "COV-005"'
    assert before in text
    model = tmp_path / "waived.sysml"
    model.write_text(text.replace(before, after), encoding="utf-8")
    _project(tmp_path, model)
    monkeypatch.chdir(tmp_path)
    assert main(["validate", "--date", "2026-06-01"]) == 0
    out = capsys.readouterr().out
    assert "Findings: 0 errors" in out
    assert "error: COV-005" in out.split("Waived findings:")[1]
    assert main(["generate", "--date", "2026-06-01"]) == 0
    assert "No file was written" not in capsys.readouterr().err


# trace: PRD-VAL-010
def test_waiver_expires_after_its_expires_date() -> None:
    waiver = Waiver("R-001", "COV-003", "R.", "O.", "2027-01-31", Location("a.sysml", 1, 1))
    assert waiver.expiry == date(2027, 1, 31)
    assert not waiver.expired(date(2027, 1, 31))
    assert waiver.expired(date(2027, 2, 1))
