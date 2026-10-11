# trace: PRD-CORE-007, PRD-CORE-021
"""Convert the OpenSysML diagnostics into findings of the category SYN.

An OpenSysML error gives SYN-001, and an OpenSysML warning gives SYN-002. Each
finding gives the file path relative to the repository root, the line and the
column.
"""

from collections.abc import Iterable

from dsml.adapter.engine import Diagnostic
from dsml.ir.model import Finding, Location
from dsml.validate.rules.syn import SYN_001, SYN_002


# trace: PRD-CORE-007, PRD-CORE-021
def syn_finding(diagnostic: Diagnostic) -> Finding:
    """Convert one OpenSysML diagnostic into a SYN finding.

    The rule depends on the severity only. A severity that is not "error"
    gives SYN-002. The message gives the text and the code of OpenSysML.
    """
    rule = SYN_001 if diagnostic.severity == "error" else SYN_002
    return Finding(
        rule=rule.id,
        severity=rule.severity,
        message=f"{diagnostic.message} (OpenSysML code: {diagnostic.code})",
        location=Location(
            file=diagnostic.file,
            line=max(diagnostic.line, 1),
            column=max(diagnostic.column, 1),
        ),
    )


# trace: PRD-CORE-021, PRD-VAL-007
def syn_findings(diagnostics: Iterable[Diagnostic]) -> tuple[Finding, ...]:
    """Convert the diagnostics into SYN findings, sorted (PRD-VAL-007)."""
    return tuple(sorted((syn_finding(item) for item in diagnostics), key=Finding.sort_key))
