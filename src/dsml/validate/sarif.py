# trace: PRD-VAL-006, PRD-CORE-028, PRD-CORE-033
"""Write the findings of the validator as SARIF 2.1.0.

GitHub code scanning and other code review tools read SARIF. The log has one
run. `tool.driver.rules` has the metadata of each rule of the registry, sorted
by rule ID. Each result has the rule, the level, the message and the location.

The output is byte-identical for the same findings (PRD-CORE-028): the writer
uses the canonical JSON writer of the IR, the lists are sorted, and the log
has no time and no absolute path (PRD-CORE-033).
"""

import posixpath
from collections.abc import Mapping
from typing import Final
from urllib.parse import quote

from dsml.ir.model import Finding, Location, Severity
from dsml.ir.writer import JsonValue, canonical_json
from dsml.validate.rule import Rule, RuleCheck

SCHEMA: Final = "https://json.schemastore.org/sarif-2.1.0.json"
"""The JSON Schema of SARIF 2.1.0."""

VERSION: Final = "2.1.0"
"""The SARIF version."""

LEVELS: Final[Mapping[Severity, str]] = {"error": "error", "warning": "warning", "info": "note"}
"""The SARIF level of each severity."""


# trace: PRD-CORE-033
def relative_uri(file: str, base: str = "") -> str:
    """Give the relative URI of a model file.

    `file` is relative to the root of the IR. `base` is the folder of the
    configuration file, relative to the same root. The URI is relative to
    `base` and uses percent-encoding.
    """
    path = posixpath.relpath(file, base or ".")
    return quote(path, safe="/")


# trace: PRD-VAL-006
def rule_descriptor(rule: Rule) -> dict[str, JsonValue]:
    """Give the SARIF metadata of one rule.

    The message of the rule is the short description, and the fix hint is
    the help text. The default configuration gives the default severity.
    """
    return {
        "defaultConfiguration": {"level": LEVELS[rule.severity]},
        "help": {"text": rule.fix_hint},
        "id": rule.id,
        "name": rule.id.replace("-", ""),
        "properties": {"category": rule.category},
        "shortDescription": {"text": rule.message},
    }


def _location(location: Location, base: str) -> dict[str, JsonValue]:
    return {
        "physicalLocation": {
            "artifactLocation": {"uri": relative_uri(location.file, base)},
            "region": {"startColumn": location.column, "startLine": location.line},
        }
    }


# trace: PRD-VAL-006
def result(finding: Finding, index: Mapping[str, int], base: str) -> dict[str, JsonValue]:
    """Give the SARIF result of one finding.

    A finding with an element has a logical location with the identity of
    the element. A finding with no location has no physical location.
    """
    data: dict[str, JsonValue] = {
        "level": LEVELS[finding.severity],
        "message": {"text": finding.message},
        "ruleId": finding.rule,
    }
    if finding.rule in index:
        data["ruleIndex"] = index[finding.rule]
    locations: list[JsonValue] = []
    if finding.location is not None:
        locations.append(_location(finding.location, base))
    if finding.element is not None:
        locations.append({"logicalLocations": [{"fullyQualifiedName": finding.element}]})
    if locations:
        data["locations"] = locations
    return data


# trace: PRD-VAL-006, PRD-CORE-028, PRD-CORE-033
def sarif_report(
    findings: tuple[Finding, ...],
    rules: Mapping[str, RuleCheck],
    version: str,
    base: str = "",
) -> str:
    """Write the findings as a SARIF 2.1.0 log.

    `version` is the version of the toolchain. `base` is the folder of the
    configuration file, relative to the root of the IR. Each URI is relative
    to that folder. The results keep the order of the findings (PRD-VAL-007).
    """
    ids = sorted(rules)
    index = {rule_id: number for number, rule_id in enumerate(ids)}
    driver: dict[str, JsonValue] = {
        "name": "dsml",
        "rules": [rule_descriptor(rules[rule_id].rule) for rule_id in ids],
        "version": version,
    }
    run: dict[str, JsonValue] = {
        "columnKind": "unicodeCodePoints",
        "results": [result(finding, index, base) for finding in findings],
        "tool": {"driver": driver},
    }
    log: dict[str, JsonValue] = {"$schema": SCHEMA, "runs": [run], "version": VERSION}
    return canonical_json(log).decode()
