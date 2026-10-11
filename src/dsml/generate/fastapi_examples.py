# trace: PRD-APP-112, PRD-APP-113, PRD-APP-114
"""Test values for the generated HTTP tests of the FastAPI target.

The HTTP tests of a CRUD slice need rows with correct values, and values
that break the field rules. The functions of this module make these values
from the type and the field rules of each field. They do not use random
values, thus the generated tests are the same at each run (PRD-CORE-028).

A value is a JSON value: a text, a number, a Boolean value or `None`. A
`Decimal` field gets a text with the digits of its scale, for example
`"0.50"`. A `Date` field and a `DateTime` field get a text in the ISO 8601
form, and a `Uuid` field gets a UUID text.

The function `pattern_example` makes a text that agrees with a regular
expression. It knows only a part of the regular expression syntax: literal
characters, character classes, `.`, the escapes `\\d`, `\\w` and `\\s`,
groups, alternatives, anchors and the quantifiers `?`, `*`, `+` and
`{m,n}`. For other syntax, it gives `None`. Then the generator cannot make
the test values, and the test file tells why.
"""

import json
import math
import re
import string
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Final

ROWS: Final = 3
"""The number of rows of the tests of an entity."""

UNKNOWN_INDEX: Final = 99
"""The index of the key value that no row of the tests has."""

_DIGITS: Final = string.digits
_LETTERS: Final = string.ascii_lowercase
_WORD: Final = string.ascii_lowercase + string.digits + string.ascii_uppercase + "_"
_PRINTABLE: Final = string.ascii_letters + string.digits + "-_.@ "
_START_DATE: Final = date(2026, 1, 1)


# trace: PRD-APP-112
@dataclass(frozen=True, slots=True)
class Rules:
    """The DSML type and the field rules of one field (PRD-DSML-025)."""

    kind: str
    """The DSML field type, for example `String`, or `Enumeration`."""
    min_length: int | None = None
    max_length: int | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    pattern: str | None = None
    precision: int | None = None
    scale: int | None = None
    values: tuple[str, ...] = ()
    """The values of an enumeration."""


@dataclass(frozen=True, slots=True)
class Invalid:
    """A value that breaks one field rule. `rule` is the name of the rule."""

    rule: str
    expression: str
    """The Python expression of the value."""


def literal(value: object) -> str:
    """Give the Python expression of a JSON value in the form of `ruff format`."""
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"The value {value!r} is not a JSON value.")


# trace: PRD-APP-112
def sample(rules: Rules, index: int) -> object | None:
    """Give a correct value of a field for the row `index`, or `None` if there is none.

    Two rows with different indexes get different values, if the type and
    the rules permit it.
    """
    match rules.kind:
        case "String":
            return _text(rules, index)
        case "Integer":
            return _integer(rules, index)
        case "Real":
            value = _number(rules, index)
            return None if value is None else float(value)
        case "Decimal":
            return _decimal(rules, index)
        case "Boolean":
            return index % 2 == 0
        case "Date":
            return (_START_DATE + timedelta(days=index)).isoformat()
        case "DateTime":
            day = _START_DATE + timedelta(days=index // 24)
            return f"{day.isoformat()}T{index % 24:02d}:00:00Z"
        case "Uuid":
            return f"00000000-0000-4000-8000-{index + 1:012d}"
        case "Enumeration":
            return rules.values[index % len(rules.values)] if rules.values else None
        case _:
            return None


# trace: PRD-APP-112, PRD-APP-113
def invalid_values(rules: Rules) -> list[Invalid]:
    """Give one value for each field rule that the value breaks."""
    result: list[Invalid] = []
    if rules.kind == "String":
        if rules.min_length is not None and rules.min_length > 0:
            result.append(Invalid("minLength", _repeat(rules.min_length - 1)))
        if rules.max_length is not None:
            result.append(Invalid("maxLength", _repeat(rules.max_length + 1)))
        if rules.pattern is not None:
            pattern = _compile(rules.pattern)
            found = next(
                (text for text in ("", "!", "-", " ") if pattern and not pattern.search(text)),
                None,
            )
            if found is not None:
                result.append(Invalid("pattern", literal(found)))
    elif rules.kind in ("Integer", "Real", "Decimal"):
        if rules.min_value is not None:
            result.append(Invalid("minValue", _out_of_range(rules, rules.min_value, -1)))
        if rules.max_value is not None:
            result.append(Invalid("maxValue", _out_of_range(rules, rules.max_value, 1)))
    return result


def _repeat(count: int) -> str:
    """Give the expression of a text of `count` characters."""
    if count <= 20:
        return literal("x" * count)
    return f'"x" * {count}'


def _out_of_range(rules: Rules, limit: float, sign: int) -> str:
    if rules.kind == "Integer":
        value = math.ceil(limit) - 1 if sign < 0 else math.floor(limit) + 1
        return literal(value)
    number = Decimal(str(limit)) + sign
    if rules.kind == "Real":
        return literal(float(number))
    return literal(_decimal_text(number, rules.scale))


def _text(rules: Rules, index: int) -> str | None:
    minimum = rules.min_length or 0
    maximum = rules.max_length
    if rules.pattern is not None:
        text = pattern_example(rules.pattern, index)
        if text is None:
            return None
    else:
        text = f"v{index}"
        text += "x" * max(0, minimum - len(text))
        if maximum is not None and len(text) > maximum:
            text = str(index)[-maximum:] if maximum > 0 else ""
    if len(text) < minimum or (maximum is not None and len(text) > maximum):
        return None
    return text


def _number(rules: Rules, index: int) -> Decimal | None:
    low = None if rules.min_value is None else Decimal(str(rules.min_value))
    high = None if rules.max_value is None else Decimal(str(rules.max_value))
    step = Decimal(index + 1)
    if low is not None and high is not None:
        value = low + (high - low) * step / (ROWS + 1)
    elif low is not None:
        value = low + step - Decimal("0.5")
    elif high is not None:
        value = high - step + Decimal("0.5")
    else:
        value = step - Decimal("0.5")
    return value if _in_range(value, low, high) else None


def _integer(rules: Rules, index: int) -> int | None:
    low = None if rules.min_value is None else math.ceil(rules.min_value)
    high = None if rules.max_value is None else math.floor(rules.max_value)
    if low is not None:
        value = low + index
    elif high is not None:
        value = high - index
    else:
        value = index + 1
    return value if (high is None or value <= high) and (low is None or value >= low) else None


def _decimal(rules: Rules, index: int) -> str | None:
    value = _number(rules, index)
    if value is None:
        return None
    text = _decimal_text(value, rules.scale)
    number = Decimal(text)
    low = None if rules.min_value is None else Decimal(str(rules.min_value))
    high = None if rules.max_value is None else Decimal(str(rules.max_value))
    if not _in_range(number, low, high):
        return None
    if rules.precision is not None:
        digits = len(number.as_tuple().digits)
        exponent = number.as_tuple().exponent
        whole = digits + exponent if isinstance(exponent, int) else digits
        if whole > rules.precision - (rules.scale or 0):
            return None
    return text


def _decimal_text(value: Decimal, scale: int | None) -> str:
    places = Decimal(1).scaleb(-(scale or 0))
    return str(value.quantize(places, rounding=ROUND_HALF_EVEN))


def _in_range(value: Decimal, low: Decimal | None, high: Decimal | None) -> bool:
    return (low is None or value >= low) and (high is None or value <= high)


def _compile(pattern: str) -> re.Pattern[str] | None:
    try:
        return re.compile(pattern)
    except re.error:
        return None


# trace: PRD-APP-112
def pattern_example(pattern: str, variant: int = 0) -> str | None:
    """Give a text that agrees with a regular expression, or `None`.

    `variant` selects a different character at each choice, thus two
    variants give different texts if the expression has a choice. The
    result agrees with the expression: `re.search` finds it.
    """
    compiled = _compile(pattern)
    if compiled is None:
        return None
    try:
        parser = _Parser(pattern, variant)
        text = parser.alternatives()
        if parser.position != len(pattern):
            return None
    except _Unsupported:
        return None
    return text if compiled.search(text) else None


class _Unsupported(Exception):
    """The expression uses a syntax that `pattern_example` does not know."""


class _Parser:
    """A recursive descent parser that writes one example text of an expression."""

    def __init__(self, pattern: str, variant: int) -> None:
        self.pattern = pattern
        self.variant = variant
        self.position = 0

    def _peek(self) -> str | None:
        return self.pattern[self.position] if self.position < len(self.pattern) else None

    def _next(self) -> str:
        character = self._peek()
        if character is None:
            raise _Unsupported
        self.position += 1
        return character

    def _choose(self, characters: str) -> str:
        if not characters:
            raise _Unsupported
        return characters[self.variant % len(characters)]

    def alternatives(self) -> str:
        first = self._sequence()
        while self._peek() == "|":
            self.position += 1
            self._sequence()
        return first

    def _sequence(self) -> str:
        parts: list[str] = []
        while (character := self._peek()) is not None and character not in "|)":
            atom = self._atom()
            count = self._quantifier()
            parts.append(atom if count == 1 else "".join(atom for _ in range(count)))
        return "".join(parts)

    def _atom(self) -> str:
        character = self._next()
        if character in "^$":
            return ""
        if character == ".":
            return self._choose(_LETTERS)
        if character == "(":
            if self._peek() == "?":
                self.position += 1
                if self._next() != ":":
                    raise _Unsupported
            text = self.alternatives()
            if self._next() != ")":
                raise _Unsupported
            return text
        if character == "[":
            return self._choose(self._class())
        if character == "\\":
            return self._choose(self._escape())
        if character in "*+?{":
            raise _Unsupported
        return character

    def _escape(self) -> str:
        character = self._next()
        classes = {"d": _DIGITS, "w": _WORD, "s": " "}
        if character in classes:
            return classes[character]
        if character in "DWS":
            excluded = classes[character.lower()]
            return "".join(item for item in _PRINTABLE if item not in excluded)
        if character.isalnum():
            raise _Unsupported
        return character

    def _class(self) -> str:
        negated = self._peek() == "^"
        if negated:
            self.position += 1
        members: list[str] = []
        first = True
        while True:
            character = self._next()
            if character == "]" and not first:
                break
            first = False
            if character == "\\":
                members.extend(self._escape())
                continue
            if self._peek() == "-" and self.position + 1 < len(self.pattern):
                end = self.pattern[self.position + 1]
                if end != "]":
                    self.position += 2
                    if end == "\\" or ord(end) < ord(character):
                        raise _Unsupported
                    members.extend(chr(code) for code in range(ord(character), ord(end) + 1))
                    continue
            members.append(character)
        if negated:
            return "".join(item for item in _PRINTABLE if item not in members)
        return "".join(dict.fromkeys(members))

    def _quantifier(self) -> int:
        character = self._peek()
        if character in ("?", "*"):
            self.position += 1
            count = 0
        elif character == "+":
            self.position += 1
            count = 1
        elif character == "{":
            end = self.pattern.find("}", self.position)
            match = re.fullmatch(r"(\d+)(,\d*)?", self.pattern[self.position + 1 : end])
            if end < 0 or match is None:
                raise _Unsupported
            self.position = end + 1
            count = int(match.group(1))
        else:
            return 1
        if self._peek() in ("?", "+"):
            raise _Unsupported
        return count
