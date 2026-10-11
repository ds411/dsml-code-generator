# trace: PRD-CORE-021, PRD-VAL-015
"""The rules of the category SYN.

The IR adapter makes the SYN findings from the OpenSysML diagnostics
(`dsml.adapter.findings`) and writes them into the IR. These rules read the
SYN findings from the IR. Thus the configuration overrides apply to them as
to all other rules, and they go into the same list of findings.
"""

from collections.abc import Iterator

from dsml.config import Configuration
from dsml.ir.model import Ir
from dsml.validate.rule import Hit, Rule, implements

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


def _adapter_hits(ir: Ir, rule: Rule) -> Iterator[Hit]:
    """Give a hit for each finding of the rule that the IR adapter wrote."""
    for finding in ir.findings:
        if finding.rule == rule.id:
            yield Hit(finding.message, finding.location, finding.element)


# trace: PRD-CORE-021
@implements(SYN_001)
def syn_001(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    return _adapter_hits(ir, SYN_001)


# trace: PRD-CORE-021
@implements(SYN_002)
def syn_002(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    return _adapter_hits(ir, SYN_002)


RULES = (syn_001, syn_002)
"""The rules of this module."""
