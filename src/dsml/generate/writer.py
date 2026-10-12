# trace: PRD-CORE-004, PRD-CORE-034, PRD-CORE-036, PRD-CORE-039, PRD-CORE-040
# trace: PRD-CORE-041, PRD-CORE-042, PRD-CORE-043, PRD-CORE-044, PRD-TRACE-006
"""The file writer of all generators.

The generators do not write files. Each generator gives the full list of its
output files: the path, the bytes, the kind and the part of the output. The
writer then does these steps:

1. It checks each file: the path, the name, the encoding and the line ends.
2. It compares the files with the old manifest and with the files on disk.
   The result is a `Plan`: the files to add, change and delete, and the
   conflicts. The plan also has the new manifest and the new trace
   manifest.
3. If there is no conflict, or if the user gives `--overwrite`, it writes
   and deletes the files of the plan. Then it writes the new manifest and
   the new trace manifest.

These are the rules of the plan:

- The writer deletes each generated file of the old manifest that the new
  run does not write (PRD-CORE-041).
- The writer writes a create-once file only if no file exists at its path
  (PRD-CORE-044).
- A generated file that is different from its hash in the old manifest is a
  conflict. A file that exists at the path of a new generated file, but is
  not a generated file of the old manifest, is also a conflict
  (PRD-CORE-042, PRD-CORE-043).
- The writer does not touch a file that is not a generated file of the old
  or the new manifest, except to write a new create-once file
  (PRD-CORE-042).
- If the run selects some parts of the output, the writer keeps the
  manifest entries, the trace manifest entries and the files of the other
  parts (PRD-CORE-005).
- The writer writes the trace manifest `.dsml/trace.gen.json` from the
  symbols of the generated files (PRD-TRACE-006). Like the manifest, it is
  in the list of changes, so `--check` finds a trace manifest that is not
  current.
"""

import enum
import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from dsml.errors import ToolchainError
from dsml.generate.manifest import (
    MANIFEST_PATH,
    CreateOnceEntry,
    GeneratedEntry,
    Manifest,
    is_safe_path,
    read_manifest,
    sha256,
)
from dsml.generate.trace import (
    TRACE_PATH,
    Symbol,
    TraceEntry,
    check_symbols,
    read_trace,
    trace_bytes,
    trace_entries,
)

INFRASTRUCTURE: Final = "infrastructure"
"""The part of the output that has the infrastructure files."""

PIPELINES: Final = "pipelines"
"""The part of the output that has the pipeline files."""

LOCKFILES: Final = frozenset({".terraform.lock.hcl", "pnpm-lock.yaml", "uv.lock"})
"""The lockfiles that the generator must not write (PRD-CORE-036)."""

_GENERATED_NAME = re.compile(r"[^/]+\.gen\.[A-Za-z0-9]+|[^/]+_gen\.py")


# trace: PRD-CORE-005
def application_part(name: str) -> str:
    """Give the part of the output that has the files of one application."""
    return f"application/{name}"


# trace: PRD-CORE-040, PRD-CORE-044
class Kind(enum.StrEnum):
    """The kind of an output file."""

    GENERATED = "generated"
    """The generator owns the file and writes it again at each run."""
    CREATE_ONCE = "create-once"
    """The generator writes the file only if no file exists. A developer owns it."""


# trace: PRD-CORE-040, PRD-TRACE-006
@dataclass(frozen=True, slots=True)
class OutputFile:
    """One output file of a generator.

    The path is relative to the folder of the configuration file and uses
    "/" as the separator. The symbols go into the trace manifest. Only a
    generated file can have symbols.
    """

    path: str
    content: bytes
    kind: Kind
    part: str
    symbols: tuple[Symbol, ...] = ()


# trace: PRD-CORE-004
@dataclass(frozen=True, slots=True)
class Change:
    """One file that a normal run adds, changes or deletes."""

    action: Literal["add", "change", "delete"]
    path: str

    def __str__(self) -> str:
        return f"{self.action} {self.path}"


# trace: PRD-CORE-042, PRD-CORE-043
@dataclass(frozen=True, slots=True)
class Conflict:
    """One file that the writer must not replace or delete without `--overwrite`."""

    path: str
    reason: Literal["changed", "not-in-manifest"]

    def __str__(self) -> str:
        if self.reason == "changed":
            return f"{self.path}: The file is different from its hash in the manifest."
        return f"{self.path}: The file exists, but it is not a generated file of the manifest."


# trace: PRD-CORE-004, PRD-CORE-040
@dataclass(frozen=True, slots=True)
class Plan:
    """The changes that a run makes to the files on disk."""

    writes: tuple[tuple[str, bytes], ...]
    """The files to add or change, with their new bytes, sorted by path."""
    deletes: tuple[str, ...]
    """The generated files to delete, sorted by path."""
    conflicts: tuple[Conflict, ...]
    """The conflicts, sorted by path."""
    manifest: bytes
    """The bytes of the new manifest."""
    trace: bytes
    """The bytes of the new trace manifest."""
    changes: tuple[Change, ...]
    """Each file to add, change or delete, sorted by path.

    The manifest and the trace manifest are included.
    """

    @property
    def manifest_changes(self) -> bool:
        """Tell if the run writes the manifest."""
        return any(change.path == MANIFEST_PATH for change in self.changes)

    @property
    def trace_changes(self) -> bool:
        """Tell if the run writes the trace manifest."""
        return any(change.path == TRACE_PATH for change in self.changes)


# trace: PRD-CORE-039
def is_generated_name(path: str, fixed_names: Collection[str]) -> bool:
    """Tell if a path has the name of a generated file.

    The name ends with `.gen.<ext>` or `_gen.py`, or the path agrees with an
    item of the fixed-name list of the target:

    - An item with no "/", for example `pyproject.toml`, agrees with each
      file that has this name.
    - An item that contains "/", for example `migrations/env.py`, agrees with
      each path that ends with these parts.
    - An item that ends with "/", for example `app/`, agrees with each file
      in a folder of this name, and in its subfolders.
    """
    if _GENERATED_NAME.fullmatch(PurePosixPath(path).name):
        return True
    parts = tuple(path.split("/"))
    for item in fixed_names:
        if item.endswith("/"):
            folder = tuple(item.rstrip("/").split("/"))
            folders = parts[:-1]
            if any(
                folders[index : index + len(folder)] == folder
                for index in range(len(folders) - len(folder) + 1)
            ):
                return True
        elif parts[-len(item.split("/")) :] == tuple(item.split("/")):
            return True
    return False


# trace: PRD-CORE-034, PRD-CORE-036, PRD-CORE-039, PRD-TRACE-006
def check_files(files: Sequence[OutputFile], fixed_names: Collection[str] = ()) -> None:
    """Check the output files of a generator. An error stops the command with exit code 2.

    An error in the output of a generator is a defect of the toolchain, not
    of the model.
    """
    errors: list[str] = []
    seen: set[str] = set()
    for file in files:
        path = file.path
        if not is_safe_path(path):
            errors.append(f'The path "{path}" is not a relative path in the repository.')
            continue
        if path in seen:
            errors.append(f'The generators give the file "{path}" more than one time.')
        seen.add(path)
        name = PurePosixPath(path).name
        if name in LOCKFILES:
            errors.append(f'The generator must not write the lockfile "{path}".')
        elif file.kind is Kind.GENERATED and not is_generated_name(path, fixed_names):
            errors.append(
                f'The name of the generated file "{path}" must end with ".gen.<ext>" '
                'or "_gen.py", or be on the fixed-name list of the target.'
            )
        problem = _text_problem(file.content)
        if problem is not None:
            errors.append(f'The file "{path}" {problem}.')
        elif file.symbols and file.kind is not Kind.GENERATED:
            errors.append(f'The create-once file "{path}" must not have symbols.')
        else:
            errors.extend(check_symbols(path, file.symbols, file.content.count(b"\n")))
    if errors:
        raise ToolchainError("\n".join(f"Generator output: {error}" for error in errors))


# trace: PRD-CORE-034
def _text_problem(content: bytes) -> str | None:
    """Tell what is wrong with the text of a file, or give `None`."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return "does not have UTF-8 encoding"
    if text.startswith("﻿"):
        return "starts with a byte order mark"
    if "\r" in text:
        return "has a line end that is not LF"
    if not text.endswith("\n") or text.endswith("\n\n"):
        return "does not end with one LF"
    return None


# trace: PRD-CORE-004, PRD-CORE-005, PRD-CORE-040, PRD-CORE-041, PRD-CORE-042
# trace: PRD-CORE-043, PRD-CORE-044, PRD-TRACE-006, PRD-TRACE-008
def make_plan(root: Path, files: Sequence[OutputFile], parts: Collection[str] | None) -> Plan:
    """Compare the output files with the old manifest and with the files on disk.

    `root` is the folder of the configuration file. `parts` gives the parts of
    the output that the run selects, or `None` for all parts. Each output file
    must be in a selected part. The function writes no file.
    """
    old = read_manifest(root)

    def selected(part: str) -> bool:
        return parts is None or part in parts

    for file in files:
        if not selected(file.part):
            raise ToolchainError(
                f'The generator gives the file "{file.path}" of the part "{file.part}", '
                "but the run does not select this part."
            )
    kept_generated = [entry for entry in old.generated if not selected(entry.part)]
    kept_create_once = [entry for entry in old.create_once if not selected(entry.part)]
    kept_parts = {entry.path: entry.part for entry in [*kept_generated, *kept_create_once]}
    for file in files:
        if file.path in kept_parts:
            raise ToolchainError(
                f'The file "{file.path}" of the part "{file.part}" is a file of the part '
                f'"{kept_parts[file.path]}" in the manifest. Generate all parts to move it.'
            )

    old_hashes = {entry.path: entry.sha256 for entry in old.generated if selected(entry.part)}
    generated = [file for file in files if file.kind is Kind.GENERATED]
    create_once = [file for file in files if file.kind is Kind.CREATE_ONCE]
    new_paths = {file.path for file in files}

    writes: list[tuple[str, bytes]] = []
    changes: list[Change] = []
    deletes: list[str] = []
    conflicts: list[Conflict] = []

    for file in generated:
        disk = _read(root, file.path)
        if disk is None:
            writes.append((file.path, file.content))
            changes.append(Change("add", file.path))
            continue
        if disk == file.content:
            continue
        if file.path not in old_hashes:
            conflicts.append(Conflict(file.path, "not-in-manifest"))
        elif sha256(disk) != old_hashes[file.path]:
            conflicts.append(Conflict(file.path, "changed"))
        writes.append((file.path, file.content))
        changes.append(Change("change", file.path))

    for path, old_hash in old_hashes.items():
        if path in new_paths:
            continue
        disk = _read(root, path)
        if disk is None:
            continue
        if sha256(disk) != old_hash:
            conflicts.append(Conflict(path, "changed"))
        deletes.append(path)
        changes.append(Change("delete", path))

    # A generated file of the old manifest can become a create-once file. The
    # file then stays, and the developer owns it.
    for file in create_once:
        if not _exists(root, file.path):
            writes.append((file.path, file.content))
            changes.append(Change("add", file.path))

    manifest = Manifest(
        generated=tuple(
            [*kept_generated]
            + [GeneratedEntry(file.path, file.part, sha256(file.content)) for file in generated]
        ),
        create_once=tuple(
            [*kept_create_once] + [CreateOnceEntry(file.path, file.part) for file in create_once]
        ),
    ).to_bytes()
    _add_change(root, MANIFEST_PATH, manifest, changes)

    # A run of some parts keeps the trace entries of the generated files of
    # the other parts.
    kept_paths = {entry.path for entry in kept_generated}
    trace_list: list[TraceEntry] = []
    if kept_paths:
        trace_list.extend(entry for entry in read_trace(root) if entry.path in kept_paths)
    for file in generated:
        trace_list.extend(trace_entries(file.path, file.symbols))
    trace = trace_bytes(trace_list)
    _add_change(root, TRACE_PATH, trace, changes)

    return Plan(
        writes=tuple(sorted(writes)),
        deletes=tuple(sorted(deletes)),
        conflicts=tuple(sorted(conflicts, key=lambda conflict: conflict.path)),
        manifest=manifest,
        trace=trace,
        changes=tuple(sorted(changes, key=lambda change: change.path)),
    )


def _add_change(root: Path, path: str, content: bytes, changes: list[Change]) -> None:
    """Add a change if the file at the path is missing or has other bytes."""
    old = _read(root, path)
    if old is None:
        changes.append(Change("add", path))
    elif old != content:
        changes.append(Change("change", path))


# trace: PRD-CORE-034, PRD-CORE-040, PRD-CORE-041, PRD-TRACE-006
def apply_plan(root: Path, plan: Plan) -> None:
    """Write and delete the files of a plan, then write the new manifests.

    The function writes the bytes with no change, so each file keeps its LF
    line ends on each operating system. After it deletes a file, it also
    deletes each folder that becomes empty.
    """
    for path in plan.deletes:
        target = _target(root, path)
        try:
            target.unlink()
        except OSError as error:
            raise ToolchainError(f"Cannot delete the file {path}: {error.strerror}.") from None
        _remove_empty_folders(root, target.parent)
    for path, content in plan.writes:
        _write(root, path, content)
    if plan.manifest_changes:
        _write(root, MANIFEST_PATH, plan.manifest)
    if plan.trace_changes:
        _write(root, TRACE_PATH, plan.trace)


# trace: PRD-CORE-034, PRD-CORE-042, PRD-CORE-044
def write_create_once(root: Path, files: Sequence[OutputFile]) -> tuple[list[str], list[str]]:
    """Write each create-once file that does not exist. Do not touch the other files.

    `root` is the folder of the configuration file. Each file must be a
    create-once file. The function does not read or write the manifest. It
    gives the paths that it wrote and the paths that it kept, each list
    sorted by path.
    """
    check_files(files)
    for file in files:
        if file.kind is not Kind.CREATE_ONCE:
            raise ToolchainError(f'The file "{file.path}" is not a create-once file.')
    written: list[str] = []
    kept: list[str] = []
    for file in sorted(files, key=lambda file: file.path):
        if _exists(root, file.path):
            kept.append(file.path)
        else:
            _write(root, file.path, file.content)
            written.append(file.path)
    return written, kept


def _exists(root: Path, path: str) -> bool:
    """Tell if a file, a folder or a symbolic link exists at the path."""
    target = _target(root, path)
    return target.exists() or target.is_symlink()


def _target(root: Path, path: str) -> Path:
    """Give the file on disk for a path. The file must be in the folder `root`.

    A symbolic link that points out of `root` is an error.
    """
    base = root.resolve()
    target = base / path
    if not target.resolve().is_relative_to(base):
        raise ToolchainError(f"The path {path} goes out of the folder of the configuration file.")
    return target


def _read(root: Path, path: str) -> bytes | None:
    """Give the bytes of a file, or `None` if no file exists at the path."""
    target = _target(root, path)
    try:
        return target.read_bytes()
    except FileNotFoundError:
        return None
    except IsADirectoryError:
        raise ToolchainError(f"The path {path} is a folder, not a file.") from None
    except OSError as error:
        raise ToolchainError(f"Cannot read the file {path}: {error.strerror}.") from None


def _write(root: Path, path: str, content: bytes) -> None:
    target = _target(root, path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    except OSError as error:
        raise ToolchainError(f"Cannot write the file {path}: {error.strerror}.") from None


def _remove_empty_folders(root: Path, folder: Path) -> None:
    base = root.resolve()
    while folder.resolve() != base and folder.resolve().is_relative_to(base):
        try:
            folder.rmdir()
        except OSError:
            return
        folder = folder.parent
