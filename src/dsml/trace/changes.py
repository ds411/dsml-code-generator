# trace: PRD-TRACE-013, PRD-TRACE-015, PRD-TRACE-016, PRD-TRACE-018, PRD-CORE-026
"""The changed elements, the impact report and the suspect report.

The reports compare the IR of the model with the IR of a baseline. This
module reads only the two IRs and the data that the caller gives
(PRD-CORE-026). The caller reads the baseline from Git.

An element is changed if the hash of its IR form, with no source locations,
is different from the hash in the baseline (PRD-TRACE-015). An element that
is only in the model is `added`. An element that is only in the baseline is
`removed`. Both also count as changed.

A change of an element also has an effect on the elements that contain it
or use it. For example, a changed field changes its entity, and a changed
entity changes the application that exposes it. The "users" of a changed
element are:

- the element,
- its owner, and the owner of the owner, to the top package,
- each element with a user in its types, and the users of that element.

The trace links of these users give the impact and the suspect links. A
removed element uses the IR of the baseline to find its users.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final, Literal

from dsml.ir.model import ElementKind, Ir
from dsml.trace.graph import LinkGraph
from dsml.trace.hashes import element_hashes
from dsml.trace.report import Cell, Report, texts

IMPACT: Final = "impact"
SUSPECT: Final = "suspect"

type Change = Literal["added", "changed", "removed"]

ADDED: Final = "added"
CHANGED: Final = "changed"
REMOVED: Final = "removed"

IMPACT_COLUMNS: Final = (
    "element",
    "change",
    "needs",
    "requirements",
    "verifications",
    "generatedFiles",
    "hclAddresses",
)
"""The columns of the impact report."""

SUSPECT_COLUMNS: Final = ("linkType", "source", "target", "changedEnds", "changedElements")
"""The columns of the suspect report."""

SOURCE: Final = "source"
TARGET: Final = "target"


# trace: PRD-TRACE-013, PRD-TRACE-016, PRD-TRACE-018
@dataclass(frozen=True, slots=True)
class ChangeData:
    """The data of the impact and suspect reports.

    All paths are relative to the folder of the configuration file, with "/".
    """

    ir: Ir
    baseline: Ir
    """The IR of the model at the baseline."""
    model_commit: str
    baseline_commit: str
    generated: tuple[tuple[str, str], ...] = ()
    """The pairs (element identity, file path) of the trace manifest."""
    addresses: tuple[tuple[str, str], ...] = ()
    """The pairs (element identity, HCL resource address) of the trace manifest."""


# trace: PRD-TRACE-015
def changed_elements(ir: Ir, baseline: Ir) -> dict[str, Change]:
    """Give the change of each changed element, in the order of the identities.

    An element with the same hash in the model and in the baseline is not in
    the result.
    """
    now = element_hashes(ir)
    before = element_hashes(baseline)
    changes: dict[str, Change] = {}
    for identity in sorted(now.keys() | before.keys()):
        if identity not in before:
            changes[identity] = ADDED
        elif identity not in now:
            changes[identity] = REMOVED
        elif now[identity] != before[identity]:
            changes[identity] = CHANGED
    return changes


# trace: PRD-TRACE-015
class Users:
    """The users of the elements of one IR: the owners and the elements that use them."""

    def __init__(self, ir: Ir) -> None:
        self._owner = {element.identity: element.owner for element in ir.elements}
        self._typed_by: dict[str, set[str]] = {}
        for element in ir.elements:
            for type_identity in element.types:
                self._typed_by.setdefault(type_identity, set()).add(element.identity)

    def of(self, identity: str) -> set[str]:
        """Give the element, its owners, the elements that use them, and so on."""
        found: set[str] = set()
        queue = [identity]
        while queue:
            current = queue.pop()
            if current in found:
                continue
            found.add(current)
            owner = self._owner.get(current)
            if owner is not None:
                queue.append(owner)
            queue.extend(self._typed_by.get(current, ()))
        return found


# trace: PRD-TRACE-013, PRD-TRACE-015, PRD-TRACE-018
def impact_report(data: ChangeData) -> Report:
    """Make the impact report: one row for each changed element.

    - `needs`, `requirements` and `verifications`: the elements of these
      kinds in the users of the changed element, upstream of them and
      downstream of them, and the verifications of these requirements.
    - `generatedFiles` and `hclAddresses`: the entries of the trace manifest
      of the users and of the elements downstream of them.
    """
    model = (LinkGraph(data.ir), Users(data.ir))
    baseline = (LinkGraph(data.baseline), Users(data.baseline))
    files = _by_element(data.generated)
    addresses = _by_element(data.addresses)
    rows: list[tuple[Cell, ...]] = []
    for identity, change in changed_elements(data.ir, data.baseline).items():
        graph, users = baseline if change == REMOVED else model
        below = users.of(identity)
        related = set(below)
        for user in sorted(below):
            if graph.links_from(user) or graph.links_to(user):
                below.update(graph.downstream(user))
                related.update(graph.upstream(user))
        related.update(below)
        requirements = _of_kind(graph, related, "Requirement")
        verifications = set(_of_kind(graph, related, "Verification"))
        for requirement in requirements:
            verifications.update(graph.verifications(requirement))
        rows.append(
            (
                identity,
                change,
                _of_kind(graph, related, "Need"),
                requirements,
                texts(verifications),
                texts(item for element in below for item in files.get(element, ())),
                texts(item for element in below for item in addresses.get(element, ())),
            )
        )
    return Report(IMPACT, IMPACT_COLUMNS, tuple(rows), data.model_commit, data.baseline_commit)


# trace: PRD-TRACE-013, PRD-TRACE-015, PRD-TRACE-018
def suspect_report(data: ChangeData) -> Report:
    """Make the suspect report: one row for each trace link of the model with a changed end.

    An end is changed if it is a user of a changed element.

    - `changedEnds`: `source`, `target` or both.
    - `changedElements`: the changed elements that change the ends.
    """
    model, baseline = Users(data.ir), Users(data.baseline)
    causes: dict[str, set[str]] = {}
    for identity, change in changed_elements(data.ir, data.baseline).items():
        for user in (baseline if change == REMOVED else model).of(identity):
            causes.setdefault(user, set()).add(identity)
    rows: list[tuple[Cell, ...]] = []
    for link in LinkGraph(data.ir).links:
        ends = tuple(
            end
            for end, identity in ((SOURCE, link.source), (TARGET, link.target))
            if identity in causes
        )
        if ends:
            changed = causes.get(link.source, set()) | causes.get(link.target, set())
            rows.append((link.type, link.source, link.target, ends, texts(changed)))
    return Report(SUSPECT, SUSPECT_COLUMNS, tuple(rows), data.model_commit, data.baseline_commit)


def _of_kind(graph: LinkGraph, identities: Iterable[str], kind: ElementKind) -> tuple[str, ...]:
    """Give the identities of the elements of the kind, sorted."""
    return texts(
        identity
        for identity in identities
        if (element := graph.element(identity)) is not None and element.kind == kind
    )


def _by_element(pairs: Iterable[tuple[str, str]]) -> Mapping[str, set[str]]:
    result: dict[str, set[str]] = {}
    for element, item in pairs:
        result.setdefault(element, set()).add(item)
    return result
