"""Tests of the rules STR-001 to STR-004 and STR-016 (story #59).

Each rule has one model that it accepts and one model that it rejects
(PRD-VAL-008). The models are in `tests/models/rules/<rule>/`.
"""

from pathlib import Path

import pytest
from conftest import PROJECT_ROOT, RULE_MODELS, RunRule

from dsml.config import Configuration, IdPatterns
from dsml.ir.model import Finding, Location
from dsml.validate.rules import registry
from dsml.validate.rules.str_core import RULES, is_aws_attribute

EXAMPLE_MODEL = PROJECT_ROOT / "docs" / "model" / "examples" / "order-service.sysml"
RULE_IDS = sorted(check.rule.id for check in RULES)


def _at(rule: str, model: str, line: int, column: int) -> Location:
    return Location(f"tests/models/rules/{rule}/{model}", line, column)


def _error(rule: str, message: str, location: Location, element: str) -> Finding:
    return Finding(rule, "error", message, location, element)


# trace: PRD-VAL-015
def test_registry_contains_the_rules_with_their_default_severities() -> None:
    rules = registry()
    assert RULE_IDS == ["STR-001", "STR-002", "STR-003", "STR-004", "STR-016"]
    for rule_id in RULE_IDS:
        assert rules[rule_id].rule.severity == "error"


# trace: PRD-VAL-008
@pytest.mark.parametrize("rule", RULE_IDS)
def test_rule_accepts_its_accept_model(run_rule: RunRule, rule: str) -> None:
    assert run_rule(rule, "accept.sysml") == ()


# trace: PRD-VAL-008
@pytest.mark.parametrize("rule", RULE_IDS)
def test_example_model_gives_no_finding(run_rule: RunRule, rule: str) -> None:
    assert run_rule(rule, EXAMPLE_MODEL) == ()


# trace: PRD-VAL-008, PRD-DSML-056
def test_str_001_rejects_a_model_with_no_dsml_version(run_rule: RunRule) -> None:
    assert run_rule("STR-001", "reject.sysml") == (
        _error(
            "STR-001",
            "The model has no @DsmlVersion on a root package.",
            _at("STR-001", "reject.sysml", 3, 1),
            "Str001Reject",
        ),
    )


# trace: PRD-VAL-008, PRD-DSML-056, PRD-DSML-057
def test_str_001_rejects_a_dsml_version_that_the_toolchain_does_not_support(
    run_rule: RunRule,
) -> None:
    assert run_rule("STR-001", "reject-version.sysml") == (
        _error(
            "STR-001",
            'The package "Str001RejectVersion" gives the DSML version 2.0. '
            "The toolchain supports the version 1.0.",
            _at("STR-001", "reject-version.sysml", 5, 5),
            "Str001RejectVersion",
        ),
    )


# trace: PRD-VAL-008, PRD-DSML-013, PRD-DSML-015, PRD-DSML-045
def test_str_002_rejects_its_reject_model(run_rule: RunRule) -> None:
    need = _at("STR-002", "reject.sysml", 10, 5)
    requirement = _at("STR-002", "reject.sysml", 18, 5)
    verification = _at("STR-002", "reject.sysml", 25, 5)
    name = "Str002Reject::trackOrders"
    assert run_rule("STR-002", "reject.sysml") == (
        _error("STR-002", f'The need "{name}" has no ID (short name).', need, name),
        _error(
            "STR-002", f'The need "{name}" has no value for the attribute "priority".', need, name
        ),
        _error(
            "STR-002",
            'The requirement "R-001" has no value for the attribute "kind".',
            requirement,
            "R-001",
        ),
        _error(
            "STR-002",
            'The requirement "R-001" has no value for the text (doc comment).',
            requirement,
            "R-001",
        ),
        _error(
            "STR-002",
            'The verification "V-001" has no value for the attribute "method".',
            verification,
            "V-001",
        ),
    )


# trace: PRD-VAL-008, PRD-DSML-050
def test_str_003_rejects_its_reject_model(run_rule: RunRule) -> None:
    assert run_rule("STR-003", "reject.sysml") == (
        _error(
            "STR-003",
            'The need short name "N-01" does not agree with the pattern "N-[0-9]{3,}" (ids.need).',
            _at("STR-003", "reject.sysml", 10, 5),
            "N-01",
        ),
        _error(
            "STR-003",
            'The requirement short name "N-002" does not agree with the pattern '
            '"R-[0-9]{3,}" (ids.requirement).',
            _at("STR-003", "reject.sysml", 15, 5),
            "N-002",
        ),
        _error(
            "STR-003",
            'The verification short name "v-001" does not agree with the pattern '
            '"V-[0-9]{3,}" (ids.verification).',
            _at("STR-003", "reject.sysml", 19, 5),
            "v-001",
        ),
    )


# trace: PRD-DSML-051
def test_str_003_uses_the_id_patterns_of_the_configuration(run_rule: RunRule) -> None:
    patterns = IdPatterns(need="N-[0-9]{2}", requirement="[NR]-[0-9]{3}", verification="v-[0-9]+")
    configuration = Configuration(path=Path("dsml.toml"), ids=patterns)
    assert run_rule("STR-003", "reject.sysml", configuration) == ()
    findings = run_rule("STR-003", "accept.sysml", configuration)
    assert [item.element for item in findings] == ["N-001", "R-1000", "V-012"]


# trace: PRD-VAL-008, PRD-DSML-052
def test_str_004_rejects_its_reject_model(run_rule: RunRule) -> None:
    sales = "Str004Reject::Sales::ShopOwner"
    support = "Str004Reject::Support::Clerk"
    assert run_rule("STR-004", "reject.sysml") == (
        _error(
            "STR-004",
            f'The short name "S-001" of "{sales}" is also on "{support}".',
            _at("STR-004", "reject.sysml", 8, 9),
            "S-001",
        ),
        _error(
            "STR-004",
            f'The short name "S-001" of "{support}" is also on "{sales}".',
            _at("STR-004", "reject.sysml", 11, 9),
            "S-001",
        ),
    )


# trace: PRD-VAL-008, PRD-DSML-036
def test_str_016_rejects_its_reject_model(run_rule: RunRule) -> None:
    assert run_rule("STR-016", "reject.sysml") == (
        _error(
            "STR-016",
            'The logical element "Str016Reject::orderDb" has the AWS attribute "instanceClass".',
            _at("STR-016", "reject.sysml", 10, 9),
            "Str016Reject::orderDb",
        ),
        _error(
            "STR-016",
            'The logical element "Str016Reject::apiService" has the AWS attribute "awsLogGroup".',
            _at("STR-016", "reject.sysml", 13, 9),
            "Str016Reject::apiService",
        ),
    )


# trace: PRD-DSML-036
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("instanceClass", True),
        ("natGatewayCount", True),
        ("region", True),
        ("awsLogGroup", True),
        ("AwsTag", True),
        ("purpose", False),
        ("engine", False),
    ],
)
def test_is_aws_attribute(name: str, expected: bool) -> None:
    assert is_aws_attribute(name) is expected


def test_each_rule_has_its_test_models() -> None:
    for rule in RULE_IDS:
        assert (RULE_MODELS / rule / "accept.sysml").is_file()
        assert (RULE_MODELS / rule / "reject.sysml").is_file()
