# trace: PRD-CORE-022, PRD-CORE-023, PRD-CORE-024, PRD-CORE-025, PRD-CORE-031, PRD-TRACE-003
"""The typed models of the IR.

Each model is a frozen data class. The writer (`dsml.ir.writer`) converts the
models to canonical JSON, and `ir.schema.json` gives the JSON form. Each field
name in Python is the snake case form of the JSON key, for example
`qualified_name` and `qualifiedName`.

Each list field is a tuple. The field metadata `ORDER` tells the writer how to
write the list:

- `SORTED`: the writer sorts the items. It sorts objects by `sort_key()`, then
  by their canonical JSON text. It sorts texts by their value.
- `MODEL`: the writer keeps the order of the model, because the order is data,
  for example the order of the views in a navigation list.

This module does not import OpenSysML (PRD-CORE-020, PRD-CORE-025).
"""

import re
from dataclasses import dataclass, field
from typing import Any, ClassVar, Final, Literal

IR_VERSION: Final = "1.1.0"
"""The semantic version of the IR (PRD-CORE-023).

A change that removes or renames a field, or that changes the meaning of a
field, increases the major version. A change that adds a field or a value
increases the minor version. `docs/notes/ir.md` gives the full rules.
"""

ORDER: Final = "order"
"""The key of the field metadata that gives the order of a list field."""

SORTED: Final = "sorted"
"""The writer sorts the items of the list."""

MODEL: Final = "model"
"""The writer keeps the order of the model."""

type ElementKind = Literal[
    "Application",
    "AwsCognito",
    "AwsEcsService",
    "AwsRdsPostgres",
    "AwsSecrets",
    "AwsStaticSite",
    "AwsVpc",
    "ContainerService",
    "Entity",
    "Enumeration",
    "Environment",
    "Exposed",
    "ExternalApi",
    "Field",
    "Need",
    "Network",
    "Operation",
    "Override",
    "Package",
    "Parameter",
    "Relation",
    "RelationalDatabase",
    "Requirement",
    "Roles",
    "SecretStore",
    "Stakeholder",
    "StaticSite",
    "ToolingAccount",
    "UserDirectory",
    "Verification",
    "View",
]
"""The kinds of IR elements.

Most kinds are the DSML keywords of element kinds. These kinds are not
keywords: `Package` (a package of the model), `Enumeration` (an enumeration
definition that is not `#Roles`), `Field` (an attribute of an entity),
`Relation` (a reference of an entity to an entity) and `Parameter` (an `in` or
`out` parameter of an operation).
"""

# trace: PRD-TRACE-001, PRD-TRACE-003
type LinkType = Literal[
    "allocate",
    "calls",
    "derivation",
    "frame",
    "realizes",
    "refinement",
    "satisfy",
    "stakeholder",
    "uses",
    "verify",
]
"""The types of links between elements (PRD-TRACE-001, PRD-DSML-030, PRD-DSML-040)."""

type Direction = Literal["in", "out", "inout"]
"""The direction of an operation parameter."""

# trace: PRD-CORE-054
type ConstraintValue = Literal["true", "false", "unknown"]
"""The result of a formal constraint in one environment."""

type Severity = Literal["error", "warning", "info"]
"""The severity of a finding (PRD-VAL-003)."""

type SortKey = tuple[str | int, ...]

# A relative POSIX path with no ".." segment. It must not start with "/" or
# with a drive letter, and it must not contain "\".
_RELATIVE_PATH = re.compile(r"^(?!/)(?![A-Za-z]:)(?!.*\\)(?!(?:.*/)?\.\.(?:/|$)).+$")


def _sorted() -> Any:
    """Give a list field that the writer sorts."""
    return field(default=(), metadata={ORDER: SORTED})


def _model_order() -> Any:
    """Give a list field that keeps the order of the model."""
    return field(default=(), metadata={ORDER: MODEL})


# trace: PRD-CORE-033
def check_relative_path(path: str) -> str:
    """Make sure that a path is relative to the repository root.

    The IR must not contain an absolute path (PRD-CORE-033). The function
    gives the path if it is correct.
    """
    if not _RELATIVE_PATH.fullmatch(path):
        raise ValueError(f'The path "{path}" must be a relative POSIX path with no ".." segment.')
    return path


@dataclass(frozen=True, slots=True)
class Node:
    """The base class of all IR models."""

    def sort_key(self) -> SortKey:
        """Give the key that sorts this object in a sorted list."""
        return ()


# trace: PRD-CORE-007, PRD-CORE-024, PRD-CORE-033
@dataclass(frozen=True, slots=True)
class Location(Node):
    """A location in a model file.

    `file` is relative to the repository root and uses "/". Lines and columns
    start at 1.
    """

    file: str
    line: int
    column: int

    def __post_init__(self) -> None:
        check_relative_path(self.file)
        if self.line < 1 or self.column < 1:
            raise ValueError("A line and a column must start at 1.")

    def sort_key(self) -> SortKey:
        return (self.file, self.line, self.column)


@dataclass(frozen=True, slots=True)
class Multiplicity(Node):
    """A multiplicity. `upper` is None for "*"."""

    lower: int
    upper: int | None


@dataclass(frozen=True, slots=True)
class Value(Node):
    """The base class of attribute values. `TYPE` is the JSON key "type"."""

    TYPE: ClassVar[str] = ""


@dataclass(frozen=True, slots=True)
class StringValue(Value):
    """A string value."""

    TYPE: ClassVar[str] = "string"
    value: str


@dataclass(frozen=True, slots=True)
class IntegerValue(Value):
    """An integer value."""

    TYPE: ClassVar[str] = "integer"
    value: int


@dataclass(frozen=True, slots=True)
class RealValue(Value):
    """A real value. The writer does not accept NaN or an infinite value."""

    TYPE: ClassVar[str] = "real"
    value: float


@dataclass(frozen=True, slots=True)
class BooleanValue(Value):
    """A Boolean value."""

    TYPE: ClassVar[str] = "boolean"
    value: bool


@dataclass(frozen=True, slots=True)
class EnumValue(Value):
    """A literal of an enumeration, for example `Priority::must`.

    `enumeration` is the qualified name of the enumeration definition.
    """

    TYPE: ClassVar[str] = "enum"
    enumeration: str
    literal: str


@dataclass(frozen=True, slots=True)
class ReferenceValue(Value):
    """A reference to an element. `target` is the identity of the element."""

    TYPE: ClassVar[str] = "reference"
    target: str


@dataclass(frozen=True, slots=True)
class ListValue(Value):
    """A list of values in the order of the model."""

    TYPE: ClassVar[str] = "list"
    items: tuple[Value, ...] = _model_order()


# trace: PRD-CORE-024
@dataclass(frozen=True, slots=True)
class Attribute(Node):
    """The value of one DSML attribute, for example `priority`."""

    name: str
    value: Value
    location: Location | None = None

    def sort_key(self) -> SortKey:
        return (self.name,)


@dataclass(frozen=True, slots=True)
class Annotation(Node):
    """A metadata usage on an element, for example `#Key`, `#Waiver` or `@FieldRules`.

    `name` is the name of the metadata definition.
    """

    name: str
    attributes: tuple[Attribute, ...] = _sorted()
    location: Location | None = None

    def sort_key(self) -> SortKey:
        return (self.name,)


# trace: PRD-CORE-024, PRD-DSML-053
@dataclass(frozen=True, slots=True)
class Element(Node):
    """One element of the five layers.

    `identity` is the short name of the element, or its qualified name if it
    has no short name (PRD-DSML-053). `owner` and `types` hold identities of
    other elements. `types` gives the definitions that type the element or
    that it specializes or subsets.
    """

    identity: str
    kind: ElementKind
    name: str
    qualified_name: str
    location: Location
    short_name: str | None = None
    owner: str | None = None
    doc: str | None = None
    multiplicity: Multiplicity | None = None
    direction: Direction | None = None
    types: tuple[str, ...] = _sorted()
    attributes: tuple[Attribute, ...] = _sorted()
    annotations: tuple[Annotation, ...] = _sorted()

    def sort_key(self) -> SortKey:
        return (self.identity, self.name)


# trace: PRD-TRACE-003
@dataclass(frozen=True, slots=True)
class Link(Node):
    """A trace link from the source element to the target element.

    `source` and `target` are identities of elements.
    """

    type: LinkType
    source: str
    target: str
    location: Location

    def sort_key(self) -> SortKey:
        return (self.source, self.type, self.target)


# trace: PRD-CORE-054
@dataclass(frozen=True, slots=True)
class ConstraintResult(Node):
    """The result of one formal constraint of a requirement in one environment.

    `requirement` and `environment` are identities of elements. `index` is the
    position of the constraint in the requirement, from 1. For an "unknown"
    result, `missing_features` gives the features that have no value.
    """

    requirement: str
    index: int
    environment: str
    value: ConstraintValue
    location: Location
    missing_features: tuple[str, ...] = _sorted()

    def __post_init__(self) -> None:
        if self.index < 1:
            raise ValueError("The index of a constraint must start at 1.")

    def sort_key(self) -> SortKey:
        return (self.requirement, self.index, self.environment)


# trace: PRD-CORE-021, PRD-VAL-007
@dataclass(frozen=True, slots=True)
class Finding(Node):
    """A finding of the adapter, for example a SYN finding.

    `element` is the identity of the element of the finding, if there is one.
    The writer sorts findings by file, line, column and rule (PRD-VAL-007). A
    finding with no location comes first.
    """

    rule: str
    severity: Severity
    message: str
    location: Location | None = None
    element: str | None = None

    def sort_key(self) -> SortKey:
        place = ("", 0, 0) if self.location is None else self.location.sort_key()
        return (*place, self.rule, self.message)


# trace: PRD-CORE-022, PRD-CORE-023, PRD-CORE-024, PRD-TRACE-003
@dataclass(frozen=True, slots=True)
class Ir(Node):
    """The IR of one model.

    `files` gives the model files, relative to the repository root.
    """

    files: tuple[str, ...] = _sorted()
    elements: tuple[Element, ...] = _sorted()
    links: tuple[Link, ...] = _sorted()
    constraint_results: tuple[ConstraintResult, ...] = _sorted()
    findings: tuple[Finding, ...] = _sorted()
    ir_version: str = IR_VERSION

    def __post_init__(self) -> None:
        for file in self.files:
            check_relative_path(file)
