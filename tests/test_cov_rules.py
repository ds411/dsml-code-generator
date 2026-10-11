"""Tests of the coverage rules COV-001 to COV-007 (story #62).

Each rule has one model that it accepts and one model that it rejects
(PRD-VAL-008). The models are in `tests/models/rules/<rule>/`.
"""

from pathlib import Path

import pytest
from conftest import RULE_MODELS, RunRule

from dsml.config import Configuration
from dsml.ir.model import Finding, Location, Severity
from dsml.validate.rules import cov, registry

RULES = [check.rule.id for check in cov.RULES]

# COV-006 finds the test files relative to the folder of the configuration file.
COV_006_CONFIGURATION = Configuration(path=RULE_MODELS / "COV-006" / "dsml.toml")


def _configuration(rule: str) -> Configuration | None:
    return COV_006_CONFIGURATION if rule == "COV-006" else None


# trace: PRD-VAL-015
def test_registry_contains_the_cov_rules_with_their_default_severities() -> None:
    expected: dict[str, Severity] = {
        "COV-001": "warning",
        "COV-002": "warning",
        "COV-003": "warning",
        "COV-004": "warning",
        "COV-005": "error",
        "COV-006": "warning",
        "COV-007": "info",
    }
    rules = registry()
    assert {rule: rules[rule].rule.severity for rule in expected} == expected
    assert sorted(expected) == RULES


# trace: PRD-VAL-008
@pytest.mark.parametrize("rule", RULES)
def test_rule_accepts_its_accept_model(run_rule: RunRule, rule: str) -> None:
    assert run_rule(rule, "accept.sysml", _configuration(rule)) == ()


# trace: PRD-VAL-008, PRD-VAL-015, PRD-TRACE-001
@pytest.mark.parametrize(
    ("rule", "severity", "line", "column", "element", "message"),
    [
        ("COV-001", "warning", 23, 5, "N-002", "No requirement frames the need N-002."),
        (
            "COV-002",
            "warning",
            24,
            5,
            "R-002",
            "The requirement R-002 frames no need and is not derived from a different requirement.",
        ),
        (
            "COV-003",
            "warning",
            24,
            5,
            "R-002",
            'The requirement R-002 has the status "implemented" but no satisfying element.',
        ),
        (
            "COV-004",
            "warning",
            23,
            5,
            "R-002",
            'The requirement R-002 has the status "approved" but no verification.',
        ),
        (
            "COV-005",
            "error",
            23,
            5,
            "R-002",
            'The requirement R-002 has the status "verified" but no verification.',
        ),
        (
            "COV-006",
            "warning",
            26,
            9,
            "V-001",
            'The verification V-001 refers to the test file "features/missing_check.py". '
            "This file does not exist.",
        ),
        (
            "COV-007",
            "info",
            8,
            5,
            "CovReject::Auditor",
            "The stakeholder CovReject::Auditor has no need.",
        ),
    ],
)
def test_rule_rejects_its_reject_model(
    run_rule: RunRule,
    rule: str,
    severity: Severity,
    line: int,
    column: int,
    element: str,
    message: str,
) -> None:
    file = f"tests/models/rules/{rule}/reject.sysml"
    assert run_rule(rule, "reject.sysml", _configuration(rule)) == (
        Finding(rule, severity, message, Location(file, line, column), element),
    )


# trace: PRD-VAL-015
def test_cov_004_and_cov_005_both_report_a_verified_requirement_with_no_verification(
    run_rule: RunRule,
) -> None:
    model = RULE_MODELS / "COV-005" / "reject.sysml"
    assert [item.element for item in run_rule("COV-004", model)] == ["R-002"]


# trace: PRD-VAL-015, PRD-DSML-048
def test_cov_006_finds_the_test_files_relative_to_the_configuration_file(
    run_rule: RunRule, tmp_path: Path
) -> None:
    model = RULE_MODELS / "COV-006" / "accept.sysml"
    findings = run_rule("COV-006", model, Configuration(path=tmp_path / "dsml.toml"))
    assert [item.message for item in findings] == [
        'The verification V-001 refers to the test file "features/order_check.py". '
        "This file does not exist."
    ]
