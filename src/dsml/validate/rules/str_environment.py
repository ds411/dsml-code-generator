# trace: PRD-VAL-015
"""The STR rules of the environments: STR-011 and STR-012.

The rules read only the IR (PRD-VAL-001, PRD-CORE-026).
"""

from collections.abc import Iterator
from typing import Final

from dsml.config import Configuration
from dsml.ir.environments import environments
from dsml.ir.model import Element, Ir, StringValue
from dsml.ir.operations import attribute
from dsml.validate.rule import Hit, Rule, implements

# trace: PRD-DSML-041
ENVIRONMENTS: Final = ("dev", "staging", "prod")
"""The environments that each model must contain (PRD-DSML-041)."""

# trace: PRD-DSML-041
ENVIRONMENT_ATTRIBUTES: Final = ("accountId", "region", "domain")
"""The attributes that each environment must have (PRD-DSML-041)."""

# trace: PRD-DSML-042
OVERRIDE_ATTRIBUTES: Final = frozenset(
    {
        "cpu",
        "desiredCount",
        "instanceClass",
        "maxCount",
        "memory",
        "minCount",
        "multiAz",
        "natGatewayCount",
    }
)
"""The attributes of an AWS realization that an environment can change (PRD-DSML-042)."""

# trace: PRD-DSML-041
STR_011 = Rule(
    id="STR-011",
    severity="error",
    message="The environments dev, staging or prod are missing, or an environment has "
    "no account ID, Region or domain.",
    fix_hint="Add the #Environment parts dev, staging and prod. Give each environment "
    "the attributes accountId, region and domain.",
)

# trace: PRD-DSML-042
STR_012 = Rule(
    id="STR-012",
    severity="error",
    message="An environment changes an attribute that is not on the list of PRD-DSML-042.",
    fix_hint="Change only cpu, memory, instanceClass, desiredCount, minCount, maxCount, "
    "multiAz or natGatewayCount in an override. Put a different value in the AWS "
    "realization.",
)


# trace: PRD-DSML-041
SOLUTION_KINDS: Final = frozenset(
    {
        "Application",
        "AwsCognito",
        "AwsEcsService",
        "AwsRdsPostgres",
        "AwsSecrets",
        "AwsVpc",
        "ContainerService",
        "Environment",
        "Network",
        "Override",
        "RelationalDatabase",
        "SecretStore",
        "ToolingAccount",
        "UserDirectory",
    }
)
"""The element kinds of the application and infrastructure layers that need environments."""


def _root(ir: Ir) -> Element | None:
    """Give the first package of the model that has no owner, or None."""
    packages = [item for item in ir.elements if item.kind == "Package" and item.owner is None]
    return min(packages, key=lambda item: (item.location.sort_key(), item.identity), default=None)


# trace: PRD-DSML-041
@implements(STR_011)
def str_011(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    """Report each missing environment and each environment with a missing attribute.

    The environments are necessary only for a model with an application or
    an infrastructure element. Thus a model of the needs and requirements
    only, for example the PRD model, gets no finding for a missing
    environment. A missing environment gets the location of the root package
    of the model.
    """
    found = environments(ir)
    names = {item.name for item in found}
    root = _root(ir)
    solution = any(item.kind in SOLUTION_KINDS for item in ir.elements)
    for name in ENVIRONMENTS:
        if solution and name not in names:
            yield Hit(
                f"The model has no environment {name}.",
                None if root is None else root.location,
                None if root is None else root.identity,
            )
    for environment in found:
        missing: list[str] = []
        for name in ENVIRONMENT_ATTRIBUTES:
            value = attribute(environment, name)
            if not isinstance(value, StringValue) or not value.value:
                missing.append(name)
        if missing:
            yield Hit(
                f"The environment {environment.name} has no value for {', '.join(missing)}.",
                environment.location,
                environment.identity,
            )


# trace: PRD-DSML-042
@implements(STR_012)
def str_012(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    overrides = sorted(
        (item for item in ir.elements if item.kind == "Override"), key=Element.sort_key
    )
    for override in overrides:
        for changed in override.attributes:
            if changed.name in OVERRIDE_ATTRIBUTES:
                continue
            yield Hit(
                f"The override {override.name} changes the attribute {changed.name}. "
                "An environment cannot change this attribute.",
                override.location if changed.location is None else changed.location,
                override.identity,
            )


RULES = (str_011, str_012)
"""The rules of this module."""
