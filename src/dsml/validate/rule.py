# trace: PRD-VAL-001, PRD-VAL-002, PRD-VAL-003, PRD-VAL-011
"""The interface of a validation rule.

A rule is a Python function with its `Rule` metadata. The function reads only
the IR and the configuration (PRD-VAL-001, PRD-CORE-026). It gives one `Hit`
for each problem. The engine converts each hit into a `Finding` with the
rule ID and the severity of the rule after the configuration overrides.

A baseline rule, for example an IDN rule, also reads the IR of the baseline
model. It runs only when there is a baseline (PRD-VAL-011).
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Final

from dsml.config import OPTIONAL_RULE_SETS, Configuration
from dsml.ir.model import Ir, Location, Severity

RULE_ID: Final = re.compile(r"(?P<category>[A-Z]{3})-[0-9]{3}")
"""The form of a rule ID: `<CATEGORY>-<NNN>`, for example `COV-003` (PRD-VAL-002)."""


# trace: PRD-VAL-001, PRD-VAL-002
@dataclass(frozen=True, slots=True)
class Rule:
    """The metadata of one validation rule.

    `message` tells what the rule finds. `fix_hint` tells how to correct the
    model.
    """

    id: str
    severity: Severity
    message: str
    fix_hint: str

    def __post_init__(self) -> None:
        if not RULE_ID.fullmatch(self.id):
            raise ValueError(f'The rule ID "{self.id}" does not have the form "COV-003".')

    @property
    def category(self) -> str:
        """The category of the rule, for example "SYN" for "SYN-001"."""
        return self.id.split("-", 1)[0]

    @property
    def optional(self) -> bool:
        """True if the rule is in an optional rule set, for example TXT (PRD-VAL-013)."""
        return self.category in OPTIONAL_RULE_SETS


# trace: PRD-CORE-007, PRD-VAL-001
@dataclass(frozen=True, slots=True)
class Hit:
    """One problem that a rule finds.

    `message` is `None` if the message of the rule is sufficient. `element` is
    the identity of the element of the problem, if there is one.
    """

    message: str | None = None
    location: Location | None = None
    element: str | None = None


type Check = Callable[[Ir, Configuration], Iterable[Hit]]
"""The function of a rule. It reads only the IR and the configuration."""


# trace: PRD-VAL-001
@dataclass(frozen=True, slots=True)
class RuleCheck:
    """A rule: its metadata and its function."""

    rule: Rule
    check: Check

    def __call__(self, ir: Ir, configuration: Configuration) -> Iterable[Hit]:
        return self.check(ir, configuration)

    def hits(self, ir: Ir, configuration: Configuration, baseline: Ir | None) -> Iterable[Hit]:
        """Give the hits of the rule. This rule does not use the baseline."""
        return self.check(ir, configuration)


type BaselineCheck = Callable[[Ir, Ir, Configuration], Iterable[Hit]]
"""The function of a baseline rule. It reads the IR, the baseline IR and the configuration."""


def _no_hits(ir: Ir, configuration: Configuration) -> Iterable[Hit]:
    return ()


# trace: PRD-VAL-011
@dataclass(frozen=True, slots=True)
class BaselineRuleCheck(RuleCheck):
    """A rule that compares the IR with the IR of a baseline, for example an IDN rule.

    The rule gives no hit when there is no baseline (PRD-VAL-011).
    """

    compare: BaselineCheck

    def hits(self, ir: Ir, configuration: Configuration, baseline: Ir | None) -> Iterable[Hit]:
        """Give the hits of the rule, or no hit if there is no baseline."""
        if baseline is None:
            return ()
        return self.compare(ir, baseline, configuration)


# trace: PRD-VAL-001
def implements(rule: Rule) -> Callable[[Check], RuleCheck]:
    """Join a rule function to its metadata.

    Use it as a decorator:

        @implements(COV_003)
        def cov_003(ir: Ir, configuration: Configuration) -> Iterator[Hit]: ...
    """

    def join(check: Check) -> RuleCheck:
        return RuleCheck(rule, check)

    return join


# trace: PRD-VAL-001, PRD-VAL-011
def compares(rule: Rule) -> Callable[[BaselineCheck], BaselineRuleCheck]:
    """Join a baseline rule function to its metadata.

    Use it as a decorator:

        @compares(IDN_002)
        def idn_002(ir: Ir, baseline: Ir, configuration: Configuration) -> Iterator[Hit]: ...
    """

    def join(compare: BaselineCheck) -> BaselineRuleCheck:
        return BaselineRuleCheck(rule, _no_hits, compare)

    return join
