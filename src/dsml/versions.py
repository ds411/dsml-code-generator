"""Read the version baseline of the toolchain from `versions.toml`."""

import tomllib
from dataclasses import dataclass
from importlib import resources
from typing import Any

BASELINE_FILE = "versions.toml"
SCHEMA = 1
_ITEM_KEYS = frozenset({"line", "version", "value"})


class BaselineError(Exception):
    """The version baseline is not correct."""


@dataclass(frozen=True, slots=True)
class Pin:
    """One item of the version baseline."""

    name: str
    line: str | None = None
    version: str | None = None
    value: str | None = None


# trace: PRD-CORE-018, PRD-TOP-008
def load_baseline(text: str | None = None) -> dict[str, Pin]:
    """Read the version baseline, sorted by item name.

    Without `text`, the function reads the `versions.toml` file of the package.
    """
    if text is None:
        text = resources.files("dsml").joinpath(BASELINE_FILE).read_text(encoding="utf-8")
    data = tomllib.loads(text)
    if data.get("schema") != SCHEMA:
        raise BaselineError(f"The version baseline must have schema = {SCHEMA}.")
    pins = [_read_item(name, item) for name, item in data.items() if name != "schema"]
    return {pin.name: pin for pin in sorted(pins, key=lambda pin: pin.name)}


def _read_item(name: str, item: Any) -> Pin:
    if not isinstance(item, dict) or not item:
        raise BaselineError(f'Item "{name}" must be a table with "line", "version" or "value".')
    unknown = sorted(set(item) - _ITEM_KEYS)
    if unknown:
        raise BaselineError(f'Item "{name}" has an unknown key: {", ".join(unknown)}.')
    for key, value in item.items():
        if not isinstance(value, str) or not value:
            raise BaselineError(
                f'The key "{key}" of item "{name}" must be a text that is not empty.'
            )
    pin = Pin(name=name, **item)
    if pin.line and pin.version and not _in_line(pin.version, pin.line):
        raise BaselineError(
            f'The version {pin.version} of item "{name}" is not in the line {pin.line}.'
        )
    return pin


def _in_line(version: str, line: str) -> bool:
    return version == line or version.startswith(f"{line}.")


# trace: PRD-CORE-018
def pinned_version(name: str, baseline: dict[str, Pin] | None = None) -> str:
    """Give the exact version of one item of the version baseline."""
    pins = load_baseline() if baseline is None else baseline
    pin = pins.get(name)
    if pin is None:
        raise BaselineError(f'The version baseline has no item "{name}".')
    if pin.version is None:
        raise BaselineError(f'The version baseline has no exact version for item "{name}".')
    return pin.version
