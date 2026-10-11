"""Shared fixtures of the tests.

The fixture `run_rule` is the test helper of the validation rules (story
#57). It runs one rule on one small model and gives its findings. Each rule
has one model that it accepts and one model that it rejects (PRD-VAL-008).
Put the models in `tests/models/rules/<rule>/`, for example
`tests/models/rules/COV-003/accept.sysml`:

    def test_cov_003_rejects_its_reject_model(run_rule: RunRule) -> None:
        assert run_rule("COV-003", "reject.sysml") == (...)
"""

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pytest

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.config import Configuration
from dsml.ir.model import Finding
from dsml.library import library_document
from dsml.validate.engine import Validator
from dsml.validate.rules import registry

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RULE_MODELS = PROJECT_ROOT / "tests" / "models" / "rules"


class RunRule(Protocol):
    """Run one rule on one model and give its findings, sorted (PRD-VAL-007).

    `model` is a file name in `tests/models/rules/<rule>/`, or a path. The
    configuration is the default configuration if there is none. The helper
    turns on the optional rule set of the rule, for example TXT.
    """

    def __call__(
        self, rule: str, model: str | Path, configuration: Configuration | None = None
    ) -> tuple[Finding, ...]: ...


@pytest.fixture(scope="session")
def rule_engine() -> Iterator[Engine]:
    """One OpenSysML service for all rule tests."""
    with Engine() as engine:
        yield engine


# trace: PRD-VAL-008
@pytest.fixture
def run_rule(rule_engine: Engine) -> RunRule:
    """Give the test helper that runs one rule on one model."""

    def run(
        rule: str, model: str | Path, configuration: Configuration | None = None
    ) -> tuple[Finding, ...]:
        path = RULE_MODELS / rule / model if isinstance(model, str) else model
        name = path.resolve().relative_to(PROJECT_ROOT).as_posix()
        parsed = rule_engine.parse_texts(
            [library_document(), (name, path.read_text(encoding="utf-8"))]
        )
        ir = build_ir(parsed, [name])
        check = registry()[rule]
        settings = Configuration() if configuration is None else configuration
        if check.rule.optional:
            optional = tuple(sorted({*settings.rules.optional, check.rule.category}))
            rules = dataclasses.replace(settings.rules, optional=optional)
            settings = dataclasses.replace(settings, rules=rules)
        return Validator(settings, {rule: check}).run(ir)

    return run
