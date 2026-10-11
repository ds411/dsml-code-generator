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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate import names as safe_names
from dsml.generate.infrastructure import hcl, names
from dsml.ir.environments import realization_attributes
from dsml.ir.model import (
    Attribute,
    BooleanValue,
    Element,
    EnumValue,
    IntegerValue,
    Ir,
    LinkType,
    ListValue,
    StringValue,
)
from dsml.versions import load_baseline

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


# trace: PRD-IAC-009
@dataclass(frozen=True, slots=True)
class RootVariable:
    """A variable of an environment root module that a module call uses.

    The pipeline gives its value. The value must agree with `pattern`.
    """

    name: str
    description: str
    pattern: str
    error_message: str


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
    variables: tuple[RootVariable, ...] = ()

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
        """Give the argument lines of the call, aligned in the format of `tofu fmt`.

        `tofu fmt` aligns the "=" of each run of one-line arguments. An
        argument with a value of more than one line is not aligned, and it
        ends the run. The value of such an argument gives its next lines with
        their indent relative to the argument.
        """
        result: list[str] = []
        run: list[tuple[str, str]] = []

        def close_run() -> None:
            width = max((len(name) for name, _ in run), default=0)
            result.extend(f"{name.ljust(width)} = {value}" for name, value in run)
            run.clear()

        for name, value in self.arguments:
            if "\n" in value:
                close_run()
                result.extend(f"{name} = {value}".split("\n"))
            else:
                run.append((name, value))
        close_run()
        return tuple(result)


# trace: PRD-IAC-023, PRD-CORE-026
@dataclass(frozen=True, slots=True)
class CallContext:
    """The values of one environment root module that the arguments of a call can use."""

    ir: Ir
    environment: Element
    """The environment element."""
    product: str
    """The product name in kebab case."""

    @property
    def environment_name(self) -> str:
        """Give the name of the environment in kebab case, for example `dev`."""
        return safe_names.kebab_case(self.environment.name)


type Arguments = Callable[[Element, Mapping[str, Attribute], CallContext], dict[str, str]]
"""Give the arguments of a call from the element, the attributes of its
realization in the environment, and the values of the root module."""

type TemplateData = Callable[[], Mapping[str, object]]
"""Give the template data of the files of a module, in addition to the header data."""


def no_template_data() -> Mapping[str, object]:
    """Give no template data."""
    return {}


type Outputs = Callable[[str], tuple[RootOutput, ...]]
"""Give the root module outputs of a call from the address of the call."""

type Variables = Callable[[Element, CallContext], tuple[RootVariable, ...]]
"""Give the root module variables of a call from the element and the values of the root module."""


def no_variables(element: Element, context: CallContext) -> tuple[RootVariable, ...]:
    """Give no root module variable."""
    return ()


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
    template_data: TemplateData = no_template_data
    variables: Variables = no_variables


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
    element: Element, attributes: Mapping[str, Attribute], context: CallContext
) -> dict[str, str]:
    product, environment = context.product, context.environment_name
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
    element: Element, attributes: Mapping[str, Attribute], context: CallContext
) -> dict[str, str]:
    product, environment = context.product, context.environment_name
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


PROD: Final = "prod"
"""The name of the environment with deletion protection of the databases (PRD-IAC-017)."""

MASTER_USERNAME: Final = "dsml_admin"
"""The name of the master user of each database."""

CALLBACK_PATH: Final = "/auth/callback"
"""The path of the callback URL of each app client (PRD-IAC-019)."""

LOGOUT_PATH: Final = "/"
"""The path of the logout URL of each app client (PRD-IAC-019)."""


def _element(ir: Ir, identity: str) -> Element:
    """Give the element with an identity."""
    for item in ir.elements:
        if item.identity == identity:
            return item
    raise ToolchainError(f'The IR has no element "{identity}".')


def _sources(ir: Ir, link_type: LinkType, target: str) -> tuple[Element, ...]:
    """Give the sources of the links of one type to a target, sorted by identity."""
    identities = {
        link.source for link in ir.links if link.type == link_type and link.target == target
    }
    return tuple(sorted((_element(ir, item) for item in identities), key=Element.sort_key))


def _the_network(ir: Ir) -> str:
    """Give the address of the call of the one network of the model."""
    found = [item for item in ir.elements if item.kind == "Network"]
    if len(found) != 1:
        raise ToolchainError(f"The model must have one #Network element, not {len(found)}.")
    return f"module.{names.hcl_address(found[0].name)}"


def hcl_map(entries: Sequence[tuple[str, str]]) -> str:
    """Give an HCL map in the format of `tofu fmt`, with the indent of an argument value.

    Each entry is a key and its HCL value. A value of more than one line has
    its next lines with their indent relative to the key. A map with no entry
    gives `{}`.
    """
    if not entries:
        return "{}"
    lines = ["{"]
    run: list[tuple[str, str]] = []

    def close_run() -> None:
        width = max((len(key) for key, _ in run), default=0)
        lines.extend(f"  {key.ljust(width)} = {value}" for key, value in run)
        run.clear()

    for key, value in entries:
        if "\n" in value:
            close_run()
            lines.extend(f"  {line}" for line in f"{key} = {value}".split("\n"))
        else:
            run.append((key, value))
    close_run()
    lines.append("}")
    return "\n".join(lines)


def _text(attributes: Mapping[str, Attribute], element: Element, name: str) -> str:
    attribute = attributes.get(name)
    if attribute is None or not isinstance(attribute.value, StringValue):
        raise ToolchainError(f'The realization of "{element.identity}" has no text "{name}".')
    return attribute.value.value


def _boolean(attributes: Mapping[str, Attribute], element: Element, name: str) -> bool:
    attribute = attributes.get(name)
    if attribute is None or not isinstance(attribute.value, BooleanValue):
        raise ToolchainError(f'The realization of "{element.identity}" has no Boolean "{name}".')
    return attribute.value.value


def _hcl_bool(value: bool) -> str:
    return "true" if value else "false"


# trace: PRD-IAC-008, PRD-IAC-017, PRD-IAC-018, PRD-IAC-031, PRD-IAC-035
def _database_arguments(
    element: Element, attributes: Mapping[str, Attribute], context: CallContext
) -> dict[str, str]:
    """Give the arguments of a database call.

    The security group of the database permits port 5432 only from the
    security group of each container service with a `#Uses` link to the
    database (PRD-IAC-018).
    """
    product, environment = context.product, context.environment_name
    network = _the_network(context.ir)
    services = [
        (names.hcl_address(item.name), f"module.{names.hcl_address(item.name)}.security_group_id")
        for item in _sources(context.ir, "uses", element.identity)
        if item.kind == "ContainerService"
    ]
    return {
        "database_name": hcl.string(names.hcl_address(element.name)),
        "deletion_protection": _hcl_bool(environment == PROD),
        "element": hcl.string(names.tag_value(element.identity)),
        "instance_class": hcl.string(_text(attributes, element, "instanceClass")),
        "master_username": hcl.string(MASTER_USERNAME),
        "multi_az": _hcl_bool(_boolean(attributes, element, "multiAz")),
        "name": hcl.string(names.aws_name(product, environment, element.name, "db_instance")),
        "source_security_group_ids": hcl_map(sorted(services)),
        "subnet_ids": f"{network}.private_subnet_ids",
        "vpc_id": f"{network}.vpc_id",
    }


def _database_outputs(address: str) -> tuple[RootOutput, ...]:
    return ()


# trace: PRD-IAC-017
def _database_template_data() -> Mapping[str, str]:
    """Give the PostgreSQL release line of the version baseline."""
    pin = load_baseline().get("postgresql")
    if pin is None or pin.line is None:
        raise ToolchainError('The version baseline has no release line for "postgresql".')
    return {"engine_version": pin.line}


# trace: PRD-DSML-033, PRD-IAC-019
def role_values(ir: Ir) -> tuple[str, ...]:
    """Give the sorted values of the `#Roles` enumerations of the model."""
    values: set[str] = set()
    for roles in (item for item in ir.elements if item.kind == "Roles"):
        for attribute in roles.attributes:
            if attribute.name == "literals" and isinstance(attribute.value, ListValue):
                values.update(
                    item.literal for item in attribute.value.items if isinstance(item, EnumValue)
                )
    return tuple(sorted(values))


# trace: PRD-IAC-019
def directory_applications(ir: Ir, directory: Element) -> tuple[Element, ...]:
    """Give the applications that use a user directory, sorted by identity.

    An application uses the user directory if it has a `#Uses` link to it,
    or if it is allocated to a container service with a `#Uses` link to it.
    """
    found: dict[str, Element] = {}
    for user in _sources(ir, "uses", directory.identity):
        if user.kind == "Application":
            found[user.identity] = user
        elif user.kind == "ContainerService":
            for item in _sources(ir, "allocate", user.identity):
                if item.kind == "Application":
                    found[item.identity] = item
    return tuple(sorted(found.values(), key=Element.sort_key))


def _environment_domain(environment: Element) -> str:
    for attribute in environment.attributes:
        if attribute.name == "domain" and isinstance(attribute.value, StringValue):
            return attribute.value.value
    raise ToolchainError(
        f'The environment "{environment.identity}" has no text value for the attribute "domain".'
    )


# trace: PRD-IAC-008, PRD-IAC-019, PRD-IAC-035
def _user_directory_arguments(
    element: Element, attributes: Mapping[str, Attribute], context: CallContext
) -> dict[str, str]:
    """Give the arguments of a user directory call.

    The user pool gets one group for each role value, and one app client for
    each application that uses it. The callback URLs are on the domain of
    the environment (PRD-IAC-019).
    """
    product, environment = context.product, context.environment_name
    domain = _environment_domain(context.environment)
    clients = [
        (
            names.hcl_address(application.name),
            hcl_map(
                [
                    (
                        "name",
                        hcl.string(
                            names.aws_name(
                                product, environment, application.name, "cognito_app_client"
                            )
                        ),
                    ),
                    ("callback_urls", f"[{hcl.string(f'https://{domain}{CALLBACK_PATH}')}]"),
                    ("logout_urls", f"[{hcl.string(f'https://{domain}{LOGOUT_PATH}')}]"),
                ]
            ),
        )
        for application in directory_applications(context.ir, element)
    ]
    groups = ", ".join(hcl.string(value) for value in role_values(context.ir))
    return {
        "clients": hcl_map(clients),
        "domain_prefix": hcl.string(
            names.aws_name(product, environment, element.name, "cognito_domain")
        ),
        "element": hcl.string(names.tag_value(element.identity)),
        "groups": f"[{groups}]",
        "name": hcl.string(names.aws_name(product, environment, element.name, "cognito_user_pool")),
    }


# trace: PRD-IAC-010
def _user_directory_outputs(address: str) -> tuple[RootOutput, ...]:
    return (
        RootOutput(
            f"{address}_app_client_ids",
            f"The ID of the app client of each application of module.{address}, by HCL name.",
            f"module.{address}.app_client_ids",
        ),
        RootOutput(
            f"{address}_login_domain",
            f"The managed login domain of module.{address}.",
            f"module.{address}.login_domain",
        ),
        RootOutput(
            f"{address}_user_pool_id",
            f"The ID of the user pool of module.{address}.",
            f"module.{address}.user_pool_id",
        ),
    )


# The container service (PRD-IAC-009, PRD-IAC-012 to PRD-IAC-016). If the
# realization does not give a value, the call uses these values: cpu 256,
# memory 512 (the smallest Fargate size), desiredCount 1, minCount the value
# of desiredCount, and maxCount two times minCount (1 or more).

DEFAULT_CPU: Final = 256
DEFAULT_MEMORY: Final = 512
DEFAULT_DESIRED_COUNT: Final = 1

CPU_TARGET: Final = 70
"""The target value of the average CPU use of a service, in percent (PRD-IAC-013)."""

LOG_RETENTION_DAYS: Final = 30
"""The retention of the log group of a service in days (PRD-IAC-016)."""

HEALTH_CHECK_PATH: Final = "/healthz"
"""The health check path of the target group (PRD-IAC-014, PRD-APP-012)."""

CONTAINER_NAME: Final = "app"
"""The name of the container in the two task definitions of a service."""

TARGETS: Final[Mapping[str, tuple[int, tuple[str, ...]]]] = {
    "fastapi": (8000, ("python", "-m", "app.migrate_gen")),
}
"""The container port and the migration command of each target (PRD-APP-128, PRD-APP-133)."""

DATABASE_SSL_MODE: Final = "require"
"""The PostgreSQL SSL mode of the application. RDS for PostgreSQL requires SSL."""

SERVICE_OUTPUTS: Final = (
    ("api_url", "The API URL"),
    ("cluster_name", "The name of the ECS cluster"),
    ("migration_task_definition", "The family of the migration task definition"),
    ("private_subnet_ids", "The IDs of the subnets of the tasks"),
    ("security_group_id", "The ID of the security group of the tasks"),
    ("service_name", "The name of the ECS service"),
)
"""The root module outputs of each container service, without the prefix `<address>_`."""

IMAGE_DIGEST_PATTERN: Final = "^sha256:[0-9a-f]{64}$"
"""The pattern of an image digest."""


def _one(items: Sequence[Element], element: Element, what: str) -> Element:
    """Give the one item of a list, or an error that names the element."""
    if len(items) != 1:
        raise ToolchainError(
            f'The container service "{element.identity}" must have one {what}, not {len(items)}.'
        )
    return items[0]


# trace: PRD-IAC-009, PRD-IAC-012
def service_application(ir: Ir, element: Element) -> Element:
    """Give the one application that is allocated to a container service."""
    applications = [
        item for item in _sources(ir, "allocate", element.identity) if item.kind == "Application"
    ]
    return _one(applications, element, "allocated application")


def _target(application: Element) -> str:
    """Give the target of an application, for example `fastapi`."""
    for attribute in application.attributes:
        if attribute.name == "target" and isinstance(attribute.value, EnumValue):
            return attribute.value.literal
    raise ToolchainError(f'The application "{application.identity}" has no target.')


def _tooling_account(ir: Ir) -> tuple[str, str]:
    """Give the account ID and the Region of the one tooling account of the model."""
    found = [item for item in ir.elements if item.kind == "ToolingAccount"]
    if len(found) != 1:
        raise ToolchainError(f"The model must have one #ToolingAccount element, not {len(found)}.")
    values = {
        attribute.name: attribute.value.value
        for attribute in found[0].attributes
        if isinstance(attribute.value, StringValue)
    }
    if "accountId" not in values or "region" not in values:
        raise ToolchainError(
            f'The tooling account "{found[0].identity}" must have an accountId and a region.'
        )
    return values["accountId"], values["region"]


def _used(ir: Ir, element: Element, kind: str) -> list[Element]:
    """Give the elements of a kind that a container service uses (`#Uses`), sorted."""
    by_identity = {item.identity: item for item in ir.elements}
    targets = sorted(
        {
            link.target
            for link in ir.links
            if link.type == "uses" and link.source == element.identity
        }
    )
    return [by_identity[item] for item in targets if by_identity[item].kind == kind]


# trace: PRD-IAC-012, PRD-IAC-013, PRD-DSML-042
def service_counts(element: Element, attributes: Mapping[str, Attribute]) -> tuple[int, int, int]:
    """Give the desired count, the minimum count and the maximum count of a service."""
    desired = _integer(attributes, "desiredCount", DEFAULT_DESIRED_COUNT)
    minimum = _integer(attributes, "minCount", desired)
    maximum = _integer(attributes, "maxCount", max(2 * minimum, 1))
    if not minimum <= desired <= maximum:
        raise ToolchainError(
            f'The container service "{element.identity}" must have '
            "minCount <= desiredCount <= maxCount."
        )
    return desired, minimum, maximum


# trace: PRD-IAC-015
def _service_environment(
    ir: Ir, element: Element, application: Element
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[str], list[str]]:
    """Give the environment variables, the secrets, the secret ARNs and the KMS key ARNs.

    The values come from the elements that the service uses (`#Uses`): one
    database, one user directory and each secret store. The secrets give
    the `valueFrom` of each secret environment variable.
    """
    variables: list[tuple[str, str]] = [("AWS_REGION", "local.aws_region")]
    secrets: list[tuple[str, str]] = []
    secret_arns: list[str] = []
    key_arns: list[str] = []
    databases = _used(ir, element, "RelationalDatabase")
    if databases:
        database = f"module.{names.hcl_address(_one(databases, element, 'database').name)}"
        secret = f"{database}.master_user_secret_arn"
        variables += [
            ("DATABASE_HOST", f"{database}.address"),
            ("DATABASE_NAME", f"{database}.database_name"),
            ("DATABASE_PORT", f"tostring({database}.port)"),
            ("DATABASE_SSL_MODE", hcl.string(DATABASE_SSL_MODE)),
        ]
        secrets += [
            ("DATABASE_PASSWORD", f'"${{{secret}}}:password::"'),
            ("DATABASE_USER", f'"${{{secret}}}:username::"'),
        ]
        secret_arns.append(secret)
        key_arns.append(f"{database}.kms_key_arn")
    directories = _used(ir, element, "UserDirectory")
    if directories:
        directory = f"module.{names.hcl_address(_one(directories, element, 'user directory').name)}"
        client = hcl.string(names.hcl_address(application.name))
        variables += [
            ("COGNITO_APP_CLIENT_ID", f"{directory}.app_client_ids[{client}]"),
            ("COGNITO_USER_POOL_ID", f"{directory}.user_pool_id"),
        ]
    for store in _used(ir, element, "SecretStore"):
        call = f"module.{names.hcl_address(store.name)}"
        secrets.append((names.hcl_address(store.name).upper(), f"{call}.secret_arn"))
        secret_arns.append(f"{call}.secret_arn")
        key_arns.append(f"{call}.key_arn")
    return sorted(variables), sorted(secrets), sorted(secret_arns), sorted(key_arns)


def _hcl_list(values: Sequence[str]) -> str:
    return f"[{', '.join(values)}]"


# trace: PRD-IAC-008, PRD-IAC-009, PRD-IAC-012, PRD-IAC-013, PRD-IAC-014, PRD-IAC-015,
# PRD-IAC-016, PRD-IAC-035, PRD-IAC-037
def _container_service_arguments(
    element: Element, attributes: Mapping[str, Attribute], context: CallContext
) -> dict[str, str]:
    """Give the arguments of a container service call.

    The API domain is `<application>.<environment domain>`. The public
    Route 53 hosted zone of the environment domain must exist (PRD-IAC-014).
    """
    product, environment = context.product, context.environment_name
    network = _the_network(context.ir)
    application = service_application(context.ir, element)
    target = _target(application)
    if target not in TARGETS:
        raise ToolchainError(
            f'The container service "{element.identity}" cannot run the target "{target}".'
        )
    port, command = TARGETS[target]
    desired, minimum, maximum = service_counts(element, attributes)
    domain = _environment_domain(context.environment)
    account, region = _tooling_account(context.ir)
    kebab = safe_names.kebab_case(element.name)

    def aws(suffix: str, resource_type: str) -> str:
        part = kebab if not suffix else f"{kebab}-{suffix}"
        return hcl.string(names.aws_name(product, environment, part, resource_type))

    aws_names = [
        ("alb", aws("", "alb")),
        ("alb_security_group", aws("alb", "security_group")),
        ("cluster", aws("", "ecs_cluster")),
        (
            "execution_role",
            hcl.string(names.task_execution_role(product, environment, element.name)),
        ),
        ("log_group", aws("", "cloudwatch_log_group")),
        ("migration_family", aws("migrate", "ecs_task_definition")),
        ("service", aws("", "ecs_service")),
        ("service_security_group", aws("service", "security_group")),
        ("target_group", aws("", "target_group")),
        ("task_family", aws("", "ecs_task_definition")),
        ("task_role", hcl.string(names.task_role(product, environment, element.name))),
    ]
    variables, secrets, secret_arns, key_arns = _service_environment(
        context.ir, element, application
    )
    return {
        "application": hcl.string(names.tag_value(application.identity)),
        "container_port": str(port),
        "cpu": str(_integer(attributes, "cpu", DEFAULT_CPU)),
        "desired_count": str(desired),
        "domain_name": hcl.string(f"{safe_names.kebab_case(application.name)}.{domain}"),
        "ecr_account_id": hcl.string(account),
        "ecr_region": hcl.string(region),
        "ecr_repository": hcl.string(names.ecr_repository(product, application.name)),
        "element": hcl.string(names.tag_value(element.identity)),
        "environment_variables": hcl_map(variables),
        "image_digest": f"var.{image_variable(application)}",
        "kms_key_arns": _hcl_list(key_arns),
        "max_count": str(maximum),
        "memory": str(_integer(attributes, "memory", DEFAULT_MEMORY)),
        "migration_command": _hcl_list([hcl.string(part) for part in command]),
        "min_count": str(minimum),
        "names": hcl_map(aws_names),
        "private_subnet_ids": f"{network}.private_subnet_ids",
        "public_subnet_ids": f"{network}.public_subnet_ids",
        "secret_arns": _hcl_list(secret_arns),
        "secrets": hcl_map(secrets),
        "vpc_id": f"{network}.vpc_id",
        "zone_name": hcl.string(domain),
    }


# trace: PRD-IAC-010
def _container_service_outputs(address: str) -> tuple[RootOutput, ...]:
    return tuple(
        RootOutput(
            f"{address}_{name}",
            f"{description} of module.{address}.",
            f"module.{address}.{name}",
        )
        for name, description in SERVICE_OUTPUTS
    )


# trace: PRD-IAC-014, PRD-IAC-016, PRD-IAC-034
def _container_service_template_data() -> Mapping[str, object]:
    """Give the fixed values of the module and the TLS policy of the version baseline."""
    pin = load_baseline().get("alb-tls-policy")
    if pin is None or pin.value is None:
        raise ToolchainError('The version baseline has no value for "alb-tls-policy".')
    return {
        "container_name": CONTAINER_NAME,
        "cpu_target": CPU_TARGET,
        "health_check_path": HEALTH_CHECK_PATH,
        "log_retention_days": LOG_RETENTION_DAYS,
        "tls_policy": pin.value,
    }


# trace: PRD-IAC-009
def image_variable(application: Element) -> str:
    """Give the name of the root module variable of the image digest of an application."""
    return f"{names.hcl_address(application.name)}_image_digest"


# trace: PRD-IAC-009
def _container_service_variables(
    element: Element, context: CallContext
) -> tuple[RootVariable, ...]:
    application = service_application(context.ir, element)
    name = image_variable(application)
    return (
        RootVariable(
            name=name,
            description=(
                f"The digest of the image of the application {application.identity}. "
                "The pipeline gives it (PRD-IAC-009)."
            ),
            pattern=IMAGE_DIGEST_PATTERN,
            error_message=(
                f"The variable {name} must be an image digest: "
                "sha256: and 64 lowercase hexadecimal characters."
            ),
        ),
    )


MODULES: Final = (
    LocalModule("Network", "AwsVpc", "network", _network_arguments, _network_outputs),
    LocalModule(
        "SecretStore", "AwsSecrets", "secret-store", _secret_store_arguments, _secret_store_outputs
    ),
    LocalModule(
        "RelationalDatabase",
        "AwsRdsPostgres",
        "relational-database",
        _database_arguments,
        _database_outputs,
        _database_template_data,
    ),
    LocalModule(
        "UserDirectory",
        "AwsCognito",
        "user-directory",
        _user_directory_arguments,
        _user_directory_outputs,
    ),
    LocalModule(
        "ContainerService",
        "AwsEcsService",
        "container-service",
        _container_service_arguments,
        _container_service_outputs,
        _container_service_template_data,
        _container_service_variables,
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
    context = CallContext(ir, environment, product)
    calls: list[ModuleCall] = []
    for module in MODULES:
        elements = sorted(
            (element for element in ir.elements if element.kind == module.kind),
            key=Element.sort_key,
        )
        for element in elements:
            aws = realization(ir, element, module.realization_kind)
            arguments = module.arguments(element, attributes.get(aws.identity, {}), context)
            address = names.hcl_address(element.name)
            calls.append(
                ModuleCall(
                    folder=module.folder,
                    element=element,
                    realization=aws,
                    arguments=tuple(sorted(arguments.items())),
                    outputs=module.outputs(address),
                    variables=module.variables(element, context),
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
