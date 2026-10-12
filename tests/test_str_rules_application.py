"""Tests of the STR rules of the applications and the environments (stories #60 and #161).

Each rule has one model that it accepts and one model that it rejects
(PRD-VAL-008). The models are in `tests/models/rules/<rule>/`.
"""

from pathlib import Path

import pytest
from conftest import RULE_MODELS, RunRule

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.config import Configuration
from dsml.ir.model import Finding, Location
from dsml.ir.operations import endpoints
from dsml.library import library_document
from dsml.validate.engine import Validator
from dsml.validate.rules import registry, str_application, str_environment

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_MODEL = "docs/model/examples/order-service.sysml"
RULES = {check.rule.id: check for check in (*str_application.RULES, *str_environment.RULES)}


def _at(rule: str, line: int, column: int) -> Location:
    return Location(f"tests/models/rules/{rule}/reject.sysml", line, column)


def _error(rule: str, message: str, line: int, column: int, element: str) -> Finding:
    return Finding(rule, "error", message, _at(rule, line, column), element)


# trace: PRD-VAL-015
def test_registry_contains_str_005_to_str_012_with_their_default_severities() -> None:
    rules = registry()
    assert sorted(RULES) == [f"STR-{number:03d}" for number in range(5, 13)]
    for rule_id, check in RULES.items():
        assert rules[rule_id] is check
        assert check.rule.severity == "error"


# trace: PRD-VAL-008
@pytest.mark.parametrize("rule", sorted(RULES))
def test_rule_accepts_its_accept_model(run_rule: RunRule, rule: str) -> None:
    assert run_rule(rule, "accept.sysml") == ()


# trace: PRD-VAL-008, PRD-VAL-015
@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        (
            "STR-005",
            (_error("STR-005", "The application web has no target.", 8, 5, "Str005Reject::web"),),
        ),
        (
            "STR-006",
            (
                _error(
                    "STR-006", "The entity Order has no #Key field.", 7, 5, "Str006Reject::Order"
                ),
                _error(
                    "STR-006",
                    "The entity Item has 2 #Key fields: code, id. It must have one.",
                    10,
                    5,
                    "Str006Reject::Item",
                ),
            ),
        ),
        (
            "STR-007",
            (
                _error(
                    "STR-007",
                    "The field count has the type ScalarValues::Natural. "
                    "This is not a supported field type.",
                    9,
                    9,
                    "Str007Reject::Item::count",
                ),
                _error(
                    "STR-007",
                    "The field other has no type.",
                    10,
                    9,
                    "Str007Reject::Item::other",
                ),
            ),
        ),
        (
            "STR-008",
            (
                _error(
                    "STR-008",
                    "The operation Ping has no method and no path.",
                    7,
                    5,
                    "Str008Reject::Ping",
                ),
                _error("STR-008", "The operation Pong has no path.", 10, 5, "Str008Reject::Pong"),
            ),
        ),
        (
            "STR-009",
            (
                _error(
                    "STR-009",
                    "In the application api, the operation getOrder has the same method "
                    "and path as read of orders: GET /orders/{orderId}.",
                    21,
                    9,
                    "Str009Reject::api::getOrder",
                ),
            ),
        ),
        (
            "STR-010",
            (
                _error(
                    "STR-010",
                    "The exposed element orders has no allowedRoles and is not public.",
                    16,
                    9,
                    "Str010Reject::api::orders",
                ),
                _error(
                    "STR-010",
                    "The exposed element ping has no allowedRoles and is not public.",
                    19,
                    9,
                    "Str010Reject::api::ping",
                ),
            ),
        ),
        (
            "STR-011",
            (
                _error("STR-011", "The model has no environment staging.", 4, 1, "Str011Reject"),
                _error(
                    "STR-011",
                    "The environment prod has no value for region, domain.",
                    9,
                    5,
                    "Str011Reject::prod",
                ),
            ),
        ),
        (
            "STR-012",
            (
                _error(
                    "STR-012",
                    "The override dbProd changes the attribute engine. "
                    "An environment cannot change this attribute.",
                    15,
                    13,
                    "Str012Reject::prod::dbProd",
                ),
            ),
        ),
    ],
)
def test_rule_rejects_its_reject_model(
    run_rule: RunRule, rule: str, expected: tuple[Finding, ...]
) -> None:
    assert run_rule(rule, "reject.sysml") == expected


# trace: PRD-VAL-008, PRD-DSML-031, PRD-DSML-033
def test_str_010_accepts_views_with_roles_or_public(run_rule: RunRule) -> None:
    assert run_rule("STR-010", "accept-views.sysml") == ()


# trace: PRD-VAL-008, PRD-DSML-031, PRD-DSML-033
def test_str_010_rejects_a_view_with_no_roles_that_is_not_public(run_rule: RunRule) -> None:
    location = Location("tests/models/rules/STR-010/reject-views.sysml", 11, 9)
    message = "The view orderList has no allowedRoles and is not public."
    assert run_rule("STR-010", "reject-views.sysml") == (
        Finding("STR-010", "error", message, location, "Str010Reject::portal::orderList"),
    )


# trace: PRD-VAL-015
def test_example_model_gives_no_finding_of_these_rules(rule_engine: Engine) -> None:
    text = (ROOT / EXAMPLE_MODEL).read_text(encoding="utf-8")
    ir = build_ir(
        rule_engine.parse_texts([library_document(), (EXAMPLE_MODEL, text)]), [EXAMPLE_MODEL]
    )
    assert Validator(Configuration(), RULES).run(ir) == ()


# trace: PRD-DSML-029, PRD-APP-110
def test_endpoints_give_the_default_crud_paths_and_the_custom_paths(rule_engine: Engine) -> None:
    text = (ROOT / EXAMPLE_MODEL).read_text(encoding="utf-8")
    ir = build_ir(
        rule_engine.parse_texts([library_document(), (EXAMPLE_MODEL, text)]), [EXAMPLE_MODEL]
    )
    found = [
        (item.operation, item.crud, item.method, item.path, item.route)
        for item in endpoints(ir, "OrderService::orderApi")
    ]
    assert found == [
        ("create", True, "post", "/orders", ("post", "/orders")),
        ("read", True, "get", "/orders/{id}", ("get", "/orders/{}")),
        ("list", True, "get", "/orders", ("get", "/orders")),
        (
            "OrderService::CancelOrder",
            False,
            "post",
            "/orders/{orderId}/cancel",
            ("post", "/orders/{}/cancel"),
        ),
    ]


# trace: PRD-DSML-041
def test_str_011_needs_no_environment_in_a_model_with_no_solution(run_rule: RunRule) -> None:
    """A model with no application and no infrastructure element needs no environment."""
    assert run_rule("STR-011", RULE_MODELS / "SYN-002" / "accept.sysml") == ()
