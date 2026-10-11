# trace: PRD-VAL-009, PRD-VAL-010, PRD-DSML-055, PRD-CORE-028
"""The waivers of the validator.

A `@Waiver` metadata usage on an element stops the findings of one rule on
that element (PRD-DSML-055, PRD-VAL-009). The waived findings stay visible in
a separate group of the report. After the `expires` date of the waiver, its
findings come back and the engine reports STR-014 (PRD-VAL-010).

The expiry check does not read the clock, because the same input must give
the same report (PRD-CORE-028). The command gives the date of the check: the
option `--date`, or else the commit date of `HEAD` of the local Git
repository of the model. `check_date()` gives this date.
"""

import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

from dsml.ir.model import Annotation, Finding, Ir, Location, StringValue

WAIVER: Final = "Waiver"
"""The name of the metadata definition of a waiver (PRD-DSML-055)."""

NOT_WAIVABLE: Final = frozenset({"STR-014", "STR-015"})
"""The rules that a waiver cannot stop. These rules report problems of the waivers."""


# trace: PRD-DSML-055
@dataclass(frozen=True, slots=True)
class Waiver:
    """One `@Waiver` on one element.

    `element` is the identity of the annotated element. An attribute that the
    model does not give is an empty text. `expires` is the text of the
    attribute `expires`, or `None` if the model does not give it.
    """

    element: str
    rule: str
    reason: str
    owner: str
    expires: str | None
    location: Location | None

    @property
    def expiry(self) -> date | None:
        """The `expires` date, or `None` if there is none or it is not a date."""
        if self.expires is None:
            return None
        try:
            return date.fromisoformat(self.expires)
        except ValueError:
            return None

    def expired(self, today: date | None) -> bool:
        """Tell if the date of the check is after the `expires` date.

        On the `expires` date, the waiver applies. With no date of the
        check, no waiver is expired.
        """
        expiry = self.expiry
        return today is not None and expiry is not None and today > expiry


# trace: PRD-VAL-009
@dataclass(frozen=True, slots=True)
class WaivedFinding:
    """A finding that a waiver stops, and the waiver."""

    finding: Finding
    waiver: Waiver


def _text(annotation: Annotation, name: str) -> str | None:
    for attribute in annotation.attributes:
        if attribute.name == name:
            value = attribute.value
            return value.value.strip() if isinstance(value, StringValue) else None
    return None


# trace: PRD-DSML-055
def read_waivers(ir: Ir) -> tuple[Waiver, ...]:
    """Give each waiver of the IR, in the order of the elements of the IR."""
    waivers: list[Waiver] = []
    for element in ir.elements:
        for annotation in element.annotations:
            if annotation.name != WAIVER:
                continue
            waivers.append(
                Waiver(
                    element=element.identity,
                    rule=_text(annotation, "rule") or "",
                    reason=_text(annotation, "reason") or "",
                    owner=_text(annotation, "owner") or "",
                    expires=_text(annotation, "expires"),
                    location=annotation.location or element.location,
                )
            )
    return tuple(waivers)


# trace: PRD-DSML-055, PRD-VAL-015
def problems(waiver: Waiver, rule_ids: Iterable[str]) -> Iterator[str]:
    """Give a message for each problem of a waiver (rule STR-015).

    A waiver must name a rule that exists, and it must have a reason and an
    owner. If it gives an `expires` date, the date must have the form
    YYYY-MM-DD.
    """
    where = f"The waiver on {waiver.element}"
    if not waiver.rule:
        yield f"{where} names no rule."
    elif waiver.rule not in set(rule_ids):
        yield f"{where} names the rule {waiver.rule}. This rule does not exist."
    if not waiver.reason:
        yield f"{where} has no reason."
    if not waiver.owner:
        yield f"{where} has no owner."
    if waiver.expires is not None and waiver.expiry is None:
        yield f'{where} has the expires value "{waiver.expires}". It is not a date YYYY-MM-DD.'


def _order(waiver: Waiver) -> tuple[str, str, date]:
    return (waiver.rule, waiver.element, waiver.expiry or date.max)


# trace: PRD-VAL-009, PRD-VAL-010
def apply_waivers(
    findings: Iterable[Finding], waivers: Iterable[Waiver], today: date | None
) -> tuple[tuple[Finding, ...], tuple[WaivedFinding, ...]]:
    """Split the findings into the findings that stay and the waived findings.

    A waiver stops a finding only if the finding has the rule and the element
    of the waiver (PRD-VAL-009). An expired waiver stops no finding
    (PRD-VAL-010). The caller gives only the waivers with no problem. Both
    results keep the order of `findings`.
    """
    active = {
        (waiver.rule, waiver.element): waiver
        for waiver in sorted(waivers, key=_order)
        if not waiver.expired(today) and waiver.rule not in NOT_WAIVABLE
    }
    kept: list[Finding] = []
    waived: list[WaivedFinding] = []
    for finding in findings:
        waiver = None if finding.element is None else active.get((finding.rule, finding.element))
        if waiver is None:
            kept.append(finding)
        else:
            waived.append(WaivedFinding(finding, waiver))
    return tuple(kept), tuple(waived)


# trace: PRD-VAL-010, PRD-CORE-028, PRD-TOP-004
def commit_date(root: Path) -> date | None:
    """Give the commit date of `HEAD` of the Git repository of a folder, in UTC.

    The function runs the local command `git`. It does not use the network
    (PRD-TOP-004). Give `None` if the folder is not in a Git repository, if
    the repository has no commit, or if there is no command `git`.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%ct", "HEAD"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError:
        return None
    seconds = result.stdout.strip()
    if result.returncode != 0 or not seconds.isdigit():
        return None
    return datetime.fromtimestamp(int(seconds), UTC).date()


# trace: PRD-VAL-010, PRD-CORE-028
def check_date(ir: Ir, root: Path, given: date | None = None) -> date | None:
    """Give the date of the expiry check.

    - `given` is the date of the option `--date`. If there is one, use it.
    - If no waiver of the IR has an `expires` date, give `None`. The check
      needs no date.
    - Else give the commit date of `HEAD`. If there is no commit, give the
      date of today in UTC. Only in this case does the clock change the
      report.
    """
    if given is not None:
        return given
    if not any(waiver.expiry is not None for waiver in read_waivers(ir)):
        return None
    found = commit_date(root)
    return datetime.now(UTC).date() if found is None else found
