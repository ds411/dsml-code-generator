# trace: PRD-CORE-040
"""The manifest `.dsml/generated.json`.

The manifest records which files the generator owns. For each generated
file, it gives the path, the part of the output and the SHA-256 hash of the
bytes that the generator wrote. For each create-once file, it gives the path
and the part. The generator does not own a create-once file after it wrote
it, so the manifest keeps no hash for it.

The manifest is canonical JSON: sorted keys, lists sorted by path, UTF-8,
LF line ends and one LF at the end (PRD-CORE-028, PRD-CORE-034).
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, cast

from dsml.errors import ToolchainError
from dsml.ir.writer import JsonValue, canonical_json

MANIFEST_PATH: Final = ".dsml/generated.json"
"""The path of the manifest, relative to the folder of the configuration file."""

MANIFEST_VERSION: Final = 1
"""The version of the manifest format that this toolchain reads and writes."""


def sha256(content: bytes) -> str:
    """Give the SHA-256 hash of the bytes as 64 lowercase hexadecimal digits."""
    return hashlib.sha256(content).hexdigest()


# trace: PRD-CORE-040
@dataclass(frozen=True, slots=True)
class GeneratedEntry:
    """One generated file of the manifest."""

    path: str
    part: str
    sha256: str


# trace: PRD-CORE-040
@dataclass(frozen=True, slots=True)
class CreateOnceEntry:
    """One create-once file of the manifest."""

    path: str
    part: str


# trace: PRD-CORE-040
@dataclass(frozen=True, slots=True)
class Manifest:
    """The contents of the manifest. Each list is sorted by path."""

    generated: tuple[GeneratedEntry, ...] = ()
    create_once: tuple[CreateOnceEntry, ...] = ()

    def to_bytes(self) -> bytes:
        """Write the manifest as canonical JSON bytes."""
        data: dict[str, JsonValue] = {
            "createOnce": [
                {"part": entry.part, "path": entry.path}
                for entry in sorted(self.create_once, key=lambda entry: entry.path)
            ],
            "generated": [
                {"part": entry.part, "path": entry.path, "sha256": entry.sha256}
                for entry in sorted(self.generated, key=lambda entry: entry.path)
            ],
            "manifestVersion": MANIFEST_VERSION,
        }
        return canonical_json(data)


# trace: PRD-CORE-040
def read_manifest(root: Path) -> Manifest:
    """Read the manifest in the folder `root`.

    If there is no manifest, the function gives an empty manifest. A manifest
    that is not correct stops the command with exit code 2.
    """
    path = root / MANIFEST_PATH
    try:
        text = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        return Manifest()
    except OSError as error:
        raise ToolchainError(
            f"Cannot read the manifest {MANIFEST_PATH}: {error.strerror}."
        ) from None
    except UnicodeDecodeError:
        raise ToolchainError(
            f"The manifest {MANIFEST_PATH} does not have UTF-8 encoding."
        ) from None
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as error:
        raise ToolchainError(
            f"The manifest {MANIFEST_PATH} is not correct JSON: {error.msg} "
            f"at line {error.lineno}, column {error.colno}."
        ) from None
    return _parse(data)


def _parse(data: object) -> Manifest:
    if not isinstance(data, dict):
        raise _error("The top level must be a JSON object.")
    top = cast(dict[str, object], data)
    if set(top) != {"createOnce", "generated", "manifestVersion"}:
        raise _error('The keys must be "createOnce", "generated" and "manifestVersion".')
    version = top["manifestVersion"]
    if type(version) is not int or version != MANIFEST_VERSION:
        raise _error(
            f"The manifest version {version!r} is unknown. "
            f"This toolchain reads manifest version {MANIFEST_VERSION}."
        )
    generated = tuple(
        GeneratedEntry(path=item["path"], part=item["part"], sha256=item["sha256"])
        for item in _entries(top["generated"], "generated", {"part", "path", "sha256"})
    )
    for entry in generated:
        if len(entry.sha256) != 64 or entry.sha256.strip("0123456789abcdef"):
            raise _error(f'The hash of "{entry.path}" is not a SHA-256 hash.')
    create_once = tuple(
        CreateOnceEntry(path=item["path"], part=item["part"])
        for item in _entries(top["createOnce"], "createOnce", {"part", "path"})
    )
    paths = [entry.path for entry in generated] + [entry.path for entry in create_once]
    for path in paths:
        if not is_safe_path(path):
            raise _error(f'The path "{path}" is not a relative path in the repository.')
    if len(set(paths)) != len(paths):
        raise _error("A path occurs more than one time.")
    return Manifest(generated, create_once)


def _entries(value: object, key: str, keys: set[str]) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise _error(f'The key "{key}" must be a list.')
    entries: list[dict[str, str]] = []
    for item in cast(list[object], value):
        if not isinstance(item, dict):
            raise _error(f'Each item of "{key}" must be a JSON object.')
        entry = cast(dict[str, object], item)
        if set(entry) != keys or not all(isinstance(text, str) and text for text in entry.values()):
            names = ", ".join(f'"{name}"' for name in sorted(keys))
            raise _error(f'Each item of "{key}" must have only the text keys {names}.')
        entries.append(cast(dict[str, str], entry))
    return entries


def _error(message: str) -> ToolchainError:
    return ToolchainError(f"The manifest {MANIFEST_PATH} is not correct. {message}")


# trace: PRD-CORE-042
def is_safe_path(path: str) -> bool:
    """Tell if a path is a normal relative path with "/" as the separator.

    A safe path has no empty part, no "." or ".." part, no "\\" and no ":".
    It is not in the folders `.dsml` and `.git`.
    """
    if not path or "\\" in path or ":" in path or path.startswith("/"):
        return False
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    return PurePosixPath(path).as_posix() == path and parts[0] not in (".dsml", ".git")
