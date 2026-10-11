# trace: PRD-IAC-001, PRD-IAC-007, PRD-IAC-008, PRD-IAC-023, PRD-CORE-026
"""The local modules and the module calls of the environment root modules.

Each local module writes the AWS resources of one logical kind (PRD-IAC-001).
The module is the same for all environments and for all elements of its kind.
The generator writes a module only if the model has an element of its kind.

Each environment root module calls the module one time for each logical
element of its kind. The address of the call is the snake case of the element
name, for example `module.network` (PRD-IAC-008). The arguments of the call
come from the AWS realization of the element in the environment (PRD-IAC-023).

The modules use only `aws_*` resources and data sources (PRD-IAC-007).

This module reads only the IR (PRD-CORE-026).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate import names as safe_names
from dsml.generate.infrastructure import hcl, names
from dsml.ir.environments import realization_attributes
from dsml.ir.model import Attribute, Element, IntegerValue, Ir

MODULE_FILES: Final = ("main", "outputs", "variables")
"""The files of each local module, without `.gen.tf`."""

TEMPLATE_FOLDER: Final = "infrastructure/modules"
"""The folder of the templates of the local modules."""

MIN_ZONES: Final = 2
"""The minimum number of availability zones of a network (PRD-IAC-011)."""

DEFAULT_NAT_GATEWAYS: Final = 1
"""The number of NAT gateways of a network that does not set `natGatewayCount`.

The tasks in the private subnets must get to ECR and to the AWS APIs. Thus
the default is one NAT gateway, not zero.
"""


# trace: PRD-TRACE-006, PRD-TRACE-007
@dataclass(frozen=True, slots=True)
class RootOutput:
    """An output of an environment root module that gives a value of a module call."""

    name: str
    description: str
    value: str


# trace: PRD-IAC-008, PRD-IAC-023, PRD-IAC-035
@dataclass(frozen=True, slots=True)
class ModuleCall:
    """The call of a local module for one logical element in one environment."""

    folder: str
    element: Element
    realization: Element
    arguments: tuple[tuple[str, str], ...]
    """The name and the HCL expression of each argument, sorted by name."""
    outputs: tuple[RootOutput, ...]

    @property
    def address(self) -> str:
        """Give the name of the module call: the snake case of the element name."""
        return names.hcl_address(self.element.name)

    @property
    def identities(self) -> tuple[str, ...]:
        """Give the identities of the logical element and its AWS realization, sorted."""
        return tuple(sorted((self.element.identity, self.realization.identity)))

    @property
    def lines(self) -> tuple[str, ...]:
        """Give the argument lines of the call, aligned in the format of `tofu fmt`."""
        width = max(len(name) for name, _ in self.arguments)
        return tuple(f"{name.ljust(width)} = {value}" for name, value in self.arguments)


type Arguments = Callable[[Element, Mapping[str, Attribute], str, str], dict[str, str]]
"""Give the arguments of a call from the element, the attributes of its
realization in the environment, the product and the environment."""

type Outputs = Callable[[str], tuple[RootOutput, ...]]
"""Give the root module outputs of a call from the address of the call."""


# trace: PRD-IAC-001
@dataclass(frozen=True, slots=True)
class LocalModule:
    """A local module for one logical kind."""

    kind: str
    """The IR kind of the logical elements, for example `Network`."""
    realization_kind: str
    """The IR kind of the AWS realizations, for example `AwsVpc`."""
    folder: str
    """The folder of the module in `modules/`, for example `network`."""
    arguments: Arguments
    outputs: Outputs


def _integer(attributes: Mapping[str, Attribute], name: str, default: int) -> int:
    """Give the integer value of an attribute, or the default if the attribute has no value."""
    attribute = attributes.get(name)
    if attribute is None:
        return default
    if not isinstance(attribute.value, IntegerValue):
        raise ToolchainError(f'The attribute "{name}" must have an integer value.')
    return attribute.value.value


# trace: PRD-IAC-011
def zone_count(nat_gateway_count: int) -> int:
    """Give the number of availability zones of a network.

    The network has two or more zones, and one or more zones for each NAT
    gateway.
    """
    return max(MIN_ZONES, nat_gateway_count)


# trace: PRD-IAC-008, PRD-IAC-011, PRD-IAC-035, PRD-IAC-037
def _network_arguments(
    element: Element, attributes: Mapping[str, Attribute], product: str, environment: str
) -> dict[str, str]:
    nat_gateways = _integer(attributes, "natGatewayCount", DEFAULT_NAT_GATEWAYS)
    if nat_gateways < 0:
        raise ToolchainError(f'The network "{element.identity}" has a negative natGatewayCount.')
    return {
        "element": hcl.string(names.tag_value(element.identity)),
        "name": hcl.string(names.aws_name(product, environment, element.name, "vpc")),
        "nat_gateway_count": str(nat_gateways),
        "zone_count": str(zone_count(nat_gateways)),
    }


# trace: PRD-IAC-010
def _network_outputs(address: str) -> tuple[RootOutput, ...]:
    return (
        RootOutput(
            f"{address}_private_subnet_ids",
            f"The IDs of the private subnets of module.{address}.",
            f"module.{address}.private_subnet_ids",
        ),
        RootOutput(
            f"{address}_public_subnet_ids",
            f"The IDs of the public subnets of module.{address}.",
            f"module.{address}.public_subnet_ids",
        ),
        RootOutput(
            f"{address}_vpc_id",
            f"The ID of the VPC of module.{address}.",
            f"module.{address}.vpc_id",
        ),
    )


# trace: PRD-IAC-008, PRD-IAC-020, PRD-IAC-035, PRD-IAC-037
def _secret_store_arguments(
    element: Element, attributes: Mapping[str, Attribute], product: str, environment: str
) -> dict[str, str]:
    return {
        "element": hcl.string(names.tag_value(element.identity)),
        "key_alias": hcl.string(names.kms_alias(product, environment, element.name)),
        "name": hcl.string(names.aws_name(product, environment, element.name, "secret")),
    }


# trace: PRD-IAC-020
def _secret_store_outputs(address: str) -> tuple[RootOutput, ...]:
    return (
        RootOutput(
            f"{address}_secret_arn",
            f"The ARN of the secret of module.{address}.",
            f"module.{address}.secret_arn",
        ),
    )


MODULES: Final = (
    LocalModule("Network", "AwsVpc", "network", _network_arguments, _network_outputs),
    LocalModule(
        "SecretStore", "AwsSecrets", "secret-store", _secret_store_arguments, _secret_store_outputs
    ),
)
"""The local modules of this toolchain version, in the order of their calls."""


# trace: PRD-DSML-037
def realization(ir: Ir, element: Element, kind: str) -> Element:
    """Give the AWS realization of a logical element.

    The realization is the source of a `realizes` link to the element, with
    the AWS kind of the logical kind.
    """
    by_identity = {item.identity: item for item in ir.elements}
    found = sorted(
        (
            by_identity[link.source]
            for link in ir.links
            if link.type == "realizes"
            and link.target == element.identity
            and link.source in by_identity
            and by_identity[link.source].kind == kind
        ),
        key=Element.sort_key,
    )
    if len(found) != 1:
        raise ToolchainError(
            f'The element "{element.identity}" must have one AWS realization of the kind {kind}.'
        )
    return found[0]


# trace: PRD-IAC-023, PRD-DSML-042
def module_calls(ir: Ir, environment: Element, product: str) -> tuple[ModuleCall, ...]:
    """Give the module calls of one environment root module.

    The calls are in the order of `MODULES`, then sorted by element identity.
    """
    attributes = realization_attributes(ir, environment.identity)
    environment_name = safe_names.kebab_case(environment.name)
    calls: list[ModuleCall] = []
    for module in MODULES:
        elements = sorted(
            (element for element in ir.elements if element.kind == module.kind),
            key=Element.sort_key,
        )
        for element in elements:
            aws = realization(ir, element, module.realization_kind)
            arguments = module.arguments(
                element, attributes.get(aws.identity, {}), product, environment_name
            )
            address = names.hcl_address(element.name)
            calls.append(
                ModuleCall(
                    folder=module.folder,
                    element=element,
                    realization=aws,
                    arguments=tuple(sorted(arguments.items())),
                    outputs=module.outputs(address),
                )
            )
    _check_addresses(calls)
    return tuple(calls)


def _check_addresses(calls: list[ModuleCall]) -> None:
    """Make sure that two module calls do not have the same address."""
    seen: dict[str, str] = {}
    for call in calls:
        other = seen.setdefault(call.address, call.element.identity)
        if other != call.element.identity:
            raise ToolchainError(
                f'The elements "{other}" and "{call.element.identity}" have the same '
                f'HCL address "module.{call.address}". Give one element a different name.'
            )
