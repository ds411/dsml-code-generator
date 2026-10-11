# trace: PRD-VAL-009, PRD-VAL-010, PRD-VAL-015, PRD-DSML-055
"""The STR rules of the waivers.

- STR-014: a waiver is after its `expires` date.
- STR-015: a waiver has no reason or no owner, or names a rule that does not
  exist.

STR-014 needs the date of the expiry check, and a rule reads only the IR and
the configuration. Thus the rule engine reports STR-014 when it applies the
waivers (`dsml.validate.waivers`). The function of STR-014 gives no hit.
"""

from collections.abc import Iterator

from dsml.config import Configuration
from dsml.ir.model import Ir
from dsml.validate.rule import Hit, Rule, implements
from dsml.validate.rules import registry
from dsml.validate.waivers import problems, read_waivers

# trace: PRD-VAL-010
STR_014 = Rule(
    id="STR-014",
    severity="warning",
    message="A waiver is after its expires date.",
    fix_hint=(
        "Correct the model, then remove the waiver. "
        "If the waiver must stay, give a new expires date."
    ),
)

# trace: PRD-DSML-055
STR_015 = Rule(
    id="STR-015",
    severity="error",
    message="A waiver has no reason or no owner, or names a rule that does not exist.",
    fix_hint=(
        "Give the waiver a rule ID of the catalog, a reason and an owner, for example "
        '@Waiver { rule = "COV-003"; reason = "..."; owner = "..."; }.'
    ),
)


# trace: PRD-VAL-010
@implements(STR_014)
def str_014(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    """Give no hit. The rule engine reports STR-014 with the date of the check."""
    return iter(())


# trace: PRD-DSML-055, PRD-VAL-015
@implements(STR_015)
def str_015(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    rule_ids = registry().keys()
    for waiver in read_waivers(ir):
        for message in problems(waiver, rule_ids):
            yield Hit(message, waiver.location, waiver.element)


RULES = (str_014, str_015)
