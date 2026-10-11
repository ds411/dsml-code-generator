# trace: PRD-VAL-015, PRD-TRACE-001
"""The rules of the category COV (coverage).

The rules follow the links of the IR (PRD-TRACE-001):

| Link | Source | Target |
| --- | --- | --- |
| `stakeholder` | The need | The stakeholder |
| `frame` | The requirement | The framed need |
| `derivation` | The derived requirement | The original requirement |
| `satisfy` | The satisfying element | The requirement |
| `verify` | The verification | The requirement |

The order of the requirement statuses is `draft`, `approved`, `implemented`,
`verified`, `retired` (PRD-DSML-016). For COV-003 and COV-004, the status
`approved` or later is `approved`, `implemented` or `verified`. A `retired`
requirement is not in the product, thus these rules do not examine it.

COV-006 is the only rule that reads more than the IR. It makes sure that each
test file exists. The path of a test file is relative to the folder of the
configuration file, the repository root (PRD-CORE-012, PRD-DSML-048).
"""

from collections.abc import Iterator
from pathlib import Path

from dsml.config import Configuration
from dsml.ir.model import (
    Element,
    ElementKind,
    EnumValue,
    Ir,
    LinkType,
    ListValue,
    StringValue,
    Value,
)
from dsml.validate.rule import Hit, Rule, implements

# trace: PRD-VAL-015
COV_001 = Rule(
    id="COV-001",
    severity="warning",
    message="No requirement frames a need.",
    fix_hint="Add a requirement with `frame <need>;`, or remove the need.",
)

# trace: PRD-VAL-015
COV_002 = Rule(
    id="COV-002",
    severity="warning",
    message="A requirement frames no need and is not derived from a different requirement.",
    fix_hint="Add `frame <need>;` to the requirement, or derive it from a different requirement.",
)

# trace: PRD-VAL-015
COV_003 = Rule(
    id="COV-003",
    severity="warning",
    message='A requirement with the status "approved" or later has no satisfying element.',
    fix_hint="Add `satisfy <requirement> by <element>;` to the application layer.",
)

# trace: PRD-VAL-015
COV_004 = Rule(
    id="COV-004",
    severity="warning",
    message='A requirement with the status "approved" or later has no verification.',
    fix_hint="Add a verification with `verify <requirement>;` in its objective.",
)

# trace: PRD-VAL-015
COV_005 = Rule(
    id="COV-005",
    severity="error",
    message='A requirement has the status "verified" but no verification.',
    fix_hint="Add a verification with `verify <requirement>;` in its objective, "
    "or change the status.",
)

# trace: PRD-VAL-015, PRD-DSML-048
COV_006 = Rule(
    id="COV-006",
    severity="warning",
    message='A verification with the method "test" refers to a test file that does not exist.',
    fix_hint="Correct the path in `testFiles`, or add the test file. The path is relative "
    "to the folder of the configuration file.",
)

# trace: PRD-VAL-015
COV_007 = Rule(
    id="COV-007",
    severity="info",
    message="A stakeholder has no need.",
    fix_hint="Add a need with `stakeholder <name> : <stakeholder>;`, or remove the stakeholder.",
)

APPROVED_OR_LATER = frozenset({"approved", "implemented", "verified"})
"""The statuses that COV-003 and COV-004 examine."""


def _elements(ir: Ir, kind: ElementKind) -> Iterator[Element]:
    return (element for element in ir.elements if element.kind == kind)


def _targets(ir: Ir, link_type: LinkType) -> set[str]:
    """Give the targets of the links of one type."""
    return {link.target for link in ir.links if link.type == link_type}


def _sources(ir: Ir, link_type: LinkType) -> set[str]:
    """Give the sources of the links of one type, if the target is a different element."""
    return {
        link.source for link in ir.links if link.type == link_type and link.source != link.target
    }


def _attribute(element: Element, name: str) -> Value | None:
    for attribute in element.attributes:
        if attribute.name == name:
            return attribute.value
    return None


def _literal(element: Element, name: str) -> str | None:
    """Give the literal of an enumeration attribute, for example "approved"."""
    value = _attribute(element, name)
    return value.literal if isinstance(value, EnumValue) else None


def _requirements(ir: Ir, statuses: frozenset[str]) -> Iterator[Element]:
    for requirement in _elements(ir, "Requirement"):
        if _literal(requirement, "status") in statuses:
            yield requirement


# trace: PRD-VAL-015, PRD-TRACE-001
@implements(COV_001)
def cov_001(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    framed = _targets(ir, "frame")
    for need in _elements(ir, "Need"):
        if need.identity not in framed:
            yield Hit(
                f"No requirement frames the need {need.identity}.", need.location, need.identity
            )


# trace: PRD-VAL-015, PRD-TRACE-001
@implements(COV_002)
def cov_002(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    linked = _sources(ir, "frame") | _sources(ir, "derivation")
    for requirement in _elements(ir, "Requirement"):
        if requirement.identity not in linked:
            yield Hit(
                f"The requirement {requirement.identity} frames no need and is not derived "
                "from a different requirement.",
                requirement.location,
                requirement.identity,
            )


# trace: PRD-VAL-015, PRD-TRACE-001
@implements(COV_003)
def cov_003(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    satisfied = _targets(ir, "satisfy")
    for requirement in _requirements(ir, APPROVED_OR_LATER):
        if requirement.identity not in satisfied:
            yield Hit(
                f'The requirement {requirement.identity} has the status "'
                f'{_literal(requirement, "status")}" but no satisfying element.',
                requirement.location,
                requirement.identity,
            )


# trace: PRD-VAL-015, PRD-TRACE-001
@implements(COV_004)
def cov_004(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    verified = _targets(ir, "verify")
    for requirement in _requirements(ir, APPROVED_OR_LATER):
        if requirement.identity not in verified:
            yield Hit(
                f'The requirement {requirement.identity} has the status "'
                f'{_literal(requirement, "status")}" but no verification.',
                requirement.location,
                requirement.identity,
            )


# trace: PRD-VAL-015, PRD-TRACE-001
@implements(COV_005)
def cov_005(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    verified = _targets(ir, "verify")
    for requirement in _requirements(ir, frozenset({"verified"})):
        if requirement.identity not in verified:
            yield Hit(
                f'The requirement {requirement.identity} has the status "verified" '
                "but no verification.",
                requirement.location,
                requirement.identity,
            )


def _test_files(value: Value | None) -> Iterator[str]:
    """Give the paths of a `testFiles` value: one string or a list of strings."""
    if isinstance(value, StringValue):
        yield value.value
    elif isinstance(value, ListValue):
        for item in value.items:
            yield from _test_files(item)


# trace: PRD-VAL-015, PRD-DSML-048
@implements(COV_006)
def cov_006(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    root = configuration.root
    for verification in _elements(ir, "Verification"):
        if _literal(verification, "method") != "test":
            continue
        attribute = next(
            (item for item in verification.attributes if item.name == "testFiles"), None
        )
        if attribute is None:
            continue
        location = attribute.location or verification.location
        for path in sorted(set(_test_files(attribute.value))):
            if not path or not (root / Path(path)).is_file():
                yield Hit(
                    f'The verification {verification.identity} refers to the test file "{path}". '
                    "This file does not exist.",
                    location,
                    verification.identity,
                )


# trace: PRD-VAL-015, PRD-TRACE-001
@implements(COV_007)
def cov_007(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    with_needs = _targets(ir, "stakeholder")
    for stakeholder in _elements(ir, "Stakeholder"):
        if stakeholder.identity not in with_needs:
            yield Hit(
                f"The stakeholder {stakeholder.identity} has no need.",
                stakeholder.location,
                stakeholder.identity,
            )


RULES = (cov_001, cov_002, cov_003, cov_004, cov_005, cov_006, cov_007)
"""The rules of this module."""
