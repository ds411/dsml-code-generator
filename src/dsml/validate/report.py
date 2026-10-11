# trace: PRD-VAL-006, PRD-CORE-006, PRD-CORE-007, PRD-CORE-028
"""Write the findings of the validator as text or as JSON.

Both formats keep the order of the findings (PRD-VAL-007). The JSON form uses
the canonical JSON writer of the IR, so the same findings give the same
bytes (PRD-CORE-028).
"""

from collections.abc import Mapping

from dsml.ir.model import Finding, Severity
from dsml.ir.writer import JsonValue, canonical_json, to_data
from dsml.validate.rule import RuleCheck

SEVERITIES: tuple[Severity, ...] = ("error", "warning", "info")


# trace: PRD-CORE-007
def finding_line(finding: Finding) -> str:
    """Give one line for a finding: the location, the severity, the rule and the message."""
    location = finding.location
    where = "" if location is None else f"{location.file}:{location.line}:{location.column}: "
    return f"{where}{finding.severity}: {finding.rule}: {finding.message}"


def _count(findings: tuple[Finding, ...]) -> dict[Severity, int]:
    return {level: sum(item.severity == level for item in findings) for level in SEVERITIES}


# trace: PRD-CORE-007, PRD-VAL-006
def text_report(findings: tuple[Finding, ...], rules: Mapping[str, RuleCheck]) -> str:
    """Write the findings as text.

    Each finding has one line, then one line with the fix hint of its rule.
    The last line gives the number of findings of each severity.
    """
    lines: list[str] = []
    for finding in findings:
        lines.append(finding_line(finding))
        check = rules.get(finding.rule)
        if check is not None:
            lines.append(f"  fix: {check.rule.fix_hint}")
    count = _count(findings)
    errors = "1 error" if count["error"] == 1 else f"{count['error']} errors"
    warnings = "1 warning" if count["warning"] == 1 else f"{count['warning']} warnings"
    lines.append(f"Findings: {errors}, {warnings}, {count['info']} info.")
    return "".join(f"{line}\n" for line in lines)


# trace: PRD-CORE-028, PRD-VAL-006
def json_report(findings: tuple[Finding, ...], rules: Mapping[str, RuleCheck]) -> str:
    """Write the findings as canonical JSON.

    The object has the list `findings` and the object `summary` with the
    number of findings of each severity. Each finding has the keys of the IR
    finding and the key `fixHint`.
    """
    items: list[JsonValue] = []
    for finding in findings:
        data = to_data(finding)
        check = rules.get(finding.rule)
        data["fixHint"] = None if check is None else check.rule.fix_hint
        items.append(data)
    summary: dict[str, JsonValue] = dict(_count(findings).items())
    return canonical_json({"findings": items, "summary": summary}).decode()
