# trace: PRD-TRACE-001, PRD-TRACE-002, PRD-TRACE-003, PRD-TRACE-004
"""The link graph of the traceability engine.

The graph holds the trace links of the IR. Each trace link has one end that is
nearer to the stakeholder needs (the upstream end) and one end that is nearer
to the solution (the downstream end):

| Link type     | Source                                | Target                 | Upstream end |
| ------------- | ------------------------------------- | ---------------------- | ------------ |
| `stakeholder` | need                                  | stakeholder            | target       |
| `frame`       | requirement                           | need                   | target       |
| `derivation`  | derived requirement                   | original requirement   | target       |
| `refinement`  | refining element                      | requirement            | target       |
| `satisfy`     | application or infrastructure element | requirement            | target       |
| `allocate`    | application element                   | infrastructure element | source       |
| `realizes`    | AWS realization                       | logical element        | target       |
| `verify`      | verification                          | requirement            | target       |

A query from a need goes downstream: to its requirements, the elements that
satisfy them, the infrastructure elements and AWS realizations of these
elements, and the verifications. A query from an element goes upstream: to its
requirements and its needs (PRD-TRACE-004).

The links `calls` and `uses` connect two solution elements. They are not trace
links (PRD-TRACE-001), thus the graph does not use them.

All query results are in sorted order, so the reports are deterministic
(PRD-CORE-028).
"""

from collections import deque
from collections.abc import Iterable, Mapping
from typing import Final, Literal

from dsml.ir.model import Element, ElementKind, Ir, Link, LinkType

type _End = Literal["source", "target"]

# trace: PRD-TRACE-001
_UPSTREAM_END: Final[Mapping[LinkType, _End]] = {
    "allocate": "source",
    "derivation": "target",
    "frame": "target",
    "realizes": "target",
    "refinement": "target",
    "satisfy": "target",
    "stakeholder": "target",
    "verify": "target",
}

# trace: PRD-TRACE-001
TRACE_LINK_TYPES: Final[frozenset[LinkType]] = frozenset(_UPSTREAM_END)
"""The link types of PRD-TRACE-001. `realizes` is the link of `#Realizes`."""


def _link_order(link: Link) -> tuple[tuple[str | int, ...], tuple[str | int, ...]]:
    return (link.sort_key(), link.location.sort_key())


# trace: PRD-TRACE-001, PRD-TRACE-002, PRD-TRACE-003, PRD-TRACE-004
class LinkGraph:
    """The trace links of one IR, with queries in the two directions.

    An identity in a query must be the identity of an element of the IR, or
    an end of a trace link.
    """

    def __init__(self, ir: Ir) -> None:
        self._elements: dict[str, Element] = {element.identity: element for element in ir.elements}
        links = sorted(
            (link for link in ir.links if link.type in TRACE_LINK_TYPES), key=_link_order
        )
        self._links: tuple[Link, ...] = tuple(links)
        self._from: dict[str, list[Link]] = {}
        self._to: dict[str, list[Link]] = {}
        self._up: dict[str, set[str]] = {}
        self._down: dict[str, set[str]] = {}
        for link in self._links:
            self._from.setdefault(link.source, []).append(link)
            self._to.setdefault(link.target, []).append(link)
            if _UPSTREAM_END[link.type] == "target":
                upper, lower = link.target, link.source
            else:
                upper, lower = link.source, link.target
            self._up.setdefault(lower, set()).add(upper)
            self._down.setdefault(upper, set()).add(lower)

    @property
    def links(self) -> tuple[Link, ...]:
        """Give all trace links, sorted by source, type and target."""
        return self._links

    def element(self, identity: str) -> Element | None:
        """Give the element with the identity, or None if the IR has no such element."""
        return self._elements.get(identity)

    def links_from(self, identity: str, link_type: LinkType | None = None) -> tuple[Link, ...]:
        """Give the trace links with the element as source, sorted.

        If `link_type` is not None, give only the links of that type.
        """
        self._check(identity)
        return _of_type(self._from.get(identity, ()), link_type)

    def links_to(self, identity: str, link_type: LinkType | None = None) -> tuple[Link, ...]:
        """Give the trace links with the element as target, sorted.

        If `link_type` is not None, give only the links of that type.
        """
        self._check(identity)
        return _of_type(self._to.get(identity, ()), link_type)

    # trace: PRD-TRACE-004
    def downstream(
        self, identity: str, kinds: Iterable[ElementKind] | None = None
    ) -> tuple[str, ...]:
        """Give the identities of all elements downstream of the element, sorted.

        For a need, these are its requirements, the requirements that come from
        them, the elements that satisfy or refine them, the infrastructure
        elements and AWS realizations of these elements, and the verifications.
        If `kinds` is not None, give only the elements of these kinds.
        """
        self._check(identity)
        return self._select(_reachable(identity, self._down), kinds)

    # trace: PRD-TRACE-004
    def upstream(
        self, identity: str, kinds: Iterable[ElementKind] | None = None
    ) -> tuple[str, ...]:
        """Give the identities of all elements upstream of the element, sorted.

        For an application or infrastructure element, these are the elements
        that it realizes or that are allocated to it, its requirements, its
        needs and their stakeholders. If `kinds` is not None, give only the
        elements of these kinds.
        """
        self._check(identity)
        return self._select(_reachable(identity, self._up), kinds)

    # trace: PRD-TRACE-004
    def needs_of(self, identity: str) -> tuple[str, ...]:
        """Give the needs upstream of the element, sorted."""
        return self.upstream(identity, ["Need"])

    # trace: PRD-TRACE-004
    def requirements_of(self, identity: str) -> tuple[str, ...]:
        """Give the requirements upstream of the element, sorted."""
        return self.upstream(identity, ["Requirement"])

    # trace: PRD-TRACE-002
    def satisfying_elements(self, requirement: str) -> tuple[str, ...]:
        """Give the elements with a `satisfy` link to the requirement, sorted.

        An element can be an application element or an infrastructure element.
        """
        return tuple(sorted({link.source for link in self.links_to(requirement, "satisfy")}))

    def verifications(self, requirement: str) -> tuple[str, ...]:
        """Give the verifications with a `verify` link to the requirement, sorted."""
        return tuple(sorted({link.source for link in self.links_to(requirement, "verify")}))

    def _check(self, identity: str) -> None:
        if (
            identity not in self._elements
            and identity not in self._from
            and identity not in self._to
        ):
            raise KeyError(f'The IR has no element "{identity}".')

    def _select(self, identities: set[str], kinds: Iterable[ElementKind] | None) -> tuple[str, ...]:
        if kinds is not None:
            wanted = frozenset(kinds)
            identities = {
                identity
                for identity in identities
                if (element := self._elements.get(identity)) is not None and element.kind in wanted
            }
        return tuple(sorted(identities))


def _of_type(links: Iterable[Link], link_type: LinkType | None) -> tuple[Link, ...]:
    return tuple(link for link in links if link_type is None or link.type == link_type)


def _reachable(start: str, edges: Mapping[str, set[str]]) -> set[str]:
    """Give all identities that the edges reach from the start, with no start.

    The search stops at an element that it found before, thus a cycle of links
    does not stop the search.
    """
    found: set[str] = set()
    queue = deque([start])
    while queue:
        for neighbor in edges.get(queue.popleft(), ()):
            if neighbor not in found and neighbor != start:
                found.add(neighbor)
                queue.append(neighbor)
    return found
