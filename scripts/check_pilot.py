"""Run SysML files through the Jupyter kernel of the OMG pilot implementation.

Story #23 adds this check for PRD-DSML-005 (Q60). The script downloads the
pinned release of the kernel (`jupyter-sysml-kernel`) from the release page of
the pilot implementation, checks its SHA-256 hash, starts the kernel and sends
each file to the kernel as one cell. `src/dsml/versions.toml` holds the pin.

Run it from the root of the repository. Java 17 or later must be installed:

    uv run python scripts/check_pilot.py src/dsml/library/DSML.sysml

With `--one-model`, the script joins the files into one cell. Use it for a
model that imports the DSML library or that has more than one file:

    uv run python scripts/check_pilot.py --one-model \
        src/dsml/library/DSML.sysml docs/model/examples/order-service.sysml

Exit codes:

- 0: the result agrees with the expectation. Without `--expect-rejection`,
  the kernel accepts each file. With `--expect-rejection`, the kernel rejects
  each file.
- 1: the result does not agree with the expectation.
- 2: the check cannot run, for example because the download failed.

The script does not use the network after the download. It does not set the
API base path of the kernel, thus the kernel does not connect to a model
repository.
"""

# trace: PRD-DSML-005

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.request
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jupyter_client.kernelspec import KernelSpecManager
from jupyter_client.manager import KernelManager

from dsml.versions import load_baseline

RELEASE_URL = (
    "https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation/releases/download/"
    "{release}/jupyter-sysml-kernel-{version}.zip"
)
KERNEL_NAME = "sysml-pilot"
KERNEL_CLASS = "org.omg.sysml.jupyter.kernel.ISysML"
LIBRARY_DIR = "sysml.library"
START_TIMEOUT_S = 180
CELL_TIMEOUT_S = 600
EXIT_EXPECTED = 0
EXIT_UNEXPECTED = 1
EXIT_SETUP = 2
# The pilot kernel gives the location of a diagnostic in this form.
LOCATION = re.compile(r"\(\d+\.sysml line : (\d+)")


class SetupError(Exception):
    """The check cannot run."""


@dataclass(frozen=True, slots=True)
class Release:
    """The pinned release of the pilot kernel."""

    version: str
    release: str
    sha256: str

    @property
    def url(self) -> str:
        return RELEASE_URL.format(release=self.release, version=self.version)


@dataclass(frozen=True, slots=True)
class CellResult:
    """The result of one cell: the error and warning lines of the kernel."""

    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return not self.errors


def pinned_release() -> Release:
    """Read the pin of the pilot kernel from the version baseline."""
    baseline = load_baseline()
    version = baseline["pilot-kernel"].version
    release = baseline["pilot-kernel-release"].value
    sha256 = baseline["pilot-kernel-sha256"].value
    if version is None or release is None or sha256 is None:
        raise SetupError("The version baseline must give the version, release and SHA-256 hash.")
    return Release(version=version, release=release, sha256=sha256.lower())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# trace: PRD-DSML-005
def download(release: Release, cache: Path) -> Path:
    """Download the release archive into `cache` and check its SHA-256 hash.

    The function keeps a downloaded archive with the correct hash and does
    not download it again.
    """
    archive = cache / f"jupyter-sysml-kernel-{release.version}.zip"
    if archive.is_file() and file_sha256(archive) == release.sha256:
        return archive
    cache.mkdir(parents=True, exist_ok=True)
    part = archive.with_suffix(".part")
    print(f"Download {release.url}")
    try:
        urllib.request.urlretrieve(release.url, part)
    except OSError as error:
        raise SetupError(f"The download of {release.url} failed: {error}") from error
    actual = file_sha256(part)
    if actual != release.sha256:
        part.unlink()
        raise SetupError(
            f"The SHA-256 hash of {release.url} is {actual}. The pin is {release.sha256}."
        )
    part.replace(archive)
    return archive


def unpack(archive: Path, target: Path) -> tuple[Path, Path]:
    """Extract the archive. Give the kernel JAR file and the library folder."""
    if not target.is_dir():
        partial = target.with_name(target.name + ".part")
        with zipfile.ZipFile(archive) as content:
            content.extractall(partial)
        partial.replace(target)
    return find_kernel(target)


def find_kernel(root: Path) -> tuple[Path, Path]:
    """Find the kernel JAR file and the SysML library folder below `root`."""
    jars = sorted(root.rglob("jupyter-sysml-kernel-*-all.jar"))
    libraries = sorted(path for path in root.rglob(LIBRARY_DIR) if path.is_dir())
    if len(jars) != 1:
        raise SetupError(f"The release must contain 1 kernel JAR file. It contains {len(jars)}.")
    if len(libraries) != 1:
        raise SetupError(
            f"The release must contain 1 {LIBRARY_DIR} folder. It contains {len(libraries)}."
        )
    return jars[0], libraries[0]


@dataclass(frozen=True, slots=True)
class Cell:
    """The text of one cell, and the first line of each file in the cell."""

    label: str
    code: str
    starts: tuple[tuple[int, str], ...]

    def locate(self, line: str) -> str:
        """Change the cell line number in a diagnostic to a file and a line."""
        match = LOCATION.search(line)
        if match is None or len(self.starts) < 2:
            return line
        number = int(match.group(1))
        first, name = max(
            (start for start in self.starts if start[0] <= number), default=self.starts[0]
        )
        return f"{name}:{number - first + 1}: {line}"


# trace: PRD-DSML-005
def make_cells(files: Sequence[tuple[str, str]], one_model: bool) -> list[Cell]:
    """Make one cell for each file, or one cell for all files.

    `files` holds the name and the text of each file. In one cell, each file
    starts on a new line, so the script can find the file of a diagnostic.
    """
    if not one_model:
        return [Cell(label=name, code=text, starts=((1, name),)) for name, text in files]
    parts: list[str] = []
    starts: list[tuple[int, str]] = []
    line = 1
    for name, text in files:
        if not text.endswith("\n"):
            text += "\n"
        starts.append((line, name))
        parts.append(text)
        line += text.count("\n")
    names = [name for name, _ in files]
    label = names[0] if len(names) == 1 else f"{names[0]} and {len(names) - 1} more files"
    return [Cell(label=label, code="".join(parts), starts=tuple(starts))]


def write_kernel_spec(kernels: Path, java: str, jar: Path, library: Path) -> None:
    """Write a kernel spec that starts the pilot kernel with no API base path."""
    spec = {
        "argv": [java, "-cp", str(jar), KERNEL_CLASS, "{connection_file}"],
        "display_name": "SysML (OMG pilot implementation)",
        "env": {"ISYSML_LIBRARY_PATH": str(library) + os.sep},
        "interrupt_mode": "message",
        "language": "sysml",
    }
    folder = kernels / KERNEL_NAME
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "kernel.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")


# trace: PRD-DSML-005
def cell_result(reply: Mapping[str, Any], messages: Iterable[Mapping[str, Any]]) -> CellResult:
    """Find the errors and warnings in the messages of one cell.

    The pilot kernel writes each diagnostic to the stderr stream, as a line
    that starts with "ERROR:" or "WARNING:". The kernel rejects the cell if
    the reply is not "ok", if it sends an error message, or if it writes an
    error line.
    """
    errors: list[str] = []
    warnings: list[str] = []
    for message in messages:
        content = message.get("content", {})
        kind = message.get("msg_type") or message.get("header", {}).get("msg_type")
        if kind == "error":
            errors.append(f"{content.get('ename', 'Error')}: {content.get('evalue', '')}")
        elif kind == "stream" and content.get("name") == "stderr":
            for line in str(content.get("text", "")).splitlines():
                if line.startswith("WARNING"):
                    warnings.append(line)
                elif line.strip():
                    errors.append(line)
    status = reply.get("content", {}).get("status")
    if status != "ok" and not errors:
        errors.append(f"The kernel reply has the status {status!r}.")
    return CellResult(errors=tuple(errors), warnings=tuple(warnings))


def run_cells(kernels: Path, cells: Sequence[str]) -> list[CellResult]:
    """Start the kernel, run each cell in a new kernel and stop the kernel."""
    results: list[CellResult] = []
    specs = KernelSpecManager(kernel_dirs=[str(kernels)])
    for code in cells:
        manager = KernelManager(kernel_name=KERNEL_NAME, kernel_spec_manager=specs)
        manager.start_kernel()
        client = manager.client()
        try:
            client.start_channels()
            client.wait_for_ready(timeout=START_TIMEOUT_S)
            messages: list[dict[str, Any]] = []
            reply = client.execute_interactive(
                code, timeout=CELL_TIMEOUT_S, output_hook=messages.append
            )
            results.append(cell_result(reply, messages))
        finally:
            client.stop_channels()
            manager.shutdown_kernel(now=True)
    return results


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run SysML files through the Jupyter kernel of the OMG pilot implementation."
    )
    parser.add_argument("files", nargs="+", type=Path, help="SysML files to send to the kernel")
    parser.add_argument(
        "--expect-rejection",
        action="store_true",
        help="expect that the kernel rejects each file",
    )
    parser.add_argument(
        "--one-model",
        action="store_true",
        help="send all files to one kernel as one cell, for example a model with its library",
    )
    parser.add_argument(
        "--java",
        default=os.environ.get("PILOT_JAVA", "java"),
        help="the Java command (default: $PILOT_JAVA or java)",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path(tempfile.gettempdir()) / "dsml-pilot",
        help="the folder for the download (default: a folder in the temporary folder)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(argv)
    try:
        release = pinned_release()
        archive = download(release, arguments.cache)
        jar, library = unpack(archive, arguments.cache / f"kernel-{release.version}")
        kernels = arguments.cache / "kernels"
        write_kernel_spec(kernels, arguments.java, jar, library)
        cells = make_cells(
            [(str(path), path.read_text(encoding="utf-8")) for path in arguments.files],
            arguments.one_model,
        )
        print(
            f"Pilot kernel: jupyter-sysml-kernel {release.version}. "
            f"Files: {len(arguments.files)}. Cells: {len(cells)}."
        )
        results = run_cells(kernels, [cell.code for cell in cells])
    except (SetupError, OSError, RuntimeError) as error:
        print(f"The check cannot run: {error}", file=sys.stderr)
        return EXIT_SETUP
    unexpected = 0
    for cell, result in zip(cells, results, strict=True):
        path = cell.label
        for line in result.warnings:
            print(f"{path}: {cell.locate(line)}")
        for line in result.errors:
            print(f"{path}: {cell.locate(line)}")
        if result.accepted == arguments.expect_rejection:
            unexpected += 1
            state = "accepts" if result.accepted else "does not accept"
            print(f"{path}: The pilot kernel {state} the file.", file=sys.stderr)
        else:
            state = "accepts" if result.accepted else "does not accept"
            print(f"{path}: The pilot kernel {state} the file, as expected.")
    return EXIT_UNEXPECTED if unexpected else EXIT_EXPECTED


if __name__ == "__main__":
    sys.exit(main())
