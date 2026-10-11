# trace: PRD-VAL-006, PRD-VAL-009, PRD-CORE-006, PRD-CORE-007, PRD-CORE-028
"""Write the findings of the validator as text or as JSON.

Both formats keep the order of the findings (PRD-VAL-007). The waived
findings are in a separate group after the other findings (PRD-VAL-009). The
JSON form uses the canonical JSON writer of the IR, so the same findings give
the same bytes (PRD-CORE-028).
"""

from collections.abc import Mapping

from dsml.ir.model import Finding, Severity
from dsml.ir.writer import JsonValue, canonical_json, to_data
from dsml.validate.rule import RuleCheck
from dsml.validate.waivers import WaivedFinding, Waiver

SEVERITIES: tuple[Severity, ...] = ("error", "warning", "info")


# trace: PRD-CORE-007
def finding_line(finding: Finding) -> str:
    """Give one line for a finding: the location, the severity, the rule and the message."""
    location = finding.location
    where = "" if location is None else f"{location.file}:{location.line}:{location.column}: "
    return f"{where}{finding.severity}: {finding.rule}: {finding.message}"


def _count(findings: tuple[Finding, ...]) -> dict[Severity, int]:
    return {level: sum(item.severity == level for item in findings) for level in SEVERITIES}


# trace: PRD-VAL-009
def waiver_line(waiver: Waiver) -> str:
    """Give one line for a waiver: the reason, the owner and the expires date."""
    expires = "" if waiver.expires is None else f", expires {waiver.expires}"
    return f"waiver: {waiver.reason} (owner: {waiver.owner}{expires})"


# trace: PRD-CORE-007, PRD-VAL-006, PRD-VAL-009
def text_report(
    findings: tuple[Finding, ...],
    rules: Mapping[str, RuleCheck],
    waived: tuple[WaivedFinding, ...] = (),
) -> str:
    """Write the findings as text.

    Each finding has one line, then one line with the fix hint of its rule.
    The next line gives the number of findings of each severity. If there are
    waived findings, the group "Waived findings" follows. Each waived finding
    has one line, then one line with its waiver.
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
    if waived:
        lines.append(f"Waived findings: {len(waived)}.")
        for item in waived:
            lines.append(finding_line(item.finding))
            lines.append(f"  {waiver_line(item.waiver)}")
    return "".join(f"{line}\n" for line in lines)


def _finding_data(finding: Finding, rules: Mapping[str, RuleCheck]) -> dict[str, JsonValue]:
    data = to_data(finding)
    check = rules.get(finding.rule)
    data["fixHint"] = None if check is None else check.rule.fix_hint
    return data


# trace: PRD-VAL-009
def waiver_data(waiver: Waiver) -> dict[str, JsonValue]:
    """Give the JSON object of a waiver."""
    return {
        "expires": waiver.expires,
        "owner": waiver.owner,
        "reason": waiver.reason,
        "rule": waiver.rule,
    }


# trace: PRD-CORE-028, PRD-VAL-006, PRD-VAL-009
def json_report(
    findings: tuple[Finding, ...],
    rules: Mapping[str, RuleCheck],
    waived: tuple[WaivedFinding, ...] = (),
) -> str:
    """Write the findings as canonical JSON.

    The object has the list `findings`, the list `waived` and the object
    `summary`. Each finding has the keys of the IR finding and the key
    `fixHint`. Each waived finding also has the key `waiver`. The summary
    gives the number of findings of each severity and the number of waived
    findings.
    """
    items: list[JsonValue] = [_finding_data(finding, rules) for finding in findings]
    waived_items: list[JsonValue] = []
    for item in waived:
        data = _finding_data(item.finding, rules)
        data["waiver"] = waiver_data(item.waiver)
        waived_items.append(data)
    summary: dict[str, JsonValue] = dict(_count(findings).items())
    summary["waived"] = len(waived)
    return canonical_json({"findings": items, "summary": summary, "waived": waived_items}).decode()
