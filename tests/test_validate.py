"""Tests of the rule engine, the rule registry and `dsml validate` (story #57)."""

import json
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import RULE_MODELS, RunRule

from dsml.cli import main
from dsml.config import Configuration, ConfigurationError, Rules, RuleSeverity
from dsml.ir.model import Finding, Ir, Location
from dsml.validate.engine import Validator, fails, severities
from dsml.validate.report import json_report, text_report
from dsml.validate.rule import Hit, Rule, RuleCheck, implements
from dsml.validate.rules import load_rules, registry

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
SYN_002_REJECT = RULE_MODELS / "SYN-002" / "reject.sysml"


def _fixed(rule: Rule, *hits: Hit) -> RuleCheck:
    """Make a test rule that gives fixed hits."""

    @implements(rule)
    def check(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
        yield from hits

    return check


INFO = _fixed(Rule("INF-001", "info", "An info finding.", "Do A."), Hit())
WARNING = _fixed(Rule("WRN-001", "warning", "A warning finding.", "Do B."), Hit())
ERROR = _fixed(Rule("ERR-001", "error", "An error finding.", "Do C."), Hit())
TEXT = _fixed(Rule("TXT-001", "warning", "A text finding.", "Do D."), Hit())
TEST_RULES = {check.rule.id: check for check in (ERROR, INFO, TEXT, WARNING)}


def _configuration(*overrides: tuple[str, RuleSeverity], optional: str = "") -> Configuration:
    sets = (optional,) if optional else ()
    return Configuration(
        path=Path("dsml.toml"), rules=Rules(optional=sets, severity=tuple(sorted(overrides)))
    )


def _write_project(root: Path, model: Path, rules: str = "") -> None:
    """Write a configuration file and a copy of the model in a project folder."""
    (root / "model").mkdir()
    shutil.copyfile(model, root / "model" / model.name)
    (root / "dsml.toml").write_text(
        f'schema = 1\n\n[model]\npaths = ["model"]\n{rules}', encoding="utf-8"
    )


# trace: PRD-VAL-001, PRD-VAL-002
def test_registry_contains_the_syn_rules() -> None:
    rules = registry()
    assert list(rules) == sorted(rules)
    assert {"SYN-001", "SYN-002"} <= set(rules)
    for rule_id, check in rules.items():
        assert check.rule.id == rule_id
        assert check.rule.message
        assert check.rule.fix_hint
        assert check.rule.severity in ("error", "warning", "info")


# trace: PRD-VAL-002
@pytest.mark.parametrize("rule_id", ["COV-3", "cov-003", "COVER-003", "COV003"])
def test_rule_id_must_have_the_form_of_prd_val_002(rule_id: str) -> None:
    with pytest.raises(ValueError, match="does not have the form"):
        Rule(rule_id, "error", "Message.", "Fix hint.")


def _write_package(
    root: Path, name: str, modules: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Write a test package of rule modules and put its folder on the import path."""
    monkeypatch.setattr(sys, "path", [str(root), *sys.path])
    for module in [key for key in sys.modules if key == name or key.startswith(f"{name}.")]:
        monkeypatch.delitem(sys.modules, module)
    package = root / name
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    for module, text in modules.items():
        (package / f"{module}.py").write_text(text, encoding="utf-8")


RULE_MODULE = """
from dsml.validate.rule import Rule, implements

@implements(Rule("{id}", "error", "Message.", "Fix hint."))
def check(ir, configuration):
    return ()

RULES = (check,)
"""


# trace: PRD-VAL-001
def test_registry_finds_each_module_of_the_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_package(
        tmp_path,
        "rules_found",
        {
            "cov": RULE_MODULE.format(id="COV-001"),
            "str_names": RULE_MODULE.format(id="STR-003"),
            "str_model": RULE_MODULE.format(id="STR-005"),
        },
        monkeypatch,
    )
    assert list(load_rules("rules_found")) == ["COV-001", "STR-003", "STR-005"]


@pytest.mark.parametrize(
    ("modules", "message"),
    [
        ({"cov": RULE_MODULE.format(id="STR-001")}, "Its module name must start with str"),
        (
            {"str_a": RULE_MODULE.format(id="STR-001"), "str_b": RULE_MODULE.format(id="STR-001")},
            "Two rules have the ID STR-001",
        ),
    ],
)
def test_registry_stops_a_wrong_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, modules: dict[str, str], message: str
) -> None:
    name = f"rules_wrong_{len(modules)}"
    _write_package(tmp_path, name, modules, monkeypatch)
    with pytest.raises(ValueError, match=message):
        load_rules(name)


# trace: PRD-VAL-004
def test_default_severities_apply() -> None:
    assert severities(_configuration(), TEST_RULES) == {
        "ERR-001": "error",
        "INF-001": "info",
        "WRN-001": "warning",
    }


# trace: PRD-VAL-004
@pytest.mark.parametrize(
    ("rule", "level", "result"),
    [
        ("INF-001", "warning", "warning"),
        ("INF-001", "error", "error"),
        ("WRN-001", "error", "error"),
        ("WRN-001", "info", "info"),
        ("ERR-001", "error", "error"),
        ("INF-001", "off", None),
        ("WRN-001", "off", None),
    ],
)
def test_configuration_changes_the_severity(
    rule: str, level: RuleSeverity, result: str | None
) -> None:
    found = severities(_configuration((rule, level)), TEST_RULES)
    assert found.get(rule) == result


# trace: PRD-VAL-004
@pytest.mark.parametrize("level", ["warning", "info", "off"])
def test_configuration_must_not_decrease_the_severity_error(level: RuleSeverity) -> None:
    with pytest.raises(ConfigurationError) as error:
        severities(_configuration(("ERR-001", level)), TEST_RULES)
    assert error.value.errors == [
        f"dsml.toml: rules.severity.ERR-001: The rule ERR-001 has the default severity "
        f'"error". You cannot set it to "{level}" (PRD-VAL-004).'
    ]


def test_configuration_must_not_name_an_unknown_rule() -> None:
    with pytest.raises(ConfigurationError, match="The rule ABC-999 does not exist"):
        severities(_configuration(("ABC-999", "error")), TEST_RULES)


# trace: PRD-VAL-013
def test_optional_rule_set_is_off_by_default() -> None:
    assert "TXT-001" not in severities(_configuration(), TEST_RULES)
    assert severities(_configuration(optional="TXT"), TEST_RULES)["TXT-001"] == "warning"
    assert "TXT-001" not in severities(
        _configuration(("TXT-001", "off"), optional="TXT"), TEST_RULES
    )


# trace: PRD-VAL-004
def test_validator_gives_the_severity_of_the_configuration() -> None:
    validator = Validator(_configuration(("WRN-001", "error"), ("INF-001", "off")), TEST_RULES)
    assert validator.run(Ir()) == (
        Finding("ERR-001", "error", "An error finding."),
        Finding("WRN-001", "error", "A warning finding."),
    )


# trace: PRD-VAL-007
def test_findings_are_sorted_by_file_line_column_and_rule() -> None:
    def at(file: str, line: int, column: int) -> Hit:
        return Hit("Text.", Location(file, line, column))

    first = _fixed(
        Rule("BBB-001", "error", "M.", "F."),
        at("b.sysml", 1, 1),
        at("a.sysml", 9, 1),
        at("a.sysml", 2, 7),
        Hit("No location."),
    )
    second = _fixed(
        Rule("AAA-001", "warning", "M.", "F."), at("a.sysml", 2, 7), at("a.sysml", 2, 3)
    )
    findings = Validator(_configuration(), {"BBB-001": first, "AAA-001": second}).run(Ir())
    places = [
        (None, finding.rule)
        if finding.location is None
        else (finding.location.sort_key(), finding.rule)
        for finding in findings
    ]
    assert places == [
        (None, "BBB-001"),
        (("a.sysml", 2, 3), "AAA-001"),
        (("a.sysml", 2, 7), "AAA-001"),
        (("a.sysml", 2, 7), "BBB-001"),
        (("a.sysml", 9, 1), "BBB-001"),
        (("b.sysml", 1, 1), "BBB-001"),
    ]


def test_syn_001_stops_the_other_rules() -> None:
    syn_001 = Finding("SYN-001", "error", "Syntax error.", Location("a.sysml", 1, 1))
    rules = {**TEST_RULES, "SYN-001": registry()["SYN-001"]}
    findings = Validator(_configuration(), rules).run(Ir(findings=(syn_001,)))
    assert findings == (syn_001,)


# trace: PRD-VAL-003, PRD-VAL-005
def test_fail_on_selects_the_severity() -> None:
    warning = (Finding("WRN-001", "warning", "W."),)
    info = (Finding("INF-001", "info", "I."),)
    error = (Finding("ERR-001", "error", "E."),)
    assert not fails(warning)
    assert fails(warning, "warning")
    assert not fails(info, "warning")
    assert fails(error)
    assert fails(error, "warning")


# trace: PRD-CORE-007, PRD-VAL-006
def test_text_and_json_reports() -> None:
    findings = (
        Finding("ERR-001", "error", "An error finding.", Location("a.sysml", 3, 5)),
        Finding("WRN-001", "warning", "A warning finding."),
    )
    assert text_report(findings, TEST_RULES) == (
        "a.sysml:3:5: error: ERR-001: An error finding.\n"
        "  fix: Do C.\n"
        "warning: WRN-001: A warning finding.\n"
        "  fix: Do B.\n"
        "Findings: 1 error, 1 warning, 0 info.\n"
    )
    data = json.loads(json_report(findings, TEST_RULES))
    assert data == {
        "findings": [
            {
                "element": None,
                "fixHint": "Do C.",
                "location": {"column": 5, "file": "a.sysml", "line": 3},
                "message": "An error finding.",
                "rule": "ERR-001",
                "severity": "error",
            },
            {
                "element": None,
                "fixHint": "Do B.",
                "location": None,
                "message": "A warning finding.",
                "rule": "WRN-001",
                "severity": "warning",
            },
        ],
        "summary": {"error": 1, "info": 0, "warning": 1},
    }


# trace: PRD-VAL-008
def test_rule_helper_runs_one_rule(run_rule: RunRule) -> None:
    assert run_rule("SYN-002", "accept.sysml") == ()
    findings = run_rule("SYN-002", "reject.sysml")
    assert findings
    assert {(item.rule, item.severity) for item in findings} == {("SYN-002", "warning")}
    assert run_rule("SYN-001", "reject.sysml")[0].rule == "SYN-001"


# trace: PRD-CORE-002, PRD-CORE-006, PRD-VAL-006
def test_validate_writes_the_findings_of_the_example_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path, EXAMPLE_MODEL)
    monkeypatch.chdir(tmp_path)
    assert main(["validate"]) == 0
    assert capsys.readouterr().out == "Findings: 0 errors, 0 warnings, 0 info.\n"
    assert main(["validate", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "findings": [],
        "summary": {"error": 0, "info": 0, "warning": 0},
    }


# trace: PRD-VAL-005
def test_fail_on_warning_gives_exit_code_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path, SYN_002_REJECT)
    monkeypatch.chdir(tmp_path)
    assert main(["validate"]) == 0
    out = capsys.readouterr().out
    assert "model/reject.sysml:6:" in out
    assert "warning: SYN-002: " in out
    assert main(["validate", "--fail-on", "warning", "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["findings"]
    assert {item["rule"] for item in data["findings"]} == {"SYN-002"}


# trace: PRD-CORE-002, PRD-VAL-003, PRD-VAL-004
def test_increased_severity_gives_exit_code_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path, SYN_002_REJECT, '\n[rules.severity]\n"SYN-002" = "error"\n')
    monkeypatch.chdir(tmp_path)
    assert main(["validate"]) == 1
    assert "error: SYN-002: " in capsys.readouterr().out


# trace: PRD-CORE-002, PRD-VAL-004
def test_decreased_severity_error_gives_exit_code_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path, EXAMPLE_MODEL, '\n[rules.severity]\n"SYN-001" = "off"\n')
    monkeypatch.chdir(tmp_path)
    assert main(["validate"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "dsml: error: dsml.toml: rules.severity.SYN-001: The rule SYN-001 has the default "
        'severity "error". You cannot set it to "off" (PRD-VAL-004).\n'
    )


# trace: PRD-CORE-003, PRD-VAL-003
def test_generate_writes_no_file_when_there_is_an_error_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path, SYN_002_REJECT, '\n[rules.severity]\n"SYN-002" = "error"\n')
    monkeypatch.chdir(tmp_path)
    assert main(["generate"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error: SYN-002: " in captured.err
    assert captured.err.endswith("No file was written.\n")
    assert not (tmp_path / ".dsml").exists()


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--format", "sarif"], "The format sarif is not available in this version."),
        (["--baseline", "v1.0.0"], "The option --baseline is not available in this version."),
    ],
)
def test_options_of_later_stories_are_not_available(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", *argv]) == 2
    assert capsys.readouterr().err == f"dsml: error: {message}\n"
