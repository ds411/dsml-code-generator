# trace: PRD-IAC-009, PRD-IAC-012, PRD-IAC-013, PRD-IAC-014, PRD-IAC-016, PRD-CORE-026
"""The values of the container services: the module `container-service` and its calls.

The functions of this module read only the IR (PRD-CORE-026). Each
`#ContainerService` element has one `#AwsEcsService` realization and one
allocated application. The realization gives `cpu`, `memory`,
`desiredCount`, `minCount` and `maxCount`. An override in an environment can
change each of them (PRD-DSML-042).

If the realization does not give a value, the generator uses these values:

- `cpu`: 256, and `memory`: 512 (the smallest Fargate size).
- `desiredCount`: 1.
- `minCount`: the value of `desiredCount`.
- `maxCount`: two times the value of `minCount`, and 1 or more.

The application name gives the root module variable
`<application>_image_digest` (PRD-IAC-009) and the API domain
`<application>.<environment domain>` (PRD-IAC-014).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from dsml.errors import ToolchainError
from dsml.generate import names as safe_names
from dsml.generate.infrastructure import names
from dsml.ir.environments import realization_attributes
from dsml.ir.model import Attribute, Element, EnumValue, IntegerValue, Ir, StringValue

MODULE: Final = "container-service"
"""The folder of the local module in `modules/`."""

MODULE_FILES: Final = ("main", "outputs", "variables")
"""The files of the local module, without `.gen.tf`."""

DEFAULT_CPU: Final = 256
DEFAULT_MEMORY: Final = 512
DEFAULT_DESIRED_COUNT: Final = 1

CPU_TARGET: Final = 70
"""The target value of the average CPU use of the service, in percent (PRD-IAC-013)."""

LOG_RETENTION_DAYS: Final = 30
"""The retention of the log group in days (PRD-IAC-016)."""

HEALTH_CHECK_PATH: Final = "/healthz"
"""The health check path of the target group (PRD-IAC-014, PRD-APP-012)."""

CONTAINER_NAME: Final = "app"
"""The name of the container in the two task definitions."""

TARGETS: Final[Mapping[str, tuple[int, tuple[str, ...]]]] = {
    "fastapi": (8000, ("python", "-m", "app.migrate_gen")),
}
"""The container port and the migration command of each target (PRD-APP-128, PRD-APP-133)."""


# trace: PRD-IAC-009, PRD-IAC-012, PRD-IAC-013, PRD-IAC-014, PRD-IAC-015, PRD-IAC-016
@dataclass(frozen=True, slots=True)
class ContainerService:
    """The values of one container service in one environment."""

    element: Element
    realization: Element
    application: Element
    network: str
    cpu: int
    memory: int
    desired_count: int
    min_count: int
    max_count: int
    port: int
    migration_command: tuple[str, ...]

    @property
    def address(self) -> str:
        """The HCL name of the module call, for example `api_service`."""
        return names.hcl_address(self.element.name)

    @property
    def image_variable(self) -> str:
        """The root module variable of the image digest, for example `order_api_image_digest`."""
        return f"{names.hcl_address(self.application.name)}_image_digest"

    @property
    def elements(self) -> tuple[str, ...]:
        """The identities of the model elements of the service, sorted."""
        return tuple(
            sorted({self.element.identity, self.realization.identity, self.application.identity})
        )


def _linked(
    ir: Ir, link_type: str, *, source: str | None = None, target: str | None = None
) -> list[str]:
    """Give the other ends of the links of one type from a source or to a target."""
    if source is not None:
        return sorted(
            link.target for link in ir.links if link.type == link_type and link.source == source
        )
    return sorted(
        link.source for link in ir.links if link.type == link_type and link.target == target
    )


def _one(ir: Ir, identities: list[str], kind: str, service: Element, what: str) -> Element:
    """Give the one element of a kind in a list of identities."""
    by_identity = {element.identity: element for element in ir.elements}
    found = [by_identity[identity] for identity in identities if identity in by_identity]
    found = [element for element in found if element.kind == kind]
    if len(found) != 1:
        raise ToolchainError(
            f'The container service "{service.identity}" must have exactly one {what}. '
            f"It has {len(found)}."
        )
    return found[0]


def _integer(attributes: Mapping[str, Attribute], name: str, default: int) -> int:
    """Give the integer value of an attribute, or the default value."""
    attribute = attributes.get(name)
    if attribute is None:
        return default
    if not isinstance(attribute.value, IntegerValue):
        raise ToolchainError(f'The attribute "{name}" must have an integer value.')
    return attribute.value.value


def _target(application: Element) -> str:
    """Give the target of an application, for example `fastapi`."""
    for attribute in application.attributes:
        if attribute.name == "target":
            if isinstance(attribute.value, EnumValue):
                return attribute.value.literal
            if isinstance(attribute.value, StringValue):
                return attribute.value.value
    raise ToolchainError(f'The application "{application.identity}" has no target.')


# trace: PRD-IAC-011, PRD-IAC-012
def network_address(ir: Ir) -> str:
    """Give the HCL name of the module call of the one network of the model."""
    networks = sorted(
        (element for element in ir.elements if element.kind == "Network"), key=Element.sort_key
    )
    if len(networks) != 1:
        raise ToolchainError(
            "A model with a container service must have exactly one network. "
            f"It has {len(networks)}."
        )
    return names.hcl_address(networks[0].name)


# trace: PRD-IAC-012, PRD-IAC-013, PRD-DSML-042
def container_services(ir: Ir, environment: str) -> tuple[ContainerService, ...]:
    """Give the container services of the IR in one environment, sorted by identity."""
    elements = sorted(
        (element for element in ir.elements if element.kind == "ContainerService"),
        key=Element.sort_key,
    )
    if not elements:
        return ()
    network = network_address(ir)
    attributes_of = realization_attributes(ir, environment)
    result: list[ContainerService] = []
    for element in elements:
        realization = _one(
            ir,
            _linked(ir, "realizes", target=element.identity),
            "AwsEcsService",
            element,
            "AWS realization",
        )
        application = _one(
            ir,
            _linked(ir, "allocate", target=element.identity),
            "Application",
            element,
            "allocated application",
        )
        target = _target(application)
        if target not in TARGETS:
            raise ToolchainError(
                f'The container service "{element.identity}" cannot run the target "{target}".'
            )
        port, command = TARGETS[target]
        attributes = attributes_of[realization.identity]
        desired = _integer(attributes, "desiredCount", DEFAULT_DESIRED_COUNT)
        minimum = _integer(attributes, "minCount", desired)
        maximum = _integer(attributes, "maxCount", max(2 * minimum, 1))
        if not minimum <= desired <= maximum:
            raise ToolchainError(
                f'The container service "{element.identity}" must have '
                f'minCount <= desiredCount <= maxCount in the environment "{environment}".'
            )
        result.append(
            ContainerService(
                element=element,
                realization=realization,
                application=application,
                network=network,
                cpu=_integer(attributes, "cpu", DEFAULT_CPU),
                memory=_integer(attributes, "memory", DEFAULT_MEMORY),
                desired_count=desired,
                min_count=minimum,
                max_count=maximum,
                port=port,
                migration_command=command,
            )
        )
    return tuple(result)


# trace: PRD-IAC-008, PRD-IAC-014, PRD-IAC-015, PRD-IAC-035, PRD-IAC-037
def module_call(
    service: ContainerService, product: str, environment: str, domain: str, tooling: Element
) -> dict[str, Any]:
    """Give the template data of the module call of one container service."""
    element = safe_names.kebab_case(service.element.name)
    application = safe_names.kebab_case(service.application.name)

    def aws(suffix: str, resource_type: str) -> str:
        part = element if not suffix else f"{element}-{suffix}"
        return names.aws_name(product, environment, part, resource_type)

    tooling_account = _tooling_value(tooling, "accountId")
    tooling_region = _tooling_value(tooling, "region")
    return {
        "address": service.address,
        "network": service.network,
        "image_variable": service.image_variable,
        "element_tag": names.tag_value(service.element.identity),
        "application_tag": names.tag_value(service.application.identity),
        "names": {
            "alb": aws("", "alb"),
            "alb_security_group": aws("alb", "security_group"),
            "cluster": aws("", "ecs_cluster"),
            "execution_role": names.task_execution_role(product, environment, service.element.name),
            "log_group": aws("", "cloudwatch_log_group"),
            "migration_family": aws("migrate", "ecs_task_definition"),
            "service": aws("", "ecs_service"),
            "service_security_group": aws("service", "security_group"),
            "target_group": aws("", "target_group"),
            "task_family": aws("", "ecs_task_definition"),
            "task_role": names.task_role(product, environment, service.element.name),
        },
        "domain_name": f"{application}.{domain}",
        "zone_name": domain,
        "cpu": service.cpu,
        "memory": service.memory,
        "desired_count": service.desired_count,
        "min_count": service.min_count,
        "max_count": service.max_count,
        "container_port": service.port,
        "migration_command": list(service.migration_command),
        "ecr_account_id": tooling_account,
        "ecr_region": tooling_region,
        "ecr_repository": names.ecr_repository(product, service.application.name),
    }


def _tooling_value(tooling: Element, name: str) -> str:
    """Give the text value of an attribute of the tooling account."""
    for attribute in tooling.attributes:
        if attribute.name == name and isinstance(attribute.value, StringValue):
            return attribute.value.value
    raise ToolchainError(
        f'The tooling account "{tooling.identity}" has no text value for the attribute "{name}".'
    )


# trace: PRD-IAC-022, PRD-DSML-043
def tooling_account(ir: Ir) -> Element:
    """Give the one tooling account of the model."""
    found = [element for element in ir.elements if element.kind == "ToolingAccount"]
    if len(found) != 1:
        raise ToolchainError(
            f"A model with a container service must have exactly one tooling account. "
            f"It has {len(found)}."
        )
    return found[0]
