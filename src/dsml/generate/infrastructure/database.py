# trace: PRD-IAC-017, PRD-IAC-018, PRD-IAC-030, PRD-IAC-031, PRD-CORE-026
"""The calls of the local module `relational-database` in an environment root module.

Each `#RelationalDatabase` element gets one module call. The realization
`#AwsRdsPostgres` and the overrides of the environment give the
`instanceClass` and `multiAz` (PRD-IAC-017). Deletion protection is on only
in prod. The security group of the database permits port 5432 only from the
security groups of the container services that use it (PRD-IAC-018).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate import names as safe_names
from dsml.generate.infrastructure import elements, names
from dsml.ir.environments import realization_attributes
from dsml.ir.model import Attribute, BooleanValue, Element, Ir, StringValue

KIND: Final = "RelationalDatabase"
"""The element kind of the logical databases."""

MODULE: Final = "relational-database"
"""The folder of the local module."""

PROD: Final = "prod"
"""The name of the environment with deletion protection."""

MASTER_USERNAME: Final = "dsml_admin"
"""The name of the master user of each database."""


# trace: PRD-IAC-017, PRD-IAC-018
@dataclass(frozen=True, slots=True)
class DatabaseCall:
    """The values of one call of the module `relational-database`."""

    address: str
    elements: tuple[str, ...]
    name: str
    element: str
    instance_class: str
    multi_az: bool
    deletion_protection: bool
    database_name: str
    master_username: str
    network: str
    services: tuple[tuple[str, str], ...]
    """The HCL name of each container service that uses the database, with
    spaces after it to align the values, and the module address of the
    service."""


def _attribute(attributes: Mapping[str, Attribute], realization: str, name: str) -> Attribute:
    try:
        return attributes[name]
    except KeyError:
        raise ToolchainError(
            f'The realization "{realization}" has no attribute "{name}".'
        ) from None


def _instance_class(attributes: Mapping[str, Attribute], realization: str) -> str:
    value = _attribute(attributes, realization, "instanceClass").value
    if not isinstance(value, StringValue):
        raise ToolchainError(f'The attribute "instanceClass" of "{realization}" must be a text.')
    return value.value


def _multi_az(attributes: Mapping[str, Attribute], realization: str) -> bool:
    value = _attribute(attributes, realization, "multiAz").value
    if not isinstance(value, BooleanValue):
        raise ToolchainError(f'The attribute "multiAz" of "{realization}" must be a Boolean.')
    return value.value


def _services(ir: Ir, database: Element) -> tuple[tuple[str, str], ...]:
    """Give the container services that use a database, aligned for `tofu fmt`."""
    keys = sorted(
        names.hcl_address(elements.element(ir, identity).name)
        for identity in elements.sources(ir, "uses", database.identity)
        if elements.element(ir, identity).kind == "ContainerService"
    )
    width = max((len(key) for key in keys), default=0)
    return tuple((key.ljust(width), f"module.{key}") for key in keys)


# trace: PRD-IAC-008, PRD-IAC-017, PRD-IAC-018, PRD-IAC-023
def database_calls(ir: Ir, product: str, environment: Element) -> tuple[DatabaseCall, ...]:
    """Give the module call of each database in one environment, sorted by identity."""
    databases = elements.elements_of_kind(ir, KIND)
    if not databases:
        return ()
    environment_name = safe_names.kebab_case(environment.name)
    attributes_by_realization = realization_attributes(ir, environment.identity)
    network = names.hcl_address(elements.network(ir).name)
    calls: list[DatabaseCall] = []
    for database in databases:
        realization = elements.realization(ir, database)
        attributes = attributes_by_realization.get(realization.identity, {})
        calls.append(
            DatabaseCall(
                address=names.hcl_address(database.name),
                elements=(
                    database.identity,
                    realization.identity,
                    *elements.overrides(ir, environment.identity, realization.identity),
                ),
                name=names.aws_name(product, environment_name, database.name, "db_instance"),
                element=names.tag_value(database.identity),
                instance_class=_instance_class(attributes, realization.identity),
                multi_az=_multi_az(attributes, realization.identity),
                deletion_protection=environment_name == PROD,
                database_name=names.hcl_address(database.name),
                master_username=MASTER_USERNAME,
                network=f"module.{network}",
                services=_services(ir, database),
            )
        )
    return tuple(calls)


def module_elements(ir: Ir) -> tuple[str, ...]:
    """Give the sorted identities of the databases and their realizations."""
    found: set[str] = set()
    for database in elements.elements_of_kind(ir, KIND):
        found.update((database.identity, elements.realization(ir, database).identity))
    return tuple(sorted(found))
