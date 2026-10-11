# trace: PRD-DSML-041, PRD-DSML-042, PRD-CORE-026
"""Give the attribute values of the AWS realizations in each environment.

An AWS realization holds the default values of its attributes. An override in
an environment subsets one realization and changes some of its attributes
(PRD-DSML-042). The IR holds the realization and each override as elements.
The functions of this module join them, so that a generator gets the values of
one environment from the IR only (PRD-CORE-026).

This module does not import OpenSysML.
"""

from collections.abc import Mapping

from dsml.ir.model import Attribute, Element, Ir

AWS_KINDS = frozenset({"AwsVpc", "AwsEcsService", "AwsRdsPostgres", "AwsCognito", "AwsSecrets"})
"""The element kinds of AWS realizations (PRD-DSML-037)."""


# trace: PRD-DSML-041
def environments(ir: Ir) -> tuple[Element, ...]:
    """Give the environments of the IR, sorted by identity."""
    return tuple(
        sorted(
            (element for element in ir.elements if element.kind == "Environment"),
            key=Element.sort_key,
        )
    )


# trace: PRD-DSML-041, PRD-DSML-042
def realization_attributes(ir: Ir, environment: str) -> Mapping[str, Mapping[str, Attribute]]:
    """Give the attributes of each AWS realization in one environment.

    `environment` is the identity of an environment. The result maps the
    identity of each realization to its attributes by name. An override in the
    environment replaces the default value of the realization.
    """
    if not any(element.identity == environment for element in environments(ir)):
        raise KeyError(f'The IR has no environment "{environment}".')
    result: dict[str, dict[str, Attribute]] = {
        element.identity: {attribute.name: attribute for attribute in element.attributes}
        for element in ir.elements
        if element.kind in AWS_KINDS
    }
    for override in sorted(ir.elements, key=Element.sort_key):
        if override.kind != "Override" or override.owner != environment:
            continue
        for realization in override.types:
            if realization in result:
                for attribute in override.attributes:
                    result[realization][attribute.name] = attribute
    return result
