"""The command line interface of the toolchain: the command `dsml`."""

import argparse
import logging
import sys
import traceback
from collections.abc import Callable, Sequence
from enum import IntEnum
from importlib import metadata
from pathlib import Path
from typing import NoReturn

from dsml import versions
from dsml.config import Configuration, load_configuration
from dsml.errors import NotAvailableError, ToolchainError, UsageError
from dsml.ir.model import IR_VERSION
from dsml.ir.writer import write_ir
from dsml.library import LIBRARY_VERSION

PROG = "dsml"
DEFAULT_CONFIG = Path("dsml.toml")
"""The configuration file that the toolchain reads if there is no `--config` (PRD-CORE-012)."""

LOG = logging.getLogger(PROG)


# trace: PRD-CORE-002
class Outcome(IntEnum):
    """The result of a subcommand. The value is the exit code."""

    SUCCESS = 0
    """The subcommand found no error."""
    ERROR_FINDING = 1
    """The subcommand found an error finding or a `--check` difference."""
    FAILURE = 2
    """A usage error or an internal error occurred."""


# trace: PRD-CORE-002
class ArgumentParser(argparse.ArgumentParser):
    """An argument parser that gives a usage error to `main()`.

    The parser of the standard library stops the program on a usage error.
    This parser raises `UsageError`, so that `main()` is the one place that
    sets the exit code.
    """

    def error(self, message: str) -> NoReturn:
        raise UsageError(message, usage=self.format_usage())


Handler = Callable[[argparse.Namespace], Outcome]


# trace: PRD-TOP-002, PRD-CORE-001, PRD-CORE-006, PRD-CORE-010, PRD-CORE-012
def build_parser() -> ArgumentParser:
    """Make the argument parser of the command `dsml`.

    Each subcommand has the common options `--config`, `--output` and
    `--verbose`, and the options of the table "Command line interface" of the
    core PRD.
    """
    common = ArgumentParser(add_help=False, allow_abbrev=False, color=False)
    common.add_argument(
        "--config",
        type=Path,
        metavar="<file>",
        help=f"read the configuration from this file (default: {DEFAULT_CONFIG})",
    )
    common.add_argument(
        "--output",
        type=Path,
        metavar="<file>",
        help="write the report to this file, not to standard output",
    )
    common.add_argument(
        "--verbose",
        action="store_true",
        help="write debug messages to standard error",
    )

    parser = ArgumentParser(
        prog=PROG,
        description="Validate a DSML model, generate code from it and trace it.",
        allow_abbrev=False,
        color=False,
    )
    subcommands = parser.add_subparsers(dest="command", metavar="<subcommand>", required=True)

    def add(name: str, summary: str, description: str | None = None) -> ArgumentParser:
        text = summary if description is None else description
        return subcommands.add_parser(
            name,
            parents=[common],
            help=summary,
            description=f"{text[0].upper()}{text[1:]}.",
            allow_abbrev=False,
            color=False,
        )

    init = add("init", "write a starter configuration file and a starter model")
    init.add_argument("--target", metavar="<name>", help="the target of the starter files")

    validate = add("validate", "validate the model and write the findings")
    validate.add_argument(
        "--format",
        choices=("text", "json", "sarif"),
        default="text",
        help="the format of the findings (default: text)",
    )
    validate.add_argument(
        "--baseline",
        metavar="<git-ref>",
        help="the baseline model for the identity rules",
    )

    generate = add("generate", "validate the model, then write all generated files")
    generate.add_argument(
        "--application",
        metavar="<name>",
        help="generate only the files of this application",
    )
    generate.add_argument(
        "--infrastructure",
        action="store_true",
        help="generate only the infrastructure files",
    )
    generate.add_argument(
        "--pipelines",
        action="store_true",
        help="generate only the pipeline files",
    )
    generate.add_argument(
        "--check",
        action="store_true",
        help="write no file and list each file that a normal run changes",
    )

    trace = add("trace", "write a trace report")
    trace.add_argument(
        "report",
        choices=("coverage", "orphans", "impact", "suspect"),
        help="the report to write",
    )
    trace.add_argument(
        "--format",
        choices=("html", "csv", "json"),
        default="html",
        help="the format of the report (default: html)",
    )
    trace.add_argument(
        "--baseline",
        metavar="<git-ref>",
        help="the baseline for the impact and suspect reports",
    )

    ir = add("ir", "write the IR as JSON")
    ir.add_argument(
        "model",
        nargs="*",
        type=Path,
        metavar="<model-file>",
        help="a SysML v2 file of the model, in the current folder or below it",
    )

    check_output = add("check-output", "run the language tools on the generated code")
    check_output.add_argument(
        "--application",
        metavar="<name>",
        help="check only the code of this application",
    )
    check_output.add_argument(
        "--infrastructure",
        action="store_true",
        help="check only the infrastructure code",
    )

    add(
        "version",
        "write the versions of the toolchain parts",
        "write the versions of the toolchain, the DSML library, OpenSysML and the IR schema",
    )
    return parser


def toolchain_version() -> str:
    """Give the version of the installed toolchain package."""
    return metadata.version(PROG)


# trace: PRD-CORE-006
def write_report(text: str, output: Path | None) -> None:
    """Write a report to standard output, or to the file that `--output` gives.

    The file has UTF-8 encoding and LF line ends (PRD-CORE-034, PRD-CORE-035).
    """
    if output is None:
        sys.stdout.write(text)
        return
    LOG.debug("Write the report to %s.", output)
    try:
        output.write_text(text, encoding="utf-8", newline="\n")
    except OSError as error:
        raise ToolchainError(f"Cannot write the file {output}: {error.strerror}.") from error


# trace: PRD-CORE-001
def run_version(args: argparse.Namespace) -> Outcome:
    """Write the versions, one line for each component."""
    lines = [
        f"toolchain: {toolchain_version()}",
        f"DSML library: {LIBRARY_VERSION}",
        f"OpenSysML: {versions.pinned_version('opensysml')}",
        f"IR schema: {IR_VERSION}",
    ]
    write_report("".join(f"{line}\n" for line in lines), args.output)
    return Outcome.SUCCESS


# trace: PRD-CORE-012
def config_path(args: argparse.Namespace) -> Path:
    """Give the configuration file of the command line, or the default file."""
    path: Path | None = args.config
    return DEFAULT_CONFIG if path is None else path


# trace: PRD-CORE-012, PRD-CORE-014
def read_configuration(args: argparse.Namespace) -> Configuration:
    """Read the configuration file of the command line.

    The file that `--config` gives must exist. If there is no `--config` and
    no `dsml.toml` in the current folder, the function gives the default
    configuration. An error in the file stops the command with exit code 2.
    """
    path = config_path(args)
    if args.config is None and not path.is_file():
        LOG.debug("The file %s does not exist. Use the default configuration.", path)
        return Configuration()
    return load_configuration(path)


# trace: PRD-CORE-032, PRD-DSML-007
def model_files(configuration: Configuration) -> list[Path]:
    """Give the model files of the configuration, sorted by path.

    A folder gives each `.sysml` file in it and in its subfolders.
    """
    files: set[Path] = set()
    for entry in configuration.model:
        path = configuration.root / entry
        if path.is_dir():
            files.update(file for file in path.rglob("*.sysml") if file.is_file())
        elif path.is_file():
            files.add(path)
        else:
            raise ToolchainError(
                f'The model path "{entry}" of the configuration file does not exist.'
            )
    return sorted(files, key=lambda file: file.as_posix())


# trace: PRD-CORE-001, PRD-CORE-002, PRD-CORE-006, PRD-CORE-012, PRD-CORE-028
def run_ir(args: argparse.Namespace) -> Outcome:
    """Write the IR of the model files as canonical JSON.

    The model files come from the command line. If the command line gives no
    model file, they come from the key `model.paths` of the configuration
    file. The IR gives each file name relative to the current folder. The
    exit code is 1 if the IR has an error finding, for example SYN-001. The
    command writes the IR also in this case.
    """
    configuration = read_configuration(args)
    files: list[Path] = args.model or model_files(configuration)
    if not files:
        raise ToolchainError(
            "Give one or more model files on the command line "
            "or in the key model.paths of the configuration file."
        )
    # The adapter imports OpenSysML. Only this subcommand needs it.
    from dsml.adapter.convert import make_ir

    LOG.debug("Model files: %s.", ", ".join(str(file) for file in files))
    ir = make_ir(files, Path.cwd())
    write_report(write_ir(ir).decode(), args.output)
    if any(finding.severity == "error" for finding in ir.findings):
        return Outcome.ERROR_FINDING
    return Outcome.SUCCESS


def not_available(args: argparse.Namespace) -> Outcome:
    """Stop a subcommand that has no implementation in this version."""
    raise NotAvailableError()


HANDLERS: dict[str, Handler] = {
    "check-output": not_available,
    "generate": not_available,
    "init": not_available,
    "ir": run_ir,
    "trace": not_available,
    "validate": not_available,
    "version": run_version,
}
"""The function that runs each subcommand. Each function gives an `Outcome`."""


# trace: PRD-TOP-002, PRD-CORE-002, PRD-CORE-009, PRD-CORE-010, PRD-CORE-019
def main(argv: Sequence[str] | None = None) -> int:
    """Run the command `dsml` and give its exit code.

    This is the one place that sets the exit code (PRD-CORE-002):

    - The subcommand gives an `Outcome`. Its value is the exit code.
    - A usage error gives exit code 2, a message and the usage.
    - A `ToolchainError`, for example a different version of `sysml-grpc`
      or an error in the configuration file, gives exit code 2 and its
      message. Each line of the message is one error line.
    - An internal error gives exit code 2 and a short message, not a
      traceback. With `--verbose`, the traceback is a debug message.

    No subcommand reads from a terminal (PRD-CORE-009).
    """
    try:
        args = build_parser().parse_args(argv)
    except UsageError as error:
        sys.stderr.write(error.usage)
        sys.stderr.write(f"{PROG}: error: {error}\n")
        return Outcome.FAILURE
    handler = _start_debug_log() if args.verbose else None
    try:
        LOG.debug("Subcommand: %s.", args.command)
        LOG.debug("Configuration file: %s.", config_path(args))
        return HANDLERS[args.command](args)
    except ToolchainError as error:
        for line in str(error).splitlines():
            sys.stderr.write(f"{PROG}: error: {line}\n")
        return Outcome.FAILURE
    except Exception as error:
        LOG.debug("Traceback of the internal error:\n%s", traceback.format_exc().rstrip("\n"))
        sys.stderr.write(
            f"{PROG}: error: An internal error occurred: {type(error).__name__}: {error}\n"
        )
        return Outcome.FAILURE
    finally:
        if handler is not None:
            _stop_debug_log(handler)


# trace: PRD-CORE-010
def _start_debug_log() -> logging.Handler:
    """Write the debug messages of the toolchain to standard error."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(f"{PROG}: debug: %(message)s"))
    LOG.addHandler(handler)
    LOG.setLevel(logging.DEBUG)
    return handler


def _stop_debug_log(handler: logging.Handler) -> None:
    LOG.removeHandler(handler)
    LOG.setLevel(logging.NOTSET)
