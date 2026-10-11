# trace: PRD-TRACE-006, PRD-TRACE-007, PRD-TRACE-008, PRD-CORE-028
"""The trace manifest `.dsml/trace.gen.json`.

Each generator gives the symbols of its generated files: a class, a
function, a route or an HCL resource address. Each symbol has a line range
and the identities of its model elements. The file writer collects the
symbols and writes the trace manifest. For each element, the manifest gives
each generated file and each symbol in that file (PRD-TRACE-006). The HCL
resource addresses of an infrastructure element are its symbols of the kind
`resource` (PRD-TRACE-007).

The manifest is sorted by element identity, then by file path, then by line
(PRD-TRACE-008). It is canonical JSON, like the manifest
`.dsml/generated.json` (PRD-CORE-028, PRD-CORE-034).
"""

import enum
import json
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from dsml.errors import ToolchainError
from dsml.ir.writer import JsonValue, canonical_json

TRACE_PATH: Final = ".dsml/trace.gen.json"
"""The path of the trace manifest, relative to the folder of the configuration file."""

TRACE_VERSION: Final = 1
"""The version of the trace manifest format that this toolchain reads and writes."""


# trace: PRD-TRACE-006, PRD-TRACE-007
class SymbolKind(enum.StrEnum):
    """The kind of a symbol in a generated file."""

    CLASS = "class"
    FUNCTION = "function"
    ROUTE = "route"
    """An HTTP route. The name is the method and the path, for example `POST /orders`."""
    RESOURCE = "resource"
    """An HCL resource address, for example `aws_ecs_service.order_api`."""


# trace: PRD-TRACE-006
@dataclass(frozen=True, slots=True)
class Symbol:
    """One symbol in a generated file.

    The lines are 1-based and include the first and the last line. The
    elements are the identities of the model elements of the symbol.
    """

    kind: SymbolKind
    name: str
    first_line: int
    last_line: int
    elements: tuple[str, ...]


# trace: PRD-TRACE-006
@dataclass(frozen=True, slots=True)
class TraceEntry:
    """One symbol of one element in one generated file."""

    element: str
    path: str
    kind: SymbolKind
    name: str
    first_line: int
    last_line: int


def _sort_key(entry: TraceEntry) -> tuple[str, str, int, int, str, str]:
    return (
        entry.element,
        entry.path,
        entry.first_line,
        entry.last_line,
        entry.kind.value,
        entry.name,
    )


# trace: PRD-TRACE-006
def trace_entries(path: str, symbols: Iterable[Symbol]) -> list[TraceEntry]:
    """Give one entry for each element of each symbol of a file."""
    return [
        TraceEntry(
            element=element,
            path=path,
            kind=symbol.kind,
            name=symbol.name,
            first_line=symbol.first_line,
            last_line=symbol.last_line,
        )
        for symbol in symbols
        for element in sorted(set(symbol.elements))
    ]


# trace: PRD-TRACE-006, PRD-TRACE-008, PRD-CORE-028
def trace_bytes(entries: Iterable[TraceEntry]) -> bytes:
    """Write the trace manifest as canonical JSON bytes.

    The function sorts the entries by element identity, then by file path,
    then by line (PRD-TRACE-008). It removes duplicate entries.
    """
    elements: list[JsonValue] = []
    current_element: dict[str, JsonValue] | None = None
    current_files: list[JsonValue] = []
    current_path: str | None = None
    current_symbols: list[JsonValue] = []
    for entry in sorted(set(entries), key=_sort_key):
        if current_element is None or current_element["element"] != entry.element:
            current_files = []
            current_element = {"element": entry.element, "files": current_files}
            elements.append(current_element)
            current_path = None
        if current_path != entry.path:
            current_symbols = []
            current_files.append({"path": entry.path, "symbols": current_symbols})
            current_path = entry.path
        current_symbols.append(
            {
                "firstLine": entry.first_line,
                "kind": entry.kind.value,
                "lastLine": entry.last_line,
                "name": entry.name,
            }
        )
    return canonical_json({"elements": elements, "traceVersion": TRACE_VERSION})


# trace: PRD-TRACE-006
def check_symbols(path: str, symbols: Sequence[Symbol], line_count: int) -> list[str]:
    """Give the errors of the symbols of one generated file, or an empty list."""
    errors: list[str] = []
    for symbol in symbols:
        if not _is_text(symbol.name):
            errors.append(f'The file "{path}" has a symbol with the name {symbol.name!r}.')
            continue
        where = f'The symbol "{symbol.name}" of the file "{path}"'
        if not 1 <= symbol.first_line <= symbol.last_line <= line_count:
            errors.append(
                f"{where} has the lines {symbol.first_line} to {symbol.last_line}. "
                f"The lines must be in the range 1 to {line_count}, in their order."
            )
        if not symbol.elements:
            errors.append(f"{where} has no element.")
        for element in symbol.elements:
            if not _is_text(element):
                errors.append(f"{where} has the element identity {element!r}.")
    return errors


def _is_text(text: str) -> bool:
    """Tell if a name is not empty, has no line break and no space at its ends."""
    return bool(text) and text == text.strip() and "\n" not in text and "\r" not in text


# trace: PRD-TRACE-006
def read_trace(root: Path) -> list[TraceEntry]:
    """Read the trace manifest in the folder `root`.

    If there is no trace manifest, the function gives an empty list. A trace
    manifest that is not correct stops the command with exit code 2.
    """
    path = root / TRACE_PATH
    try:
        text = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        return []
    except OSError as error:
        raise ToolchainError(
            f"Cannot read the trace manifest {TRACE_PATH}: {error.strerror}."
        ) from None
    except UnicodeDecodeError:
        raise _error("It does not have UTF-8 encoding.") from None
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as error:
        raise _error(
            f"It is not correct JSON: {error.msg} at line {error.lineno}, column {error.colno}."
        ) from None
    return _parse(data)


def _parse(data: object) -> list[TraceEntry]:
    top = _object(data, {"elements", "traceVersion"}, "The top level")
    version = top["traceVersion"]
    if type(version) is not int or version != TRACE_VERSION:
        raise _error(
            f"The trace manifest version {version!r} is unknown. "
            f"This toolchain reads trace manifest version {TRACE_VERSION}."
        )
    entries: list[TraceEntry] = []
    for element_item in _list(top["elements"], "elements"):
        element_data = _object(element_item, {"element", "files"}, 'Each item of "elements"')
        element = _text(element_data["element"], "element")
        for file_item in _list(element_data["files"], "files"):
            file_data = _object(file_item, {"path", "symbols"}, 'Each item of "files"')
            path = _text(file_data["path"], "path")
            for symbol_item in _list(file_data["symbols"], "symbols"):
                symbol = _object(
                    symbol_item,
                    {"firstLine", "kind", "lastLine", "name"},
                    'Each item of "symbols"',
                )
                kind = _text(symbol["kind"], "kind")
                if kind not in SymbolKind:
                    raise _error(f'The symbol kind "{kind}" is unknown.')
                entries.append(
                    TraceEntry(
                        element=element,
                        path=path,
                        kind=SymbolKind(kind),
                        name=_text(symbol["name"], "name"),
                        first_line=_line(symbol["firstLine"], "firstLine"),
                        last_line=_line(symbol["lastLine"], "lastLine"),
                    )
                )
    return entries


def _object(value: object, keys: Collection[str], what: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(cast(dict[str, object], value)) != set(keys):
        names = ", ".join(f'"{name}"' for name in sorted(keys))
        raise _error(f"{what} must be a JSON object with the keys {names}.")
    return cast(dict[str, object], value)


def _list(value: object, key: str) -> list[object]:
    if not isinstance(value, list):
        raise _error(f'The key "{key}" must be a list.')
    return cast(list[object], value)


def _text(value: object, key: str) -> str:
    if not isinstance(value, str) or not value:
        raise _error(f'The key "{key}" must be a text that is not empty.')
    return value


def _line(value: object, key: str) -> int:
    if type(value) is not int or value < 1:
        raise _error(f'The key "{key}" must be a line number of 1 or more.')
    return value


def _error(message: str) -> ToolchainError:
    return ToolchainError(
        f"The trace manifest {TRACE_PATH} is not correct. {message} "
        "Generate all parts to write it again."
    )
