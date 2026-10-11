# trace: PRD-VAL-015, PRD-DSML-041, PRD-DSML-042, PRD-DSML-043
"""The rules of the category AWS.

The rules read the AWS accounts and Regions of the environments and of the
tooling account, and the values of the AWS realizations in each environment.
An override in an environment replaces the default value of a realization
(`dsml.ir.environments`). The rules do not use the network or an AWS account
(PRD-TOP-004).
"""

import re
from collections.abc import Iterator, Mapping
from typing import Final

from dsml.config import Configuration
from dsml.ir.environments import environments, realization_attributes
from dsml.ir.model import Attribute, BooleanValue, Element, IntegerValue, Ir, StringValue
from dsml.validate.rule import Hit, Rule, implements

# trace: PRD-VAL-015
AWS_001 = Rule(
    id="AWS-001",
    severity="error",
    message=(
        "An account ID does not have 12 digits, two environments use one account, "
        "or an environment uses the tooling account."
    ),
    fix_hint="Give each environment its own AWS account. The ID of an account has 12 digits.",
)

# trace: PRD-VAL-015, PRD-CORE-013
AWS_002 = Rule(
    id="AWS-002",
    severity="error",
    message="A Region is not on the list of permitted Regions in the configuration file.",
    fix_hint="Use a Region from the key aws.regions, or add the Region to aws.regions.",
)

# trace: PRD-VAL-015, PRD-IAC-012
AWS_003 = Rule(
    id="AWS-003",
    severity="error",
    message="The cpu and memory of a Fargate service are not a valid pair.",
    fix_hint="Use a pair of cpu and memory that AWS Fargate accepts.",
)

# trace: PRD-VAL-015, PRD-IAC-017
AWS_004 = Rule(
    id="AWS-004",
    severity="warning",
    message="The prod database has multiAz = false.",
    fix_hint="Set multiAz = true for the database in the environment prod.",
)

# trace: PRD-VAL-015, PRD-IAC-013
AWS_005 = Rule(
    id="AWS-005",
    severity="warning",
    message="A prod container service has minCount less than 2.",
    fix_hint="Set minCount to 2 or more for the service in the environment prod.",
)

ACCOUNT_ID: Final = re.compile(r"[0-9]{12}")
"""The form of an AWS account ID."""

PROD: Final = "prod"
"""The name of the prod environment (PRD-DSML-041)."""


def _memory(start: int, stop: int, step: int) -> frozenset[int]:
    return frozenset(range(start, stop + 1, step))


# trace: PRD-VAL-015, PRD-IAC-012
FARGATE_PAIRS: Final[Mapping[int, frozenset[int]]] = {
    256: frozenset({512, 1024, 2048}),
    512: _memory(1024, 4096, 1024),
    1024: _memory(2048, 8192, 1024),
    2048: _memory(4096, 16384, 1024),
    4096: _memory(8192, 30720, 1024),
    8192: _memory(16384, 61440, 4096),
    16384: _memory(32768, 122880, 8192),
}
"""The valid pairs of a Fargate task: the memory values (MiB) for each cpu value (CPU units).

The table comes from the AWS documentation of the Fargate task size. The rule
does not read it from AWS, because the rules do not use the network.
"""


def _text(element: Element, name: str) -> Attribute | None:
    """Give the attribute `name` of an element if it has a text value."""
    for attribute in element.attributes:
        if attribute.name == name and isinstance(attribute.value, StringValue):
            return attribute
    return None


def _value(attribute: Attribute) -> str:
    assert isinstance(attribute.value, StringValue)
    return attribute.value.value


def _accounts(ir: Ir) -> tuple[Element, ...]:
    """Give the environments and the tooling accounts, sorted by identity."""
    return tuple(
        sorted(
            (e for e in ir.elements if e.kind in ("Environment", "ToolingAccount")),
            key=Element.sort_key,
        )
    )


def _kind_name(element: Element) -> str:
    return "environment" if element.kind == "Environment" else "tooling account"


# trace: PRD-VAL-015, PRD-DSML-041, PRD-DSML-043
@implements(AWS_001)
def aws_001(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    tooling: dict[str, str] = {}
    used: dict[str, list[Element]] = {}
    for element in _accounts(ir):
        attribute = _text(element, "accountId")
        if attribute is None:
            continue
        account = _value(attribute)
        if not ACCOUNT_ID.fullmatch(account):
            yield Hit(
                f'The account ID "{account}" of the {_kind_name(element)} {element.name} '
                "does not have 12 digits.",
                attribute.location or element.location,
                element.identity,
            )
        elif element.kind == "ToolingAccount":
            tooling.setdefault(account, element.name)
        else:
            used.setdefault(account, []).append(element)
    for account, group in sorted(used.items()):
        for element in group:
            attribute = _text(element, "accountId")
            location = element.location if attribute is None else attribute.location
            others = [other.name for other in group if other is not element]
            if others:
                also = (
                    f"The environment {others[0]} also uses"
                    if len(others) == 1
                    else f"The environments {', '.join(others[:-1])} and {others[-1]} also use"
                )
                yield Hit(
                    f"The environment {element.name} uses the account {account}. "
                    f"{also} this account.",
                    location or element.location,
                    element.identity,
                )
            if account in tooling:
                yield Hit(
                    f"The environment {element.name} uses the account {account} "
                    f"of the tooling account {tooling[account]}.",
                    location or element.location,
                    element.identity,
                )


# trace: PRD-VAL-015, PRD-CORE-013, PRD-DSML-041, PRD-DSML-043
@implements(AWS_002)
def aws_002(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    """Find the Regions that are not in `aws.regions`.

    If the configuration has no permitted Region, the rule gives no finding
    (`docs/configuration.md`).
    """
    permitted = set(configuration.regions)
    if not permitted:
        return
    for element in _accounts(ir):
        attribute = _text(element, "region")
        if attribute is None or _value(attribute) in permitted:
            continue
        yield Hit(
            f'The {_kind_name(element)} {element.name} uses the Region "{_value(attribute)}". '
            "This Region is not in aws.regions.",
            attribute.location or element.location,
            element.identity,
        )


def _integer(attributes: Mapping[str, Attribute], name: str) -> int | None:
    attribute = attributes.get(name)
    if attribute is None or not isinstance(attribute.value, IntegerValue):
        return None
    return attribute.value.value


def _realizations(ir: Ir, kind: str) -> dict[str, Element]:
    return {element.identity: element for element in ir.elements if element.kind == kind}


# trace: PRD-VAL-015, PRD-IAC-012, PRD-DSML-042
@implements(AWS_003)
def aws_003(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    """Find the services with a pair of cpu and memory that Fargate does not accept.

    The rule examines the values of each service in each environment. If the
    model has no environment, it examines the default values. If a value is
    missing, the rule gives no finding.
    """
    services = _realizations(ir, "AwsEcsService")
    defaults = {
        identity: {attribute.name: attribute for attribute in element.attributes}
        for identity, element in services.items()
    }
    places: list[tuple[str | None, Mapping[str, Mapping[str, Attribute]]]] = [
        (environment.name, realization_attributes(ir, environment.identity))
        for environment in environments(ir)
    ] or [(None, defaults)]
    hits: dict[tuple[object, ...], Hit] = {}
    for environment, values in places:
        for identity, element in sorted(services.items()):
            attributes = values[identity]
            cpu = _integer(attributes, "cpu")
            memory = _integer(attributes, "memory")
            if cpu is None or memory is None or memory in FARGATE_PAIRS.get(cpu, ()):
                continue
            changed = [
                attributes[name]
                for name in ("cpu", "memory")
                if attributes[name] is not defaults[identity].get(name)
            ]
            where = (
                "" if not changed or environment is None else f" in the environment {environment}"
            )
            attribute = (changed or [attributes["cpu"]])[0]
            hit = Hit(
                f"The service {element.name} has cpu = {cpu} and memory = {memory}{where}. "
                "Fargate does not accept this pair.",
                attribute.location or element.location,
                identity,
            )
            hits.setdefault((hit.location, hit.message), hit)
    yield from hits.values()


def _prod_values(ir: Ir, kind: str, name: str) -> Iterator[tuple[Element, Attribute]]:
    """Give the attribute `name` of each realization of a kind in the prod environment."""
    services = _realizations(ir, kind)
    for environment in environments(ir):
        if environment.name != PROD:
            continue
        values = realization_attributes(ir, environment.identity)
        for identity, element in sorted(services.items()):
            attribute = values[identity].get(name)
            if attribute is not None:
                yield element, attribute


# trace: PRD-VAL-015, PRD-IAC-017, PRD-DSML-042
@implements(AWS_004)
def aws_004(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    for element, attribute in _prod_values(ir, "AwsRdsPostgres", "multiAz"):
        if isinstance(attribute.value, BooleanValue) and not attribute.value.value:
            yield Hit(
                f"The database {element.name} has multiAz = false in the environment prod.",
                attribute.location or element.location,
                element.identity,
            )


# trace: PRD-VAL-015, PRD-IAC-013, PRD-DSML-042
@implements(AWS_005)
def aws_005(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    for element, attribute in _prod_values(ir, "AwsEcsService", "minCount"):
        if isinstance(attribute.value, IntegerValue) and attribute.value.value < 2:
            yield Hit(
                f"The service {element.name} has minCount = {attribute.value.value} "
                "in the environment prod.",
                attribute.location or element.location,
                element.identity,
            )


RULES = (aws_001, aws_002, aws_003, aws_004, aws_005)
"""The rules of this module."""
