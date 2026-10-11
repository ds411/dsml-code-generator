# trace: PRD-VAL-015, PRD-DSML-030, PRD-DSML-037, PRD-DSML-039, PRD-DSML-040
"""The rules of the category XLY. They examine links between the layers.

The rules read the `allocate`, `realizes`, `uses` and `calls` links of the IR
(`docs/notes/ir-solution-layers.md`).

Phase 1 has no static site and no imported OpenAPI file. Thus:

- The IR has no `#StaticSite` element. XLY-002 rejects each allocation of a
  `react` application, because only a static site is correct for it.
- XLY-005 accepts only a `#Calls` dependency.
- XLY-007 examines only exposed entities and operations. A view is in phase 2.
"""

from collections.abc import Iterator
from typing import Final

from dsml.config import Configuration
from dsml.ir.model import (
    BooleanValue,
    Element,
    ElementKind,
    EnumValue,
    Ir,
    Link,
    LinkType,
)
from dsml.validate.rule import Hit, Rule, implements

# trace: PRD-DSML-035, PRD-DSML-037
REALIZATIONS: Final[dict[ElementKind, ElementKind]] = {
    "Network": "AwsVpc",
    "ContainerService": "AwsEcsService",
    "RelationalDatabase": "AwsRdsPostgres",
    "UserDirectory": "AwsCognito",
    "SecretStore": "AwsSecrets",
}
"""The logical kinds of phase 1 and the AWS kind that realizes each logical kind."""

# trace: PRD-DSML-039
HOSTS: Final[dict[str, str]] = {
    "fastapi": "ContainerService",
    "nextjs": "ContainerService",
    "react": "StaticSite",
}
"""The correct logical kind for the allocation of each application target."""

# trace: PRD-DSML-039
XLY_001 = Rule(
    id="XLY-001",
    severity="error",
    message="An application is not allocated to a logical element.",
    fix_hint="Allocate the application to one logical element with `allocate`.",
)

# trace: PRD-DSML-039
XLY_002 = Rule(
    id="XLY-002",
    severity="error",
    message="An application is allocated to a logical element of the wrong kind.",
    fix_hint=(
        "Allocate a `fastapi` or `nextjs` application to a `#ContainerService`. "
        "Allocate a `react` application to a `#StaticSite`."
    ),
)

# trace: PRD-DSML-037
XLY_003 = Rule(
    id="XLY-003",
    severity="error",
    message="A logical element has no AWS realization, or more than one.",
    fix_hint=(
        "Add one part usage with the correct AWS kind and a `#Realizes` dependency "
        "from it to the logical element. Remove the other realizations."
    ),
)

# trace: PRD-DSML-030, PRD-DSML-039
XLY_004 = Rule(
    id="XLY-004",
    severity="error",
    message="A `react` application uses a database.",
    fix_hint=(
        "Remove the `#Uses` dependency to the database. "
        "Let the `react` application call an API application with `#Calls`."
    ),
)

# trace: PRD-DSML-030
XLY_005 = Rule(
    id="XLY-005",
    severity="error",
    message="A `react` application has no `#Calls` dependency and no imported OpenAPI file.",
    fix_hint=(
        "Add a `#Calls` dependency from the `react` application to the application that it calls."
    ),
)

# trace: PRD-DSML-027, PRD-DSML-040
XLY_006 = Rule(
    id="XLY-006",
    severity="error",
    message="An application exposes entities, but its container service uses no database.",
    fix_hint="Add a `#Uses` dependency from the container service to a `#RelationalDatabase`.",
)

# trace: PRD-DSML-033, PRD-DSML-040
XLY_007 = Rule(
    id="XLY-007",
    severity="error",
    message=(
        "An application has protected operations or views, "
        "but its service or site uses no user directory."
    ),
    fix_hint=(
        "Add a `#Uses` dependency from the service or site to a `#UserDirectory`, "
        "or set `public = true` on each exposed element."
    ),
)


class _Graph:
    """The elements and links of the IR, with lookups by identity."""

    def __init__(self, ir: Ir) -> None:
        self.elements = {element.identity: element for element in ir.elements}
        self.links = ir.links

    def of_kind(self, *kinds: str) -> Iterator[Element]:
        """Give the elements of the kinds, in the order of the IR."""
        return (element for element in self.elements.values() if element.kind in kinds)

    def links_from(self, source: str, link_type: LinkType) -> Iterator[Link]:
        return (link for link in self.links if link.source == source and link.type == link_type)

    def links_to(self, target: str, link_type: LinkType) -> Iterator[Link]:
        return (link for link in self.links if link.target == target and link.type == link_type)

    def kind(self, identity: str) -> ElementKind | None:
        element = self.elements.get(identity)
        return None if element is None else element.kind

    def hosts(self, application: Element) -> list[Link]:
        """Give the allocations of an application to logical elements.

        Phase 2 adds the logical kind `StaticSite` to `REALIZATIONS`.
        """
        return [
            link
            for link in self.links_from(application.identity, "allocate")
            if self.kind(link.target) in REALIZATIONS
        ]

    def uses(self, source: str, kind: ElementKind) -> list[Link]:
        """Give the `uses` links from an element to elements of one kind."""
        return [link for link in self.links_from(source, "uses") if self.kind(link.target) == kind]

    def exposed(self, application: Element) -> Iterator[Element]:
        """Give the exposed entities and operations of an application."""
        return (
            element for element in self.of_kind("Exposed") if element.owner == application.identity
        )


def _target(application: Element) -> str | None:
    """Give the target of an application, for example "fastapi", or None."""
    for attribute in application.attributes:
        if attribute.name == "target" and isinstance(attribute.value, EnumValue):
            return attribute.value.literal
    return None


def _is_public(element: Element) -> bool:
    for attribute in element.attributes:
        if attribute.name == "public" and isinstance(attribute.value, BooleanValue):
            return attribute.value.value
    return False


def _react_applications(graph: _Graph) -> Iterator[Element]:
    return (app for app in graph.of_kind("Application") if _target(app) == "react")


# trace: PRD-DSML-039
@implements(XLY_001)
def xly_001(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    graph = _Graph(ir)
    for application in graph.of_kind("Application"):
        hosts = graph.hosts(application)
        if not hosts:
            yield Hit(location=application.location, element=application.identity)
        elif len(hosts) > 1:
            yield Hit(
                f"The application {application.name} is allocated to more than one "
                "logical element. Allocate it to one logical element only.",
                application.location,
                application.identity,
            )


# trace: PRD-DSML-039
@implements(XLY_002)
def xly_002(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    graph = _Graph(ir)
    for application in graph.of_kind("Application"):
        target = _target(application)
        if target not in HOSTS:
            continue  # STR-005 reports a missing or unknown target.
        for link in graph.hosts(application):
            kind = graph.kind(link.target)
            if kind != HOSTS[target]:
                yield Hit(
                    f"The {target} application {application.name} is allocated to the "
                    f"{kind} {graph.elements[link.target].name}. "
                    f"Allocate it to a #{HOSTS[target]}.",
                    link.location,
                    application.identity,
                )


# trace: PRD-DSML-037
@implements(XLY_003)
def xly_003(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    graph = _Graph(ir)
    for logical in graph.of_kind(*REALIZATIONS):
        expected = REALIZATIONS[logical.kind]
        count = sum(
            1
            for link in graph.links_to(logical.identity, "realizes")
            if graph.kind(link.source) == expected
        )
        if count == 1:
            continue
        amount = "no" if count == 0 else f"{count}"
        yield Hit(
            f"The {logical.kind} {logical.name} has {amount} AWS realizations "
            f"of the kind #{expected}. It must have one.",
            logical.location,
            logical.identity,
        )


# trace: PRD-DSML-030, PRD-DSML-039, PRD-DSML-040
@implements(XLY_004)
def xly_004(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    graph = _Graph(ir)
    for application in _react_applications(graph):
        sources = [application.identity, *(link.target for link in graph.hosts(application))]
        for source in sources:
            for link in graph.uses(source, "RelationalDatabase"):
                yield Hit(
                    f"The react application {application.name} uses the database "
                    f"{graph.elements[link.target].name}.",
                    link.location,
                    application.identity,
                )


# trace: PRD-DSML-030
@implements(XLY_005)
def xly_005(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    graph = _Graph(ir)
    for application in _react_applications(graph):
        calls = graph.links_from(application.identity, "calls")
        if not any(graph.kind(link.target) == "Application" for link in calls):
            yield Hit(location=application.location, element=application.identity)


# trace: PRD-DSML-027, PRD-DSML-039, PRD-DSML-040
@implements(XLY_006)
def xly_006(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    graph = _Graph(ir)
    for application in graph.of_kind("Application"):
        exposes_entities = any(
            graph.kind(identity) == "Entity"
            for element in graph.exposed(application)
            for identity in element.types
        )
        services = [
            link.target
            for link in graph.hosts(application)
            if graph.kind(link.target) == "ContainerService"
        ]
        if not exposes_entities or not services:
            continue  # XLY-001 and XLY-002 report a missing service.
        if not any(graph.uses(service, "RelationalDatabase") for service in services):
            yield Hit(location=application.location, element=application.identity)


# trace: PRD-DSML-033, PRD-DSML-039, PRD-DSML-040
@implements(XLY_007)
def xly_007(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    graph = _Graph(ir)
    for application in graph.of_kind("Application"):
        protected = any(not _is_public(element) for element in graph.exposed(application))
        hosts = [link.target for link in graph.hosts(application)]
        if not protected or not hosts:
            continue  # XLY-001 reports a missing service or site.
        if not any(graph.uses(host, "UserDirectory") for host in hosts):
            yield Hit(location=application.location, element=application.identity)


RULES = (xly_001, xly_002, xly_003, xly_004, xly_005, xly_006, xly_007)
"""The rules of this module."""
