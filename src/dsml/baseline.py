# trace: PRD-VAL-011, PRD-TRACE-016, PRD-TOP-004
"""Read the baseline model from the local Git repository.

The identity rules (IDN) of the validator and the impact and suspect reports
compare the model with a baseline. The baseline is a Git reference, for
example a commit, a branch or a tag.

This module uses the local `git` command. It does not fetch from a remote
repository, so it does not use the network (PRD-TOP-004). It copies the model
files at the baseline into a temporary folder. The IR adapter then makes the
IR of these files, so only the adapter imports OpenSysML (PRD-CORE-020).
"""

import io
import subprocess
import tarfile
import tempfile
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.ir.model import Ir

RELEASE_TAGS = "v*"
"""The pattern of the release tags (Q54)."""


# trace: PRD-TOP-004
def git(folder: Path, *args: str) -> bytes:
    """Run a local `git` command in a folder and give its standard output.

    A command that fails is an error with exit code 2.
    """
    try:
        result = subprocess.run(["git", "-C", str(folder), *args], capture_output=True, check=False)
    except OSError as error:
        raise ToolchainError(f"Cannot run the command git: {error.strerror}.") from None
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip().splitlines()
        reason = f" {detail[-1]}" if detail else ""
        raise ToolchainError(f"The command git {args[0]} failed.{reason}")
    return result.stdout


# trace: PRD-VAL-011
def repository_root(folder: Path) -> Path:
    """Give the top folder of the Git repository that contains a folder."""
    try:
        text = git(folder, "rev-parse", "--show-toplevel").decode("utf-8").strip()
    except ToolchainError:
        raise ToolchainError(
            f"The folder {folder} is not in a Git repository. A baseline needs a Git repository."
        ) from None
    return Path(text).resolve()


# trace: PRD-VAL-011
def resolve(folder: Path, ref: str) -> str:
    """Give the commit of a Git reference in the repository of a folder.

    A reference that does not exist is an error with exit code 2.
    """
    if not ref or ref.startswith("-"):
        raise ToolchainError(f'The Git reference "{ref}" is not correct.')
    try:
        text = git(folder, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    except ToolchainError:
        raise ToolchainError(
            f'The Git reference "{ref}" does not exist in the local repository.'
        ) from None
    return text.decode("utf-8").strip()


# trace: PRD-TRACE-016
def newest_release_tag(folder: Path) -> str | None:
    """Give the newest release tag `v*` before `HEAD`, or `None` if there is none (Q54).

    The newest tag is the tag nearest to `HEAD` in the commit graph. A tag on
    `HEAD` is not before `HEAD`, so the function does not give it.
    """
    resolve(folder, "HEAD")
    at_head = git(folder, "tag", "--points-at", "HEAD", "--list", RELEASE_TAGS).decode("utf-8")
    excluded = [f"--exclude={tag}" for tag in sorted(at_head.split())]
    try:
        text = git(
            folder, "describe", "--tags", "--abbrev=0", f"--match={RELEASE_TAGS}", *excluded, "HEAD"
        )
    except ToolchainError:
        return None
    return text.decode("utf-8").strip()


# trace: PRD-VAL-011
@dataclass(frozen=True, slots=True)
class Checkout:
    """The model files at a baseline, in a temporary folder.

    `root` is the folder in the temporary copy that agrees with the current
    folder. `files` are the model files in this copy, sorted by path. Thus
    the IR of the baseline gives the same file names as the IR of the
    current model.
    """

    commit: str
    root: Path
    files: tuple[Path, ...]


# trace: PRD-VAL-011, PRD-CORE-032
@contextmanager
def checkout(ref: str, configuration: Configuration, cwd: Path) -> Generator[Checkout]:
    """Copy the model files of the configuration at a Git reference into a temporary folder.

    The key `model.paths` of the current configuration gives the model files.
    A model path that does not exist at the baseline gives no file. The
    temporary folder is deleted at the end.
    """
    top = repository_root(cwd)
    commit = resolve(cwd, ref)
    here = _inside(cwd.resolve(), top, "The current folder")
    config_root = _inside(configuration.root.resolve(), top, "The folder of the configuration")
    entries = [config_root / PurePosixPath(entry) for entry in configuration.model]
    names = _model_names(_tree(top, commit), entries)
    with tempfile.TemporaryDirectory(prefix="dsml-baseline-") as folder:
        copy = Path(folder)
        if names:
            data = git(top, "archive", "--format=tar", commit, "--", *names)
            with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                archive.extractall(copy, filter="data")
        root = copy.joinpath(*here.parts)
        files = tuple(copy.joinpath(*PurePosixPath(name).parts) for name in names)
        yield Checkout(commit, root, files)


# trace: PRD-VAL-011, PRD-TRACE-016, PRD-CORE-020
def read_baseline(ref: str, configuration: Configuration, cwd: Path) -> Ir:
    """Make the IR of the model at a Git reference.

    If the model has no file at the baseline, the IR is empty.
    """
    with checkout(ref, configuration, cwd) as copy:
        if not copy.files:
            return Ir()
        # The adapter imports OpenSysML. Import it only when it is necessary.
        from dsml.adapter.convert import make_ir

        return make_ir(copy.files, copy.root)


def _inside(path: Path, top: Path, what: str) -> PurePosixPath:
    try:
        return PurePosixPath(path.relative_to(top).as_posix())
    except ValueError:
        raise ToolchainError(f"{what} {path} is not in the Git repository {top}.") from None


def _tree(top: Path, commit: str) -> list[str]:
    """Give the paths of the files at a commit, relative to the repository root."""
    data = git(top, "ls-tree", "-r", "-z", "--full-tree", "--name-only", commit)
    return [name for name in data.decode("utf-8").split("\0") if name]


def _model_names(tree: Sequence[str], entries: Sequence[PurePosixPath]) -> list[str]:
    """Select the model files of the model paths from the files of a commit.

    A model path is a file or a folder. A folder gives each `.sysml` file in
    it and in its subfolders.
    """
    names: set[str] = set()
    for entry in entries:
        text = entry.as_posix()
        for name in tree:
            if name == text or (
                name.endswith(".sysml") and (text == "." or name.startswith(f"{text}/"))
            ):
                names.add(name)
    return sorted(names)
