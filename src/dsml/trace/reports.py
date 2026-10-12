# trace: PRD-TRACE-012, PRD-TRACE-013, PRD-TRACE-014, PRD-CORE-026
"""The coverage report and the orphans report.

The reports use the link graph of the IR, the trace manifest and the trace
comments in the hand-written files (PRD-TRACE-013). This module reads only
the IR and the data that the caller gives (PRD-CORE-026).

The coverage report has one row for each requirement. The status of a
requirement is (PRD-TRACE-014):

- `missing`: the requirement has no satisfying element.
- `satisfied`: the requirement has a satisfying element and no verification.
- `verified`: the requirement has a satisfying element and a verification.

The orphans report has one row for each item with no link. The categories
are in `ORPHAN_CATEGORIES`.
"""

import re
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

from dsml.ir.external import imported
from dsml.ir.model import Element, ElementKind, Ir, ListValue, StringValue
from dsml.trace.comments import TraceComment
from dsml.trace.graph import LinkGraph
from dsml.trace.report import Cell, Report, texts

COVERAGE: Final = "coverage"
ORPHANS: Final = "orphans"

COVERAGE_COLUMNS: Final = (
    "requirement",
    "needs",
    "satisfiedBy",
    "generatedFiles",
    "traceComments",
    "verifications",
    "status",
)
"""The columns of the coverage report."""

ORPHANS_COLUMNS: Final = ("category", "item", "location")
"""The columns of the orphans report."""

MISSING: Final = "missing"
SATISFIED: Final = "satisfied"
VERIFIED: Final = "verified"

NEED_WITHOUT_REQUIREMENT: Final = "need-without-requirement"
REQUIREMENT_WITHOUT_NEED: Final = "requirement-without-need"
ELEMENT_WITHOUT_REQUIREMENT: Final = "element-without-requirement"
UNKNOWN_TRACE_ID: Final = "unknown-trace-id"
TEST_FILE_WITHOUT_VERIFICATION: Final = "test-file-without-verification"

ORPHAN_CATEGORIES: Final = (
    NEED_WITHOUT_REQUIREMENT,
    REQUIREMENT_WITHOUT_NEED,
    ELEMENT_WITHOUT_REQUIREMENT,
    UNKNOWN_TRACE_ID,
    TEST_FILE_WITHOUT_VERIFICATION,
)
"""The categories of the orphans report."""

SOLUTION_KINDS: Final[frozenset[ElementKind]] = frozenset(
    {
        "Application",
        "AwsCognito",
        "AwsEcsService",
        "AwsRdsPostgres",
        "AwsSecrets",
        "AwsVpc",
        "ContainerService",
        "Entity",
        "ExternalApi",
        "Network",
        "Operation",
        "RelationalDatabase",
        "SecretStore",
        "UserDirectory",
    }
)
"""The application and infrastructure elements that the orphans report examines.

The members of these elements, for example a field of an entity or an
exposed part of an application, are not in the report. The entities and the
operations that the OpenAPI file of an external API gives are also not in
the report: the external API is the element of the model. An element satisfies
a requirement if a requirement is upstream of it: through a `satisfy` link,
or through an `allocate` or a `#Realizes` link to an element that satisfies
a requirement.
"""

_TEST_FILE_NAMES: Final = (
    re.compile(r"test_.*\.py"),
    re.compile(r".*_test\.py"),
    re.compile(r".*\.(?:test|spec)\.(?:cts|mts|ts|tsx)"),
)
"""The names of test files: the defaults of pytest and of the TypeScript test tools."""

TEST_FILES_ATTRIBUTE: Final = "testFiles"
"""The attribute of a verification that gives its test files (PRD-DSML-048)."""


# trace: PRD-TRACE-013
@dataclass(frozen=True, slots=True)
class TraceData:
    """The data of the coverage and orphans reports.

    All paths are relative to the folder of the configuration file, with "/".
    """

    ir: Ir
    generated: tuple[tuple[str, str], ...] = ()
    """The pairs (element identity, file path) of the trace manifest `.dsml/trace.gen.json`."""
    comments: tuple[TraceComment, ...] = ()
    """The trace comments in the hand-written files."""
    files: tuple[str, ...] = ()
    """The hand-written files in the output folders and in the test folders."""
    model_commit: str = ""


# trace: PRD-TRACE-013, PRD-TRACE-014
def coverage_report(data: TraceData) -> Report:
    """Make the coverage report: one row for each requirement, with its status.

    - `needs`: the needs that the requirement frames, also through the
      requirements that it is derived from.
    - `satisfiedBy`: the elements with a `satisfy` link to the requirement.
    - `generatedFiles`: the generated files of the requirement and of the
      elements downstream of it, from the trace manifest.
    - `traceComments`: the trace comments with the ID of the requirement, as
      `<file>:<line>`.
    - `verifications`: the verifications with a `verify` link to the
      requirement.
    """
    graph = LinkGraph(data.ir)
    files: dict[str, set[str]] = {}
    for element, path in data.generated:
        files.setdefault(element, set()).add(path)
    places = _comment_places(data)
    rows: list[tuple[Cell, ...]] = []
    for requirement in _of_kind(data.ir, "Requirement"):
        identity = requirement.identity
        satisfied_by = graph.satisfying_elements(identity)
        verifications = graph.verifications(identity)
        elements = (identity, *graph.downstream(identity))
        rows.append(
            (
                identity,
                graph.needs_of(identity),
                satisfied_by,
                texts(path for element in elements for path in files.get(element, ())),
                tuple(f"{path}:{line}" for path, line in sorted(places.get(identity, ()))),
                verifications,
                requirement_status(satisfied_by, verifications),
            )
        )
    return Report(COVERAGE, COVERAGE_COLUMNS, tuple(rows), data.model_commit)


# trace: PRD-TRACE-014
def requirement_status(satisfied_by: Collection[str], verifications: Collection[str]) -> str:
    """Give the status of a requirement in the coverage report."""
    if not satisfied_by:
        return MISSING
    return VERIFIED if verifications else SATISFIED


# trace: PRD-TRACE-012, PRD-TRACE-013
def orphans_report(data: TraceData) -> Report:
    """Make the orphans report: one row for each item with no link.

    The column `item` gives the identity of an element, the ID in a trace
    comment or the path of a test file. The column `location` gives the
    file and the line of the item.
    """
    graph = LinkGraph(data.ir)
    rows: list[tuple[Cell, ...]] = []
    for need in _of_kind(data.ir, "Need"):
        if not graph.downstream(need.identity, ["Requirement"]):
            rows.append((NEED_WITHOUT_REQUIREMENT, need.identity, _location(need)))
    for requirement in _of_kind(data.ir, "Requirement"):
        if not graph.needs_of(requirement.identity):
            rows.append((REQUIREMENT_WITHOUT_NEED, requirement.identity, _location(requirement)))
    outside = imported(data.ir)
    for element in data.ir.elements:
        if element.identity in outside:
            continue
        if element.kind in SOLUTION_KINDS and not graph.requirements_of(element.identity):
            rows.append((ELEMENT_WITHOUT_REQUIREMENT, element.identity, _location(element)))
    names = _names(data.ir)
    for comment in data.comments:
        for trace_id in comment.ids:
            if _normal(trace_id) not in names:
                rows.append((UNKNOWN_TRACE_ID, trace_id, f"{comment.path}:{comment.line}"))
    named = _named_test_files(data.ir)
    for path in data.files:
        if is_test_file(path) and path not in named:
            rows.append((TEST_FILE_WITHOUT_VERIFICATION, path, path))
    return Report(ORPHANS, ORPHANS_COLUMNS, tuple(rows), data.model_commit)


def is_test_file(path: str) -> bool:
    """Tell if the name of the file is the name of a test file."""
    name = PurePosixPath(path).name
    return any(pattern.fullmatch(name) for pattern in _TEST_FILE_NAMES)


def _of_kind(ir: Ir, kind: ElementKind) -> list[Element]:
    return [element for element in ir.elements if element.kind == kind]


def _location(element: Element) -> str:
    return f"{element.location.file}:{element.location.line}"


def _normal(name: str) -> str:
    """Remove the quotes of each part of a short name or a qualified name."""
    return "::".join(part.strip("'") for part in name.split("::"))


def _names(ir: Ir) -> dict[str, str]:
    """Give the identity of the element of each ID that a trace comment can use.

    An ID is the identity, the short name or the qualified name of an element.
    """
    names: dict[str, str] = {}
    for element in ir.elements:
        for name in (element.qualified_name, element.short_name, element.identity):
            if name:
                names[_normal(name)] = element.identity
    return names


def _comment_places(data: TraceData) -> Mapping[str, set[tuple[str, int]]]:
    """Give the file and the line of the trace comments of each element identity."""
    names = _names(data.ir)
    places: dict[str, set[tuple[str, int]]] = {}
    for comment in data.comments:
        for trace_id in comment.ids:
            identity = names.get(_normal(trace_id))
            if identity is not None:
                places.setdefault(identity, set()).add((comment.path, comment.line))
    return places


def _named_test_files(ir: Ir) -> set[str]:
    """Give the test files that the verifications name (PRD-DSML-048)."""
    named: set[str] = set()
    for verification in _of_kind(ir, "Verification"):
        for attribute in verification.attributes:
            if attribute.name == TEST_FILES_ATTRIBUTE:
                named.update(_strings([attribute.value]))
    return named


def _strings(values: Iterable[object]) -> Iterable[str]:
    for value in values:
        if isinstance(value, StringValue):
            yield value.value
        elif isinstance(value, ListValue):
            yield from _strings(value.items)
