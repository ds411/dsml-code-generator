# trace: PRD-DSML-040, PRD-CORE-026
"""Find the infrastructure elements of the IR and the links between them.

The local modules of the infrastructure generator use these functions to
find the logical elements of one kind, their AWS realizations, the
overrides of an environment and the `#Uses` links (PRD-DSML-040).
"""

from dsml.errors import ToolchainError
from dsml.ir.model import Element, Ir, LinkType


def elements_of_kind(ir: Ir, kind: str) -> tuple[Element, ...]:
    """Give the elements of one kind, sorted by identity."""
    return tuple(sorted((item for item in ir.elements if item.kind == kind), key=Element.sort_key))


def element(ir: Ir, identity: str) -> Element:
    """Give the element with an identity."""
    for item in ir.elements:
        if item.identity == identity:
            return item
    raise ToolchainError(f'The IR has no element "{identity}".')


def sources(ir: Ir, link_type: LinkType, target: str) -> tuple[str, ...]:
    """Give the sorted identities of the sources of the links of one type to a target."""
    return tuple(
        sorted(
            {link.source for link in ir.links if link.type == link_type and link.target == target}
        )
    )


# trace: PRD-DSML-040
def realization(ir: Ir, logical: Element) -> Element:
    """Give the AWS realization of a logical element (`#Realizes`)."""
    found = sources(ir, "realizes", logical.identity)
    if len(found) != 1:
        raise ToolchainError(
            f'The element "{logical.identity}" must have one AWS realization, not {len(found)}.'
        )
    return element(ir, found[0])


# trace: PRD-DSML-042
def overrides(ir: Ir, environment: str, realization_identity: str) -> tuple[str, ...]:
    """Give the sorted identities of the overrides of a realization in one environment."""
    return tuple(
        sorted(
            item.identity
            for item in ir.elements
            if item.kind == "Override"
            and item.owner == environment
            and realization_identity in item.types
        )
    )


# trace: PRD-IAC-011
def network(ir: Ir) -> Element:
    """Give the one network of the model."""
    found = elements_of_kind(ir, "Network")
    if len(found) != 1:
        raise ToolchainError(f"The model must have one #Network element, not {len(found)}.")
    return found[0]
