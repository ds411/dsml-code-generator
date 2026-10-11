# trace: PRD-VAL-012, PRD-VAL-015, PRD-CORE-026, PRD-CORE-054
"""The rules of the category FCN: the results of the formal constraints.

The IR adapter evaluates each formal constraint of each requirement one time
for each environment. It writes each result into the IR (PRD-CORE-054, Q57).
These rules read the results from the IR only. They do not use OpenSysML
(PRD-CORE-026).

- FCN-001: a result is `false`.
- FCN-002: a result is `unknown`, because a feature has no value. The message
  names each feature that has no value.
"""

from collections.abc import Iterator, Mapping

from dsml.config import Configuration
from dsml.ir.model import ConstraintResult, ConstraintValue, Element, Ir
from dsml.validate.rule import Hit, Rule, implements

# trace: PRD-VAL-012
FCN_001 = Rule(
    id="FCN-001",
    severity="error",
    message="A formal constraint is false for an environment.",
    fix_hint=(
        "Change the model so that the constraint is true in the environment, "
        "or correct the constraint."
    ),
)

# trace: PRD-VAL-012
FCN_002 = Rule(
    id="FCN-002",
    severity="warning",
    message=(
        "The adapter cannot evaluate a formal constraint for an environment, "
        "because a feature has no value."
    ),
    fix_hint=(
        "Give a value to each feature that the message names, in the AWS "
        "realization or in an override of the environment."
    ),
)


def _label(elements: Mapping[str, Element], identity: str) -> str:
    """Give the short name of an element, or its name, or its identity."""
    element = elements.get(identity)
    if element is None:
        return identity
    return element.short_name or element.name


def _results(ir: Ir, value: ConstraintValue) -> Iterator[tuple[ConstraintResult, str]]:
    """Give each constraint result with the value, and the start of its message."""
    elements = {element.identity: element for element in ir.elements}
    for result in ir.constraint_results:
        if result.value == value:
            requirement = _label(elements, result.requirement)
            environment = _label(elements, result.environment)
            yield (
                result,
                f'The formal constraint {result.index} of the requirement "{requirement}" '
                f'is {value} in the environment "{environment}".',
            )


# trace: PRD-VAL-012, PRD-CORE-054
@implements(FCN_001)
def fcn_001(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    for result, message in _results(ir, "false"):
        yield Hit(message, result.location, result.requirement)


# trace: PRD-VAL-012, PRD-CORE-054
@implements(FCN_002)
def fcn_002(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    for result, message in _results(ir, "unknown"):
        features = ", ".join(result.missing_features)
        if features:
            message = f"{message} These features have no value: {features}."
        yield Hit(message, result.location, result.requirement)


RULES = (fcn_001, fcn_002)
"""The rules of this module."""
