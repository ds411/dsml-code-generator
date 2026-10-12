# trace: PRD-TRACE-006
"""The symbols of a generated TypeScript file for the trace manifest.

The function `typescript_symbols` reads the text of a generated TypeScript
file that has the Prettier format. It gives one symbol for each top-level
declaration: a function, a class, an interface, a type or a constant. A
top-level declaration starts in the first column of a line, with or with
no `export`.

- A function declaration gives a symbol of the kind `function`.
- A class, an interface, a type or a constant gives a symbol of the kind
  `class`. For example, a Zod schema is a constant that gives the type of
  a value.

The line range of a symbol starts at the line of the declaration and stops
at the last line before the next top-level statement or comment. The
range does not include blank lines at its end.
"""

import re
from collections.abc import Mapping
from typing import Final

from dsml.generate.trace import Symbol, SymbolKind

_DECLARATION: Final = re.compile(
    r"^(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:async\s+)?"
    r"(function|class|interface|type|const|let|var)\*?\s+([A-Za-z_$][A-Za-z0-9_$]*)"
)
"""The start of a top-level declaration and its name."""

_CONTINUATION: Final = ("}", ")", "]")
"""The first characters of a line in the first column that continues a statement."""


# trace: PRD-TRACE-006
def typescript_symbols(
    content: bytes,
    elements: tuple[str, ...],
    symbol_elements: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[Symbol, ...]:
    """Give the symbols of the top-level declarations of TypeScript text.

    `elements` are the element identities of each symbol. `symbol_elements`
    gives other identities for the symbols with these names. The symbols are
    in the order of the file.
    """
    lines = content.decode("utf-8").split("\n")
    starts = [
        index
        for index, line in enumerate(lines)
        if line and not line[0].isspace() and not line.startswith(_CONTINUATION)
    ]
    symbols: list[Symbol] = []
    for position, start in enumerate(starts):
        match = _DECLARATION.match(lines[start])
        if match is None:
            continue
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        last = end - 1
        while last > start and not lines[last].strip():
            last -= 1
        keyword, name = match.groups()
        kind = SymbolKind.FUNCTION if keyword == "function" else SymbolKind.CLASS
        identities = (symbol_elements or {}).get(name, elements)
        symbols.append(Symbol(kind, name, start + 1, last + 1, identities))
    return tuple(symbols)
