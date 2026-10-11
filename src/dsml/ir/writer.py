# trace: PRD-CORE-022, PRD-CORE-028, PRD-CORE-031, PRD-CORE-033, PRD-CORE-034
"""The canonical JSON writer of the IR.

The same IR gives the same bytes on each platform:

- Object keys are in sorted order.
- The writer sorts each list with the order `SORTED` (see `dsml.ir.model`):
  objects by `sort_key()` (element identity, then name, for elements), then by
  their canonical JSON text. A list with the order `MODEL` keeps its order.
- The text is UTF-8 with no byte order mark, LF line ends and one LF at the
  end. The writer does not escape characters that are not ASCII.

The writer accepts only IR models and JSON values. Thus no OpenSysML object
can get into the IR (PRD-CORE-025).
"""

import json
import math
import re
from dataclasses import fields
from typing import cast

from dsml.ir.model import MODEL, ORDER, SORTED, Ir, Node, Value

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None

_UPPER_AFTER_UNDERSCORE = re.compile(r"_([a-z])")


def json_key(field_name: str) -> str:
    """Give the JSON key of a field name, for example `qualifiedName`."""
    return _UPPER_AFTER_UNDERSCORE.sub(lambda match: match.group(1).upper(), field_name)


# trace: PRD-CORE-022, PRD-CORE-031
def to_data(node: Node) -> dict[str, JsonValue]:
    """Convert an IR model to JSON data, with all lists in canonical order."""
    return _node_data(node)


# trace: PRD-CORE-028, PRD-CORE-034
def canonical_json(data: JsonValue) -> bytes:
    """Write JSON data as canonical bytes.

    Object keys are in sorted order. The text is UTF-8 with no byte order mark,
    LF line ends and one LF at the end.
    """
    text = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
    return f"{text}\n".encode()


# trace: PRD-CORE-022, PRD-CORE-028, PRD-CORE-031
def write_ir(ir: Ir) -> bytes:
    """Write the IR as canonical JSON bytes."""
    return canonical_json(to_data(ir))


def _node_data(node: Node) -> dict[str, JsonValue]:
    data: dict[str, JsonValue] = {}
    if isinstance(node, Value):
        data["type"] = node.TYPE
    for item in fields(node):
        value: object = getattr(node, item.name)
        if isinstance(value, tuple):
            order = item.metadata.get(ORDER)
            if order not in (SORTED, MODEL):
                raise TypeError(f"The list field {type(node).__name__}.{item.name} has no order.")
            items = cast(tuple[object, ...], value)
            data[json_key(item.name)] = _list_data(items, order == SORTED)
        else:
            data[json_key(item.name)] = _value_data(value)
    return data


def _list_data(items: tuple[object, ...], sort: bool) -> list[JsonValue]:
    if not sort:
        return [_value_data(item) for item in items]
    if all(isinstance(item, str) for item in items):
        return list[JsonValue](sorted(cast(tuple[str, ...], items)))
    keyed: list[tuple[tuple[str | int, ...], bytes, JsonValue]] = []
    for item in items:
        if not isinstance(item, Node):
            raise TypeError(f"A sorted list must hold only texts or only IR models: {item!r}")
        data = _node_data(item)
        keyed.append((item.sort_key(), canonical_json(data), data))
    keyed.sort(key=lambda entry: (entry[0], entry[1]))
    return [data for _, _, data in keyed]


def _value_data(value: object) -> JsonValue:
    match value:
        case None | bool() | str():
            return value
        case int():
            return value
        case float():
            if not math.isfinite(value):
                raise ValueError(f"The IR must not contain the real value {value}.")
            return value
        case Node():
            return _node_data(value)
        case _:
            raise TypeError(f"The IR must not contain an object of type {type(value).__name__}.")
