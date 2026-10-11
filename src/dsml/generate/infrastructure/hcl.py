# trace: PRD-TRACE-006, PRD-TRACE-007
"""Small parts of HCL text: string literals and the symbols of the top-level blocks."""

import re
from collections.abc import Callable

from dsml.generate.trace import Symbol, SymbolKind

_BLOCK = re.compile(r'([a-z_]+)((?: "[^"]+")*) \{$')
_ADDRESS_PREFIX = {
    "data": "data.",
    "module": "module.",
    "output": "output.",
    "provider": "provider.",
    "variable": "var.",
}


# trace: PRD-IAC-003
def string(value: str) -> str:
    """Give an HCL string literal with the value.

    The function escapes the characters that have a special meaning in an
    HCL string, and the template sequences `${` and `%{`.
    """
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("${", "$${")
        .replace("%{", "%%{")
    )
    return f'"{escaped}"'


def address(line: str) -> str | None:
    """Give the address of the top-level block that starts on a line, or None.

    For example, `resource "aws_vpc" "main" {` gives `aws_vpc.main`,
    `variable "model_commit" {` gives `var.model_commit` and `terraform {`
    gives `terraform`.
    """
    match = _BLOCK.fullmatch(line)
    if match is None:
        return None
    block_type = match.group(1)
    labels = [label.strip('"') for label in match.group(2).split()]
    if not labels:
        return block_type
    if block_type == "resource":
        return ".".join(labels)
    return _ADDRESS_PREFIX.get(block_type, f"{block_type}.") + ".".join(labels)


# trace: PRD-TRACE-006, PRD-TRACE-007
def block_symbols(text: str, elements: Callable[[str], tuple[str, ...]]) -> tuple[Symbol, ...]:
    """Give a symbol of the kind `resource` for each top-level block of HCL text.

    The text must have the format of `tofu fmt`: a top-level block starts at
    the start of a line and ends at the next line that is "}". `elements`
    gives the identities of the model elements of a block address. A block
    with no element gets no symbol.
    """
    symbols: list[Symbol] = []
    first: int | None = None
    name = ""
    for number, line in enumerate(text.split("\n"), start=1):
        if first is None:
            found = address(line)
            if found is not None:
                first, name = number, found
        elif line == "}":
            identities = elements(name)
            if identities:
                symbols.append(Symbol(SymbolKind.RESOURCE, name, first, number, identities))
            first = None
    if first is not None:
        raise ValueError(f'The HCL block "{name}" on line {first} has no end.')
    return tuple(symbols)
