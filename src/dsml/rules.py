# trace: PRD-VAL-001, PRD-VAL-002, PRD-VAL-003
"""The metadata of the validation rules.

Each rule has an ID, a category, a default severity, a message and a fix hint
(PRD-VAL-001). This module gives the rules of the category SYN. The IR adapter
makes their findings (PRD-CORE-021). The rule catalog of the validator adds
the other categories.
"""

from dataclasses import dataclass

from dsml.ir.model import Severity


# trace: PRD-VAL-001
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

    @property
    def category(self) -> str:
        """The category of the rule, for example "SYN" for "SYN-001"."""
        return self.id.split("-", 1)[0]


# trace: PRD-CORE-021
SYN_001 = Rule(
    id="SYN-001",
    severity="error",
    message="OpenSysML reports a syntax error or a name that it cannot resolve.",
    fix_hint="Correct the SysML v2 text or the name at the location of the finding.",
)

# trace: PRD-CORE-021
SYN_002 = Rule(
    id="SYN-002",
    severity="warning",
    message="OpenSysML reports a warning.",
    fix_hint="Correct the model at the location of the finding. Then OpenSysML gives no warning.",
)

RULES: dict[str, Rule] = {rule.id: rule for rule in (SYN_001, SYN_002)}
"""All rules of this module, by rule ID."""
