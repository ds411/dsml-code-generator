# trace: PRD-VAL-015, PRD-DSML-013, PRD-DSML-015, PRD-DSML-036, PRD-DSML-045
# trace: PRD-DSML-050, PRD-DSML-051, PRD-DSML-052, PRD-DSML-056
"""The STR rules for the DSML version, the mandatory attributes and the IDs.

- STR-001: the model states a DSML version that the toolchain supports.
- STR-002: each need, requirement and verification has its mandatory attributes.
- STR-003: each short name agrees with the ID pattern of its kind.
- STR-004: each short name is unique in the model.
- STR-016: a logical infrastructure element has no AWS attribute.

The other STR rules are in other modules of the registry.
"""

import re
from collections import defaultdict
from collections.abc import Iterator, Mapping
from typing import Final

from dsml.config import Configuration
from dsml.ir.model import Element, ElementKind, IntegerValue, Ir, StringValue
from dsml.library import LIBRARY_VERSION
from dsml.validate.rule import Hit, Rule, implements

# trace: PRD-DSML-056
STR_001 = Rule(
    id="STR-001",
    severity="error",
    message="The model has no #DsmlVersion, or a DSML version that the toolchain does not support.",
    fix_hint=(
        "Put @DsmlVersion { major = 1; minor = 0; } on the root package. "
        "Use a major version and a minor version that the toolchain supports."
    ),
)

# trace: PRD-DSML-013, PRD-DSML-015, PRD-DSML-045
STR_002 = Rule(
    id="STR-002",
    severity="error",
    message="A need, requirement or verification has no value for a mandatory attribute.",
    fix_hint="Give a value for the attribute. docs/prd/01-dsml-prd.md gives the attributes.",
)

# trace: PRD-DSML-050, PRD-DSML-051
STR_003 = Rule(
    id="STR-003",
    severity="error",
    message="A short name does not agree with the ID pattern of its kind.",
    fix_hint="Change the short name, or change the pattern in the keys ids.* of dsml.toml.",
)

# trace: PRD-DSML-052
STR_004 = Rule(
    id="STR-004",
    severity="error",
    message="Two elements have the same short name.",
    fix_hint="Give each element a different short name. Do not use a deleted ID again.",
)

# trace: PRD-DSML-036, PRD-DSML-038
STR_016 = Rule(
    id="STR-016",
    severity="error",
    message="A logical infrastructure element has an AWS attribute.",
    fix_hint="Move the attribute to the AWS realization of the logical element.",
)

# trace: PRD-DSML-056, PRD-DSML-057
SUPPORTED_MAJOR: Final = int(LIBRARY_VERSION.split(".")[0])
"""The major DSML version that the toolchain supports."""

SUPPORTED_MINOR: Final = int(LIBRARY_VERSION.split(".")[1])
"""The highest minor DSML version that the toolchain supports.

A minor version does not make a valid model invalid (PRD-DSML-057). Thus the
toolchain supports each minor version up to the minor version of its library.
"""

SUPPORTED: Final = (
    f"the version {SUPPORTED_MAJOR}.0"
    if SUPPORTED_MINOR == 0
    else f"the versions {SUPPORTED_MAJOR}.0 to {SUPPORTED_MAJOR}.{SUPPORTED_MINOR}"
)
"""The DSML versions that the toolchain supports, as text for a message."""

DSML_VERSION: Final = "DsmlVersion"
"""The name of the metadata that gives the DSML version (PRD-DSML-056)."""

# trace: PRD-DSML-013, PRD-DSML-015, PRD-DSML-045
MANDATORY: Final[Mapping[ElementKind, tuple[str, ...]]] = {
    "Need": ("title", "doc", "priority", "status"),
    "Requirement": ("title", "doc", "kind", "priority", "status"),
    "Verification": ("title", "method"),
}
"""The mandatory attributes of each kind, after the ID. "doc" is the text."""

_NOUNS: Final[Mapping[ElementKind, str]] = {
    "Need": "need",
    "Requirement": "requirement",
    "Verification": "verification",
}

# trace: PRD-DSML-036, PRD-DSML-038, PRD-DSML-042
AWS_ATTRIBUTES: Final = frozenset(
    {
        "accountId",
        "cpu",
        "desiredCount",
        "instanceClass",
        "maxCount",
        "memory",
        "minCount",
        "multiAz",
        "natGatewayCount",
        "region",
    }
)
"""The AWS attributes of the DSML library: the attributes of the AWS realizations
(PRD-DSML-042), and the account ID and the Region."""

LOGICAL_KINDS: Final = frozenset(
    {"Network", "ContainerService", "RelationalDatabase", "UserDirectory", "SecretStore"}
)
"""The kinds of logical infrastructure elements in phase 1 (PRD-DSML-035)."""


# trace: PRD-DSML-056
def _root_packages(ir: Ir) -> list[Element]:
    return [item for item in ir.elements if item.kind == "Package" and item.owner is None]


# trace: PRD-DSML-056, PRD-DSML-057
@implements(STR_001)
def str_001(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    roots = _root_packages(ir)
    found = False
    for package in roots:
        for annotation in package.annotations:
            if annotation.name != DSML_VERSION:
                continue
            found = True
            values = {item.name: item.value for item in annotation.attributes}
            major, minor = values.get("major"), values.get("minor")
            if (
                isinstance(major, IntegerValue)
                and isinstance(minor, IntegerValue)
                and major.value == SUPPORTED_MAJOR
                and 0 <= minor.value <= SUPPORTED_MINOR
            ):
                continue
            given = ".".join(
                str(item.value) if isinstance(item, IntegerValue) else "?"
                for item in (major, minor)
            )
            yield Hit(
                f'The package "{package.name}" gives the DSML version {given}. '
                f"The toolchain supports {SUPPORTED}.",
                annotation.location or package.location,
                package.identity,
            )
    if not found:
        first = min(roots, key=lambda item: item.location.sort_key(), default=None)
        yield Hit(
            "The model has no @DsmlVersion on a root package.",
            None if first is None else first.location,
            None if first is None else first.identity,
        )


def _has_value(element: Element, name: str) -> bool:
    if name == "doc":
        return element.doc is not None and element.doc.strip() != ""
    for attribute in element.attributes:
        if attribute.name == name:
            value = attribute.value
            return not (isinstance(value, StringValue) and value.value.strip() == "")
    return False


# trace: PRD-DSML-013, PRD-DSML-015, PRD-DSML-045, PRD-DSML-050
@implements(STR_002)
def str_002(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    for element in ir.elements:
        names = MANDATORY.get(element.kind)
        if names is None:
            continue
        noun = _NOUNS[element.kind]
        if element.short_name is None:
            yield Hit(
                f'The {noun} "{element.qualified_name}" has no ID (short name).',
                element.location,
                element.identity,
            )
        for name in names:
            if not _has_value(element, name):
                what = "text (doc comment)" if name == "doc" else f'attribute "{name}"'
                yield Hit(
                    f'The {noun} "{element.identity}" has no value for the {what}.',
                    element.location,
                    element.identity,
                )


# trace: PRD-DSML-050, PRD-DSML-051
@implements(STR_003)
def str_003(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    patterns: Mapping[ElementKind, str] = {
        "Need": configuration.ids.need,
        "Requirement": configuration.ids.requirement,
        "Verification": configuration.ids.verification,
    }
    for element in ir.elements:
        pattern = patterns.get(element.kind)
        if pattern is None or element.short_name is None:
            continue
        if not re.fullmatch(pattern, element.short_name):
            key = _NOUNS[element.kind]
            yield Hit(
                f'The {key} short name "{element.short_name}" does not agree with the '
                f'pattern "{pattern}" (ids.{key}).',
                element.location,
                element.identity,
            )


# trace: PRD-DSML-052
@implements(STR_004)
def str_004(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    groups: defaultdict[str, list[Element]] = defaultdict(list)
    for element in ir.elements:
        if element.short_name is not None:
            groups[element.short_name].append(element)
    for short_name, elements in sorted(groups.items()):
        if len(elements) < 2:
            continue
        for element in elements:
            others = sorted(item.qualified_name for item in elements if item is not element)
            yield Hit(
                f'The short name "{short_name}" of "{element.qualified_name}" is also on '
                + ", ".join(f'"{name}"' for name in others)
                + ".",
                element.location,
                element.identity,
            )


# trace: PRD-DSML-036
def is_aws_attribute(name: str) -> bool:
    """Tell if an attribute name is an AWS attribute.

    An AWS attribute is an attribute of the list `AWS_ATTRIBUTES`, or an
    attribute with a name that starts with "aws", for example `awsLogGroup`.
    """
    return name in AWS_ATTRIBUTES or name.lower().startswith("aws")


# trace: PRD-DSML-036, PRD-DSML-038
@implements(STR_016)
def str_016(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    for element in ir.elements:
        if element.kind not in LOGICAL_KINDS:
            continue
        for attribute in element.attributes:
            if is_aws_attribute(attribute.name):
                yield Hit(
                    f'The logical element "{element.identity}" has the AWS attribute '
                    f'"{attribute.name}".',
                    attribute.location or element.location,
                    element.identity,
                )


RULES = (str_001, str_002, str_003, str_004, str_016)
"""The rules of this module."""
