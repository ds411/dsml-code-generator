"""Tests of the XLY rules (stories #63 and #161).

Each rule has one model that it accepts and one model that it rejects
(PRD-VAL-008). The models are in `tests/models/rules/<rule>/`. Story #161
added models with a static site and with views.
"""

import pytest
from conftest import PROJECT_ROOT, RunRule

from dsml.ir.model import Finding, Location
from dsml.validate.rules import registry, xly

EXAMPLE_MODEL = PROJECT_ROOT / "docs" / "model" / "examples" / "order-service.sysml"
PORTAL_MODEL = PROJECT_ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
XLY_RULES = sorted(check.rule.id for check in xly.RULES)


def _finding(
    rule: str, line: int, element: str, message: str | None = None, model: str = "reject.sysml"
) -> Finding:
    check = registry()[rule]
    return Finding(
        rule=rule,
        severity="error",
        message=check.rule.message if message is None else message,
        location=Location(f"tests/models/rules/{rule}/{model}", line, 5),
        element=f"XlyReject::{element}",
    )


# trace: PRD-VAL-015
def test_registry_contains_the_xly_rules_with_their_severities() -> None:
    rules = registry()
    assert [f"XLY-00{number}" for number in range(1, 8)] == XLY_RULES
    for rule_id in XLY_RULES:
        assert rules[rule_id].rule.severity == "error"


# trace: PRD-VAL-008
@pytest.mark.parametrize("rule", XLY_RULES)
def test_rule_accepts_its_accept_model(run_rule: RunRule, rule: str) -> None:
    assert run_rule(rule, "accept.sysml") == ()


# trace: PRD-VAL-008, PRD-VAL-015
@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        ("XLY-001", (_finding("XLY-001", 10, "orderApi"),)),
        (
            "XLY-002",
            (
                _finding(
                    "XLY-002",
                    23,
                    "orderApi",
                    "The fastapi application orderApi is allocated to the RelationalDatabase "
                    "orderDb. Allocate it to a #ContainerService.",
                ),
            ),
        ),
        (
            "XLY-003",
            (
                _finding(
                    "XLY-003",
                    19,
                    "orderDb",
                    "The RelationalDatabase orderDb has no AWS realizations of the kind "
                    "#AwsRdsPostgres. It must have one.",
                ),
                _finding(
                    "XLY-003",
                    20,
                    "users",
                    "The UserDirectory users has 2 AWS realizations of the kind #AwsCognito. "
                    "It must have one.",
                ),
            ),
        ),
        (
            "XLY-004",
            (
                _finding(
                    "XLY-004",
                    21,
                    "orderWeb",
                    "The react application orderWeb uses the database orderDb.",
                ),
            ),
        ),
        ("XLY-005", (_finding("XLY-005", 18, "orderWeb"),)),
        ("XLY-006", (_finding("XLY-006", 10, "orderApi"),)),
        ("XLY-007", (_finding("XLY-007", 10, "orderApi"),)),
    ],
)
def test_rule_rejects_its_reject_model(
    run_rule: RunRule, rule: str, expected: tuple[Finding, ...]
) -> None:
    assert run_rule(rule, "reject.sysml") == expected


# trace: PRD-VAL-008, PRD-DSML-031, PRD-DSML-037, PRD-DSML-039
@pytest.mark.parametrize(
    ("rule", "model"),
    [
        ("XLY-002", "accept-static-site.sysml"),
        ("XLY-003", "accept-static-site.sysml"),
        ("XLY-005", "accept-static-site.sysml"),
        ("XLY-007", "accept-views.sysml"),
        ("XLY-007", "accept-public-views.sysml"),
    ],
)
def test_rule_accepts_its_static_site_model(run_rule: RunRule, rule: str, model: str) -> None:
    assert run_rule(rule, model) == ()


# trace: PRD-VAL-008, PRD-DSML-031, PRD-DSML-037, PRD-DSML-039, PRD-DSML-040
@pytest.mark.parametrize(
    ("rule", "model", "expected"),
    [
        (
            "XLY-002",
            "reject-static-site.sysml",
            _finding(
                "XLY-002",
                36,
                "orderPortal",
                "The react application orderPortal is allocated to the ContainerService "
                "apiService. Allocate it to a #StaticSite.",
                "reject-static-site.sysml",
            ),
        ),
        (
            "XLY-003",
            "reject-static-site.sysml",
            _finding(
                "XLY-003",
                28,
                "portalSite",
                "The StaticSite portalSite has no AWS realizations of the kind "
                "#AwsStaticSite. It must have one.",
                "reject-static-site.sysml",
            ),
        ),
        (
            "XLY-004",
            "reject-static-site.sysml",
            _finding(
                "XLY-004",
                39,
                "orderPortal",
                "The react application orderPortal uses the database orderDb.",
                "reject-static-site.sysml",
            ),
        ),
        (
            "XLY-005",
            "reject-static-site.sysml",
            _finding("XLY-005", 19, "orderPortal", model="reject-static-site.sysml"),
        ),
        (
            "XLY-007",
            "reject-views.sysml",
            _finding("XLY-007", 18, "orderPortal", model="reject-views.sysml"),
        ),
    ],
)
def test_rule_rejects_its_static_site_model(
    run_rule: RunRule, rule: str, model: str, expected: Finding
) -> None:
    assert run_rule(rule, model) == (expected,)


# trace: PRD-DSML-039
def test_xly_001_rejects_an_application_with_two_allocations(run_rule: RunRule) -> None:
    location = Location("tests/models/rules/XLY-001/reject-two-allocations.sysml", 10, 5)
    message = (
        "The application orderApi is allocated to more than one logical element. "
        "Allocate it to one logical element only."
    )
    assert run_rule("XLY-001", "reject-two-allocations.sysml") == (
        Finding("XLY-001", "error", message, location, "XlyReject::orderApi"),
    )


# trace: PRD-VAL-015
@pytest.mark.parametrize("rule", XLY_RULES)
def test_example_model_gives_no_xly_finding(run_rule: RunRule, rule: str) -> None:
    assert run_rule(rule, EXAMPLE_MODEL) == ()


# trace: PRD-VAL-015, PRD-DSML-039
@pytest.mark.parametrize("rule", XLY_RULES)
def test_order_portal_gives_no_xly_finding(run_rule: RunRule, rule: str) -> None:
    assert run_rule(rule, PORTAL_MODEL) == ()
