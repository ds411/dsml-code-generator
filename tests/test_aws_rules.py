"""Tests of the AWS rules (story #64).

Each AWS rule has one model that it accepts and one model that it rejects
(PRD-VAL-008). The models are in `tests/models/rules/<rule>/`.
"""

import pytest
from conftest import PROJECT_ROOT, RunRule

from dsml.config import Configuration
from dsml.ir.model import Finding, Location
from dsml.validate.rules import aws

RULES = sorted(check.rule.id for check in aws.RULES)
REGIONS = Configuration(regions=("eu-central-1", "eu-west-1"))
EXAMPLE_MODEL = PROJECT_ROOT / "docs" / "model" / "examples" / "order-service.sysml"


def _at(rule: str, line: int, column: int) -> Location:
    return Location(f"tests/models/rules/{rule}/reject.sysml", line, column)


# trace: PRD-VAL-015
def test_the_registry_contains_the_aws_rules() -> None:
    assert RULES == ["AWS-001", "AWS-002", "AWS-003", "AWS-004", "AWS-005"]
    severities = {check.rule.id: check.rule.severity for check in aws.RULES}
    assert severities == {
        "AWS-001": "error",
        "AWS-002": "error",
        "AWS-003": "error",
        "AWS-004": "warning",
        "AWS-005": "warning",
    }


# trace: PRD-VAL-008
@pytest.mark.parametrize("rule", RULES)
def test_rule_accepts_its_accept_model(run_rule: RunRule, rule: str) -> None:
    assert run_rule(rule, "accept.sysml", REGIONS) == ()


# trace: PRD-VAL-008, PRD-VAL-015
@pytest.mark.parametrize("configuration", [Configuration(), REGIONS], ids=["default", "regions"])
@pytest.mark.parametrize("rule", RULES)
def test_example_model_gives_no_aws_finding(
    run_rule: RunRule, rule: str, configuration: Configuration
) -> None:
    assert run_rule(rule, EXAMPLE_MODEL, configuration) == ()


# trace: PRD-VAL-008, PRD-DSML-043
def test_aws_001_rejects_its_reject_model(run_rule: RunRule) -> None:
    rule = "AWS-001"
    assert run_rule(rule, "reject.sysml") == (
        Finding(
            rule,
            "error",
            "The environment dev uses the account 111111111111 of the tooling account tooling.",
            _at(rule, 8, 29),
            "Aws001Reject::dev",
        ),
        Finding(
            rule,
            "error",
            'The account ID "12345" of the environment staging does not have 12 digits.',
            _at(rule, 9, 33),
            "Aws001Reject::staging",
        ),
        Finding(
            rule,
            "error",
            "The environment prod uses the account 444444444444. "
            "The environment qa also uses this account.",
            _at(rule, 10, 30),
            "Aws001Reject::prod",
        ),
        Finding(
            rule,
            "error",
            "The environment qa uses the account 444444444444. "
            "The environment prod also uses this account.",
            _at(rule, 11, 28),
            "Aws001Reject::qa",
        ),
    )


# trace: PRD-VAL-008, PRD-CORE-013
def test_aws_002_rejects_its_reject_model(run_rule: RunRule) -> None:
    rule = "AWS-002"
    assert run_rule(rule, "reject.sysml", REGIONS) == (
        Finding(
            rule,
            "error",
            'The tooling account tooling uses the Region "us-east-1". '
            "This Region is not in aws.regions.",
            _at(rule, 7, 68),
            "Aws002Reject::tooling",
        ),
        Finding(
            rule,
            "error",
            'The environment prod uses the Region "us-east-1". This Region is not in aws.regions.',
            _at(rule, 9, 62),
            "Aws002Reject::prod",
        ),
    )


# trace: PRD-CORE-013
def test_aws_002_gives_no_finding_if_aws_regions_is_missing(run_rule: RunRule) -> None:
    assert run_rule("AWS-002", "reject.sysml") == ()


# trace: PRD-VAL-008, PRD-IAC-012
def test_aws_003_rejects_its_reject_model(run_rule: RunRule) -> None:
    rule = "AWS-003"
    assert run_rule(rule, "reject.sysml") == (
        Finding(
            rule,
            "error",
            "The service small has cpu = 256 and memory = 4096. Fargate does not accept this pair.",
            _at(rule, 7, 33),
            "Aws003Reject::small",
        ),
        Finding(
            rule,
            "error",
            "The service large has cpu = 512 and memory = 512 in the environment prod. "
            "Fargate does not accept this pair.",
            _at(rule, 14, 45),
            "Aws003Reject::large",
        ),
    )


# trace: PRD-IAC-012
@pytest.mark.parametrize(
    ("cpu", "memory", "valid"),
    [
        (256, 512, True),
        (256, 2048, True),
        (256, 3072, False),
        (1024, 8192, True),
        (4096, 30720, True),
        (8192, 20480, True),
        (8192, 18432, False),
        (16384, 122880, True),
        (128, 512, False),
    ],
)
def test_the_table_of_fargate_pairs(cpu: int, memory: int, valid: bool) -> None:
    assert (memory in aws.FARGATE_PAIRS.get(cpu, ())) is valid


# trace: PRD-VAL-008, PRD-IAC-017
def test_aws_004_rejects_its_reject_model(run_rule: RunRule) -> None:
    rule = "AWS-004"
    assert run_rule(rule, "reject.sysml") == (
        Finding(
            rule,
            "warning",
            "The database orderDb has multiAz = false in the environment prod.",
            _at(rule, 12, 49),
            "Aws004Reject::orderDb",
        ),
    )


# trace: PRD-VAL-008, PRD-IAC-013
def test_aws_005_rejects_its_reject_model(run_rule: RunRule) -> None:
    rule = "AWS-005"
    assert run_rule(rule, "reject.sysml") == (
        Finding(
            rule,
            "warning",
            "The service api has minCount = 1 in the environment prod.",
            _at(rule, 6, 31),
            "Aws005Reject::api",
        ),
    )
