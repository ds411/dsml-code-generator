# trace: PRD-IAC-008, PRD-APP-120
"""Safe names for generated code.

Each function divides a model name into words, then joins the words in the
form of the target. Each character that is not an ASCII letter or digit
divides two words. A change from a lowercase letter to an uppercase letter
also divides two words, for example `OrderService` gives `order` and
`service`.

The result is a name that the target language accepts. If a name starts
with a digit or has no letter or digit, the function gives an error.
"""

import keyword
import re

_WORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z0-9]+")
_SEPARATOR = re.compile(r"[^A-Za-z0-9]+")


def words(name: str) -> list[str]:
    """Divide a name into its words, in lowercase."""
    found = [word.lower() for part in _SEPARATOR.split(name) for word in _WORD.findall(part)]
    if not found:
        raise ValueError(f"The name {name!r} has no letter or digit.")
    if found[0][0].isdecimal():
        raise ValueError(f"The name {name!r} must not start with a digit.")
    return found


def snake_case(name: str) -> str:
    """Give the name in snake case, for example `order_service`."""
    return "_".join(words(name))


def kebab_case(name: str) -> str:
    """Give the name in kebab case, for example `order-service`."""
    return "-".join(words(name))


def pascal_case(name: str) -> str:
    """Give the name in Pascal case, for example `OrderService`."""
    return "".join(word.capitalize() for word in words(name))


def camel_case(name: str) -> str:
    """Give the name in camel case, for example `orderService`."""
    first, *rest = words(name)
    return first + "".join(word.capitalize() for word in rest)


def python_name(name: str) -> str:
    """Give a Python name in snake case. Add `_` to a Python keyword, for example `class_`."""
    result = snake_case(name)
    if keyword.iskeyword(result) or keyword.issoftkeyword(result):
        return f"{result}_"
    return result
