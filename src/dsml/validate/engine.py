# trace: PRD-VAL-001, PRD-VAL-003, PRD-VAL-004, PRD-VAL-007, PRD-VAL-011, PRD-VAL-013, PRD-CORE-026
"""The rule engine. It runs the enabled rules on the IR.

The engine reads only the IR and the configuration (PRD-CORE-026). It applies
the keys `rules.severity` and `rules.optional` of the configuration file:

- The configuration can increase the severity of each rule.
- The configuration can decrease the severity of a rule with the default
  severity `warning` or `info`, or turn it off with `off`.
- The configuration must not decrease the severity of a rule with the
  default severity `error`, or turn it off. This is a configuration error
  (PRD-VAL-004).
- The rules of an optional rule set, for example TXT, run only if the key
  `rules.optional` turns the set on (PRD-VAL-013).
- A baseline rule, for example an IDN rule, runs only if there is a
  baseline IR (PRD-VAL-011).
"""

from collections.abc import Mapping
from typing import Final

from dsml.config import Configuration, ConfigurationError, RuleSeverity
from dsml.ir.model import Finding, Ir, Severity
from dsml.validate.rule import RuleCheck
from dsml.validate.rules import registry
from dsml.validate.rules.syn import SYN_001

RANK: Final[Mapping[Severity, int]] = {"info": 0, "warning": 1, "error": 2}
"""The order of the severities, from low to high."""


# trace: PRD-VAL-004, PRD-VAL-013
def severities(configuration: Configuration, rules: Mapping[str, RuleCheck]) -> dict[str, Severity]:
    """Give the severity of each enabled rule after the configuration overrides.

    A rule that is off is not in the result. An override for a rule that does
    not exist, and an override that decreases the severity `error`, are
    configuration errors with exit code 2.
    """
    overrides: dict[str, RuleSeverity] = dict(configuration.rules.severity)
    where = "the configuration" if configuration.path is None else str(configuration.path)
    errors: list[str] = []
    for rule_id, level in overrides.items():
        check = rules.get(rule_id)
        if check is None:
            errors.append(f"{where}: rules.severity.{rule_id}: The rule {rule_id} does not exist.")
        elif check.rule.severity == "error" and level != "error":
            errors.append(
                f"{where}: rules.severity.{rule_id}: The rule {rule_id} has the default "
                f'severity "error". You cannot set it to "{level}" (PRD-VAL-004).'
            )
    if errors:
        raise ConfigurationError(errors)
    result: dict[str, Severity] = {}
    for rule_id, check in rules.items():
        if check.rule.optional and check.rule.category not in configuration.rules.optional:
            continue
        level = overrides.get(rule_id, check.rule.severity)
        if level != "off":
            result[rule_id] = level
    return result


# trace: PRD-VAL-001, PRD-VAL-003, PRD-VAL-004, PRD-VAL-007, PRD-VAL-011
class Validator:
    """Run the enabled rules on the IR.

    The constructor reads the overrides of the configuration. Thus an error
    in the overrides stops the command before it reads the model.
    """

    def __init__(
        self, configuration: Configuration, rules: Mapping[str, RuleCheck] | None = None
    ) -> None:
        self.configuration = configuration
        self.rules = registry() if rules is None else rules
        self.severities = severities(configuration, self.rules)

    def run(self, ir: Ir, baseline: Ir | None = None) -> tuple[Finding, ...]:
        """Give the findings of all enabled rules, sorted (PRD-VAL-007).

        The findings are sorted by file, line, column and rule ID. A finding
        with no location comes first. If the IR has a SYN-001 finding, only
        the SYN rules run, because the elements of the IR are not complete.
        The baseline rules run only if `baseline` gives the IR of a baseline
        (PRD-VAL-011).
        """
        broken = any(finding.rule == SYN_001.id for finding in ir.findings)
        findings: list[Finding] = []
        for rule_id, severity in self.severities.items():
            check = self.rules[rule_id]
            if broken and check.rule.category != SYN_001.category:
                continue
            for hit in check.hits(ir, self.configuration, baseline):
                findings.append(
                    Finding(
                        rule=rule_id,
                        severity=severity,
                        message=check.rule.message if hit.message is None else hit.message,
                        location=hit.location,
                        element=hit.element,
                    )
                )
        return tuple(sorted(findings, key=lambda item: (*item.sort_key(), item.element or "")))


# trace: PRD-VAL-003, PRD-VAL-005
def fails(findings: tuple[Finding, ...], fail_on: Severity = "error") -> bool:
    """Tell if a finding has the severity `fail_on` or a higher severity."""
    return any(RANK[finding.severity] >= RANK[fail_on] for finding in findings)
