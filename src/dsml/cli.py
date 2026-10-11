"""The command line interface of the toolchain: the command `dsml`."""

import argparse
import logging
import sys
import traceback
from collections.abc import Callable, Sequence
from enum import IntEnum
from importlib import metadata
from pathlib import Path, PurePosixPath
from typing import NoReturn

from dsml import starter, versions
from dsml.config import Configuration, load_configuration
from dsml.errors import NotAvailableError, ToolchainError, UsageError
from dsml.generate import generators
from dsml.generate.manifest import read_manifest
from dsml.generate.trace import read_trace
from dsml.generate.writer import (
    INFRASTRUCTURE,
    PIPELINES,
    Kind,
    OutputFile,
    application_part,
    apply_plan,
    make_plan,
    write_create_once,
)
from dsml.ir.model import IR_VERSION, Ir
from dsml.ir.writer import write_ir
from dsml.library import LIBRARY_VERSION
from dsml.trace.comments import hand_written_files, read_trace_comments
from dsml.trace.commit import model_commit
from dsml.trace.report import csv_report
from dsml.trace.report import json_report as json_trace_report
from dsml.trace.reports import COVERAGE, ORPHANS, TraceData, coverage_report, orphans_report
from dsml.validate.engine import Validator, fails
from dsml.validate.report import finding_line, json_report, text_report

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
    init.add_argument(
        "--target",
        choices=starter.TARGETS,
        default=starter.DEFAULT_TARGET,
        help=f"the target of the starter files (default: {starter.DEFAULT_TARGET})",
    )

    validate = add("validate", "validate the model and write the findings")
    validate.add_argument(
        "--format",
        choices=("text", "json", "sarif"),
        default="text",
        help="the format of the findings (default: text)",
    )
    validate.add_argument(
        "--fail-on",
        choices=("error", "warning"),
        default="error",
        help="stop with exit code 1 if a finding has this severity or a higher one "
        "(default: error)",
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
    generate.add_argument(
        "--overwrite",
        action="store_true",
        help="replace the generated files that are different from the manifest",
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


# trace: PRD-CORE-006, PRD-CORE-015, PRD-CORE-034
def write_report(text: str, output: Path | None) -> None:
    """Write a report to standard output, or to the file that `--output` gives.

    The report has UTF-8 encoding and LF line ends (PRD-CORE-034,
    PRD-CORE-035). On standard output, the function writes the UTF-8 bytes.
    Thus the locale and `PYTHONIOENCODING` do not change the report
    (PRD-CORE-015).
    """
    if output is None:
        sys.stdout.flush()
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.flush()
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


INIT_PART = "init"
"""The part of the output that has the starter files of `dsml init`."""


# trace: PRD-CORE-001, PRD-CORE-006, PRD-CORE-012, PRD-CORE-042, PRD-CORE-044
def run_init(args: argparse.Namespace) -> Outcome:
    """Write the starter configuration file and the starter model as create-once files.

    The configuration file goes to the path of `--config`, or to `dsml.toml`
    in the current folder. The model goes to `model/` in the folder of the
    configuration file. The command writes only a file that does not exist.
    It does not change a file that exists, and it writes no manifest.

    The report has one line for each file, sorted by path: `add <path>` for a
    file that the command wrote, or a message for a file that exists.
    """
    path = config_path(args)
    root = path.parent
    output = [
        OutputFile(
            path.name if name == starter.CONFIG_FILE else name, content, Kind.CREATE_ONCE, INIT_PART
        )
        for name, content in starter.starter_files(args.target).items()
    ]
    written, kept = write_create_once(root, output)
    lines = {name: f"add {(root / name).as_posix()}" for name in written}
    lines |= {
        name: f"keep {(root / name).as_posix()}: The file exists. The command did not change it."
        for name in kept
    }
    write_report("".join(f"{lines[name]}\n" for name in sorted(lines)), args.output)
    return Outcome.SUCCESS


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


# trace: PRD-CORE-005
def selected_parts(args: argparse.Namespace, ir: Ir) -> frozenset[str] | None:
    """Give the parts of the output that the options select, or `None` for all parts.

    The application of `--application` must be an application of the model.
    """
    parts: set[str] = set()
    if args.application is not None:
        names = sorted({element.name for element in ir.elements if element.kind == "Application"})
        if args.application not in names:
            known = ", ".join(names) if names else "none"
            raise ToolchainError(
                f'The model has no application "{args.application}". '
                f"The applications of the model are: {known}."
            )
        parts.add(application_part(args.application))
    if args.infrastructure:
        parts.add(INFRASTRUCTURE)
    if args.pipelines:
        parts.add(PIPELINES)
    return frozenset(parts) if parts else None


# trace: PRD-CORE-001, PRD-CORE-020
def read_model(configuration: Configuration) -> Ir:
    """Make the IR of the model files of the key `model.paths`."""
    files = model_files(configuration)
    if not files:
        raise ToolchainError(
            "Give one or more model files in the key model.paths of the configuration file."
        )
    # The adapter imports OpenSysML. Only the subcommands that read the model
    # need it.
    from dsml.adapter.convert import make_ir

    LOG.debug("Model files: %s.", ", ".join(str(file) for file in files))
    return make_ir(files, Path.cwd())


# trace: PRD-CORE-001, PRD-CORE-002, PRD-CORE-006, PRD-VAL-003, PRD-VAL-005, PRD-VAL-006
def run_validate(args: argparse.Namespace) -> Outcome:
    """Run all enabled rules on the IR and write the findings.

    The report is text or JSON (`--format`). The exit code is 1 if a finding
    has the severity `error`, or the severity `warning` with
    `--fail-on warning` (PRD-VAL-005).
    """
    if args.format == "sarif":
        raise ToolchainError("The format sarif is not available in this version.")
    if args.baseline is not None:
        raise ToolchainError("The option --baseline is not available in this version.")
    configuration = read_configuration(args)
    validator = Validator(configuration)
    findings = validator.run(read_model(configuration))
    write = json_report if args.format == "json" else text_report
    write_report(write(findings, validator.rules), args.output)
    return Outcome.ERROR_FINDING if fails(findings, args.fail_on) else Outcome.SUCCESS


# trace: PRD-CORE-001, PRD-CORE-002, PRD-CORE-003, PRD-CORE-004, PRD-CORE-005, PRD-CORE-043,
# PRD-VAL-003
def run_generate(args: argparse.Namespace) -> Outcome:
    """Validate the model, then write the generated files through the file writer.

    - The validator runs all enabled rules on the IR. An error finding stops
      the command before it writes a file. The exit code is 1 (PRD-CORE-003,
      PRD-VAL-003).
    - With `--check`, the command writes no file. It lists each file that a
      normal run adds, changes or deletes. The exit code is 1 if there is a
      difference (PRD-CORE-004).
    - If a generated file is different from its hash in the manifest, the
      command writes no file. It lists the changed files and the exit code is
      1. With `--overwrite`, the command replaces them (PRD-CORE-043).
    - Each file to add, change or delete is one line of the report.
    """
    configuration = read_configuration(args)
    validator = Validator(configuration)
    ir = read_model(configuration)
    errors = [finding for finding in validator.run(ir) if finding.severity == "error"]
    if errors:
        for finding in errors:
            sys.stderr.write(f"{PROG}: {finding_line(finding)}\n")
        count = "1 error finding" if len(errors) == 1 else f"{len(errors)} error findings"
        sys.stderr.write(f"{PROG}: error: The model has {count}. No file was written.\n")
        return Outcome.ERROR_FINDING
    parts = selected_parts(args, ir)
    output = generators.collect(generators.GENERATORS, ir, configuration, parts)
    plan = make_plan(configuration.root, output, parts)
    report = "".join(f"{change}\n" for change in plan.changes)
    if args.check:
        write_report(report, args.output)
        return Outcome.ERROR_FINDING if plan.changes else Outcome.SUCCESS
    if plan.conflicts and not args.overwrite:
        for conflict in plan.conflicts:
            sys.stderr.write(f"{PROG}: error: {conflict}\n")
        sys.stderr.write(
            f"{PROG}: error: No file was written. "
            "Use --overwrite to replace or delete these files.\n"
        )
        return Outcome.ERROR_FINDING
    apply_plan(configuration.root, plan)
    write_report(report, args.output)
    return Outcome.SUCCESS


# trace: PRD-TRACE-010
def trace_folders(configuration: Configuration) -> list[PurePosixPath]:
    """Give the output folders and the test folders of the configuration, sorted."""
    folders = {app.output for app in configuration.applications if app.output is not None}
    folders.update(
        folder
        for folder in (configuration.infrastructure, configuration.pipelines)
        if folder is not None
    )
    folders.update(configuration.trace.tests)
    return sorted(folders, key=lambda folder: folder.as_posix())


# trace: PRD-CORE-001, PRD-CORE-006, PRD-TRACE-010, PRD-TRACE-012, PRD-TRACE-013,
# PRD-TRACE-017, PRD-TRACE-018
def run_trace(args: argparse.Namespace) -> Outcome:
    """Write the coverage report or the orphans report as JSON or as CSV.

    The command reads the model, the trace manifest `.dsml/trace.gen.json`
    and the trace comments in the hand-written files of the output folders
    and the test folders. A trace comment that the reader cannot read gives
    a warning on standard error. The exit code is 0, also if the report has
    a requirement with the status `missing` or an orphan.
    """
    if args.report not in (COVERAGE, ORPHANS):
        raise NotAvailableError()
    if args.format == "html":
        raise ToolchainError(
            "The format html is not available in this version. Use --format json or --format csv."
        )
    if args.baseline is not None:
        raise ToolchainError("The option --baseline is not available in this version.")
    configuration = read_configuration(args)
    ir = read_model(configuration)
    root = configuration.root
    generated = [entry.path for entry in read_manifest(root).generated]
    folders = trace_folders(configuration)
    found = read_trace_comments(root, folders, generated)
    for problem in found.problems:
        where = problem.path if problem.line is None else f"{problem.path}:{problem.line}"
        sys.stderr.write(f"{PROG}: warning: {where}: {problem.message}\n")
    data = TraceData(
        ir=ir,
        entries=tuple(read_trace(root)),
        comments=found.comments,
        files=tuple(hand_written_files(root, folders, generated)),
        model_commit=model_commit(root),
    )
    report = coverage_report(data) if args.report == COVERAGE else orphans_report(data)
    write = json_trace_report if args.format == "json" else csv_report
    write_report(write(report), args.output)
    return Outcome.SUCCESS


def not_available(args: argparse.Namespace) -> Outcome:
    """Stop a subcommand that has no implementation in this version."""
    raise NotAvailableError()


HANDLERS: dict[str, Handler] = {
    "check-output": not_available,
    "generate": run_generate,
    "init": run_init,
    "ir": run_ir,
    "trace": run_trace,
    "validate": run_validate,
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
