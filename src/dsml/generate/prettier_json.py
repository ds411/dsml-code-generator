# trace: PRD-CORE-028, PRD-CORE-031, PRD-CORE-034
"""A JSON writer that gives the Prettier format of a TypeScript project.

The CI job "Next.js golden project" and the script `format` of a generated
Next.js project run `prettier --check` on all files. Thus a generated JSON
file must have the Prettier format. The writer applies these rules of
Prettier for JSON, with the print width 80 and two spaces of indent:

- A non-empty object has one key on each line, because Prettier keeps an
  object on many lines when the source has a line break after `{`.
- An array that contains a non-empty object or a non-empty array has one
  item on each line.
- An array of scalar values is on one line if that line has 80 characters
  or fewer. If not, each item is on its own line.

The keys are in sorted order (PRD-CORE-031). The text is UTF-8 with LF line
ends and one LF at the end (PRD-CORE-028, PRD-CORE-034).
"""

import json
from typing import Final

from dsml.ir.writer import JsonValue

PRINT_WIDTH: Final = 80
"""The print width of Prettier."""

_INDENT: Final = "  "


# trace: PRD-CORE-028, PRD-CORE-031, PRD-CORE-034
def prettier_json(data: JsonValue) -> bytes:
    """Write JSON data in the Prettier format, with sorted keys."""
    return f"{_value(data, '', '', '')}\n".encode()


def _scalar(value: JsonValue) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _value(value: JsonValue, indent: str, head: str, tail: str) -> str:
    """Give the text of a value.

    The value starts after the text `head` on a line with the indent
    `indent`. The text `tail` follows the value on the same line, for
    example a comma.
    """
    if isinstance(value, dict):
        if not value:
            return "{}"
        inner = indent + _INDENT
        lines = [
            inner
            + f"{_scalar(key)}: "
            + _value(value[key], inner, f"{_scalar(key)}: ", "," if index < len(value) - 1 else "")
            + ("," if index < len(value) - 1 else "")
            for index, key in enumerate(sorted(value))
        ]
        return "{\n" + "\n".join(lines) + f"\n{indent}}}"
    if isinstance(value, list):
        if not value:
            return "[]"
        if all(not isinstance(item, (dict, list)) or not item for item in value):
            line = "[" + ", ".join(_value(item, indent, "", "") for item in value) + "]"
            if len(indent) + len(head) + len(line) + len(tail) <= PRINT_WIDTH:
                return line
        inner = indent + _INDENT
        lines = [
            inner
            + _value(item, inner, "", "," if index < len(value) - 1 else "")
            + ("," if index < len(value) - 1 else "")
            for index, item in enumerate(value)
        ]
        return "[\n" + "\n".join(lines) + f"\n{indent}]"
    return _scalar(value)
