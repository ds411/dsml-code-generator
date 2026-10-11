# trace: PRD-VAL-011, PRD-VAL-015, PRD-DSML-053
"""The rules of the category IDN: the identity of the elements.

The identity of an element is its short name, or its qualified name if it
has no short name (PRD-DSML-053, Q10). These rules compare the model with
the baseline model from Git. They run only when there is a baseline
(PRD-VAL-011).
"""

from collections import defaultdict
from collections.abc import Callable, Iterator, Mapping, Sequence

from dsml.config import Configuration
from dsml.ir.model import Element, Ir
from dsml.ir.writer import JsonValue, canonical_json, to_data
from dsml.validate.rule import Hit, Rule, compares

# trace: PRD-VAL-015
IDN_001 = Rule(
    id="IDN-001",
    severity="error",
    message="A short name that the baseline used for an element of a different kind is used again.",
    fix_hint="Give the element a new short name. Do not use a short name again for a different "
    "kind of element.",
)

# trace: PRD-VAL-015
IDN_002 = Rule(
    id="IDN-002",
    severity="info",
    message="An element with a short name has a different qualified name from the baseline.",
    fix_hint="No change is necessary. The short name keeps the identity of the element.",
)

# trace: PRD-VAL-015
IDN_003 = Rule(
    id="IDN-003",
    severity="warning",
    message="An element with no short name has a different qualified name from the baseline, "
    "so its trace identity changes.",
    fix_hint="Use the qualified name of the baseline again, or give the element a short name.",
)


def _by_short_name(ir: Ir) -> dict[str, list[Element]]:
    found: dict[str, list[Element]] = defaultdict(list)
    for element in ir.elements:
        if element.short_name is not None:
            found[element.short_name].append(element)
    return found


# trace: PRD-VAL-015, PRD-DSML-053
@compares(IDN_001)
def idn_001(ir: Ir, baseline: Ir, configuration: Configuration) -> Iterator[Hit]:
    """Find a short name that was the short name of a different kind of element."""
    before = _by_short_name(baseline)
    for element in ir.elements:
        if element.short_name is None or element.short_name not in before:
            continue
        kinds = sorted({item.kind for item in before[element.short_name]})
        if element.kind not in kinds:
            yield Hit(
                f'The short name "{element.short_name}" is the short name of a '
                f"{element.kind}. In the baseline, it was the short name of a "
                f"{' and a '.join(kinds)}.",
                element.location,
                element.identity,
            )


# trace: PRD-VAL-015, PRD-DSML-053
@compares(IDN_002)
def idn_002(ir: Ir, baseline: Ir, configuration: Configuration) -> Iterator[Hit]:
    """Find an element with a short name that has a different qualified name."""
    before = _by_short_name(baseline)
    for element in ir.elements:
        if element.short_name is None:
            continue
        old = sorted(
            item.qualified_name
            for item in before.get(element.short_name, ())
            if item.kind == element.kind
        )
        if old and element.qualified_name not in old:
            yield Hit(
                f'The qualified name of "{element.short_name}" is "{element.qualified_name}". '
                f'In the baseline, it was "{old[0]}".',
                element.location,
                element.identity,
            )


# trace: PRD-VAL-015, PRD-DSML-053
@compares(IDN_003)
def idn_003(ir: Ir, baseline: Ir, configuration: Configuration) -> Iterator[Hit]:
    """Find an element with no short name that has a different qualified name."""
    for element, old in renamed(ir, baseline):
        yield Hit(
            f'The qualified name of the {element.kind} "{element.qualified_name}" '
            f'was "{old.qualified_name}" in the baseline. Its identity changes.',
            element.location,
            element.identity,
        )


# trace: PRD-DSML-053
def renamed(ir: Ir, baseline: Ir) -> list[tuple[Element, Element]]:
    """Pair each element with no short name with its baseline element of a different identity.

    Only an element that is not in the baseline, and a baseline element that
    is not in the model, can be a pair. They must have the same kind. The
    function examines the elements in the order of their qualified names,
    owners first. A pair agrees with one of these conditions, in this order:

    1. The two elements have the same name, and the owners are a pair or
       have the same identity. Thus the element moved with its owner.
    2. The owners are a pair or have the same identity, and the two elements
       have the same contents. Thus the element has a new name.
    3. The two elements have the same name and the same contents. Thus the
       element moved to a different owner.

    A condition makes a pair only if it gives exactly one baseline element
    for the element, and exactly one element for this baseline element. Thus
    the function makes no pair when it is not sure.
    """
    now = {element.identity for element in ir.elements}
    then = {element.identity for element in baseline.elements}
    owners: dict[str | None, str | None] = {identity: identity for identity in now & then}
    owners[None] = None
    removed = [
        element
        for element in baseline.elements
        if element.short_name is None and element.identity not in now
    ]
    added = sorted(
        (
            element
            for element in ir.elements
            if element.short_name is None and element.identity not in then
        ),
        key=lambda element: (len(element.qualified_name), element.qualified_name),
    )
    pairs: list[tuple[Element, Element]] = []
    for element in list(added):
        old = _match(element, removed, added, owners)
        if old is not None:
            removed.remove(old)
            added.remove(element)
            owners[old.identity] = element.identity
            pairs.append((element, old))
    return sorted(pairs, key=lambda pair: pair[0].sort_key())


type _Condition = Callable[[Element, Element, Mapping[str | None, str | None]], bool]

_CONDITIONS: tuple[_Condition, ...] = (
    lambda old, new, owners: old.name == new.name and _owned(old, new, owners),
    lambda old, new, owners: _owned(old, new, owners) and _contents(old) == _contents(new),
    lambda old, new, owners: old.name == new.name and _contents(old) == _contents(new),
)
"""The conditions of a pair of a baseline element and an element, in their order."""


def _match(
    element: Element,
    removed: Sequence[Element],
    added: Sequence[Element],
    owners: Mapping[str | None, str | None],
) -> Element | None:
    for condition in _CONDITIONS:
        found = [
            old for old in removed if old.kind == element.kind and condition(old, element, owners)
        ]
        if len(found) != 1:
            continue
        others = [
            new for new in added if new.kind == element.kind and condition(found[0], new, owners)
        ]
        return found[0] if others == [element] else None
    return None


def _owned(old: Element, element: Element, owners: Mapping[str | None, str | None]) -> bool:
    return old.owner in owners and owners[old.owner] == element.owner


_NAME_KEYS = frozenset({"identity", "location", "name", "owner", "qualifiedName"})


def _contents(element: Element) -> bytes:
    """Give the canonical JSON of the element with no name, owner or source location."""
    kept = {key: value for key, value in to_data(element).items() if key not in _NAME_KEYS}
    return canonical_json(_without_locations(kept))


def _without_locations(data: JsonValue) -> JsonValue:
    match data:
        case dict():
            return {
                key: _without_locations(value) for key, value in data.items() if key != "location"
            }
        case list():
            return [_without_locations(item) for item in data]
        case _:
            return data


RULES = (idn_001, idn_002, idn_003)
"""The rules of this module."""
