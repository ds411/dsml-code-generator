# trace: PRD-CICD-014, PRD-TRACE-006
"""Small parts of GitHub Actions workflows: strings, pinned actions and job symbols."""

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate.trace import Symbol, SymbolKind
from dsml.versions import Pin

EXPRESSION_START: Final = "${{"
"""The start of a GitHub Actions expression."""

_JOB = re.compile(r"  ([A-Za-z_][A-Za-z0-9_-]*):$")
_SHA = re.compile(r"[0-9a-f]{40}")
_ACTION = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./-]+)?")


# trace: PRD-CICD-001
def yaml_string(value: str) -> str:
    """Give a YAML string literal in double quotes with the value.

    A JSON string is also a correct YAML string in double quotes. GitHub
    Actions reads an expression `${{ ... }}` in each string. Thus a value
    from the model or the configuration must not contain `${{`.
    """
    if EXPRESSION_START in value:
        raise ToolchainError(
            f"The value {value!r} contains {EXPRESSION_START!r}. "
            "A workflow value must not contain a GitHub Actions expression."
        )
    return json.dumps(value, ensure_ascii=False)


# trace: PRD-CICD-014
@dataclass(frozen=True, slots=True)
class Action:
    """A third-party action, pinned to a full commit SHA."""

    name: str
    """The action, for example `actions/checkout`."""
    sha: str
    """The full commit SHA of the release tag: 40 hexadecimal characters."""
    version: str
    """The release tag without "v", for example `7.0.1`."""

    @property
    def uses(self) -> str:
        """Give the value of the key `uses:`, with the version in a comment."""
        return f"{self.name}@{self.sha} # v{self.version}"


# trace: PRD-CICD-014, PRD-TOP-008
def pinned_action(item: str, baseline: Mapping[str, Pin]) -> Action:
    """Give the pinned action of an item of the version baseline.

    The value of the item is `<action>@<SHA>`. The version of the item is the
    release tag without "v".
    """
    pin = baseline.get(item)
    if pin is None or pin.value is None or pin.version is None:
        raise ToolchainError(f'The version baseline has no action with a version for "{item}".')
    name, _, sha = pin.value.partition("@")
    if not _ACTION.fullmatch(name) or not _SHA.fullmatch(sha):
        raise ToolchainError(
            f'The value of "{item}" in the version baseline must be "<action>@<SHA>" '
            "with a full commit SHA of 40 hexadecimal characters."
        )
    return Action(name, sha, pin.version)


# trace: PRD-TRACE-006
def job_symbols(text: str, elements: Callable[[str], tuple[str, ...]]) -> tuple[Symbol, ...]:
    """Give a symbol of the kind `job` for each job of a workflow.

    The text must have the form of the workflow templates: the key `jobs:`
    starts at the start of a line, and each job ID has an indent of two
    spaces. A job stops at its last line before the next job, the next
    top-level key or the end of the file. Empty lines and the comments of the
    next job at the end are not part of the job. `elements` gives the identities of
    the model elements of a job ID. A job with no element gets no symbol.
    """
    lines = text.split("\n")
    try:
        start = lines.index("jobs:")
    except ValueError:
        return ()
    found: list[tuple[str, int]] = []
    stop = len(lines)
    for number, line in enumerate(lines[start + 1 :], start=start + 2):
        if line and not line.startswith(" "):
            stop = number - 1
            break
        match = _JOB.fullmatch(line)
        if match is not None:
            found.append((match.group(1), number))
    symbols: list[Symbol] = []
    for index, (job, first) in enumerate(found):
        end = found[index + 1][1] - 1 if index + 1 < len(found) else stop
        last = end
        while last > first and (not lines[last - 1].strip() or lines[last - 1].startswith("  #")):
            last -= 1
        identities = elements(job)
        if identities:
            symbols.append(Symbol(SymbolKind.JOB, job, first, last, identities))
    return tuple(symbols)
