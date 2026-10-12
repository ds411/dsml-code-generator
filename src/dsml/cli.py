"""The command line interface of the toolchain: the command `dsml`."""

import argparse
import logging
import os
import re
import sys
import traceback
from collections.abc import Callable, Sequence
from datetime import date
from enum import IntEnum
from importlib import metadata
from pathlib import Path, PurePosixPath
from typing import NoReturn

from dsml import skills, starter, versions
from dsml.baseline import (
    Baseline,
    load_baseline,
    newest_release_tag,
    read_baseline,
    repository_root,
)
from dsml.check_output import ApplicationCode, check_output, passed, select_applications
from dsml.check_output import text_report as check_report
from dsml.config import Configuration, load_configuration
from dsml.errors import ToolchainError, UsageError
from dsml.generate import generators
from dsml.generate.manifest import read_manifest
from dsml.generate.trace import SymbolKind, read_trace
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
from dsml.mcp.project import Project
from dsml.trace.changes import IMPACT, ChangeData, impact_report, suspect_report
from dsml.trace.comments import hand_written_files, read_trace_comments
from dsml.trace.commit import model_commit
from dsml.trace.report import Report, csv_report, html_report
from dsml.trace.report import json_report as json_trace_report
from dsml.trace.reports import COVERAGE, ORPHANS, TraceData, coverage_report, orphans_report
from dsml.validate.engine import Validator, fails
from dsml.validate.report import finding_line, json_report, text_report
from dsml.validate.sarif import sarif_report
from dsml.validate.waivers import check_date

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
# trace: PRD-VAL-010
def check_date_option(text: str) -> date:
    """Read the value of the option `--date`. It must have the form YYYY-MM-DD."""
    try:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
            return date.fromisoformat(text)
    except ValueError:
        pass
    raise argparse.ArgumentTypeError(f'"{text}" is not a date. Use the form YYYY-MM-DD.')


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
    validate.add_argument(
        "--date",
        type=check_date_option,
        metavar="<YYYY-MM-DD>",
        help="the date of the expiry check of the waivers (default: the commit date of HEAD)",
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
    generate.add_argument(
        "--date",
        type=check_date_option,
        metavar="<YYYY-MM-DD>",
        help="the date of the expiry check of the waivers (default: the commit date of HEAD)",
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

    # trace: PRD-AI-004, PRD-AI-008
    # The subcommands "skills" and "mcp" read no configuration file and write
    # no report, so they have only the option --verbose of the common options.
    verbose = ArgumentParser(add_help=False, allow_abbrev=False, color=False)
    verbose.add_argument(
        "--verbose",
        action="store_true",
        help="write debug messages to standard error",
    )

    def add_other(name: str, summary: str, parent: Callable[..., ArgumentParser]) -> ArgumentParser:
        command = parent(
            name,
            parents=[verbose],
            help=summary,
            description=f"{summary[0].upper()}{summary[1:]}.",
            allow_abbrev=False,
            color=False,
        )
        command.set_defaults(config=None, output=None)
        return command

    skills_command = subcommands.add_parser(
        "skills",
        help="install the skills for AI agents",
        description="Install the skills for AI agents.",
        allow_abbrev=False,
        color=False,
    )
    skills_actions = skills_command.add_subparsers(
        dest="skills_command", metavar="<action>", required=True
    )
    install = add_other(
        "install", "write the skills for AI agents into the project", skills_actions.add_parser
    )
    install.add_argument(
        "--output",
        type=Path,
        metavar="<folder>",
        help=f"write the skills into this folder (default: {skills.DEFAULT_OUTPUT.as_posix()})",
    )

    mcp = add_other(
        "mcp", "start the local MCP server with the stdio transport", subcommands.add_parser
    )
    mcp.add_argument(
        "--project",
        type=Path,
        default=Path(),
        metavar="<folder>",
        help="the project folder of the server (default: the current folder)",
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


# trace: PRD-VAL-011
def read_baseline_model(args: argparse.Namespace, configuration: Configuration) -> Ir | None:
    """Make the IR of the baseline model, or give `None` if there is no baseline.

    `--baseline` gives the baseline. If it does not, the key `trace.baseline`
    of the configuration file gives it. A Git reference that does not exist
    stops the command with exit code 2.
    """
    ref: str | None = args.baseline if args.baseline is not None else configuration.trace.baseline
    if ref is None:
        return None
    LOG.debug("Baseline: %s.", ref)
    return read_baseline(ref, configuration, Path.cwd())


# trace: PRD-CORE-001, PRD-CORE-002, PRD-CORE-006, PRD-VAL-003, PRD-VAL-005, PRD-VAL-006
# trace: PRD-VAL-009, PRD-VAL-010, PRD-VAL-011
def run_validate(args: argparse.Namespace) -> Outcome:
    """Run all enabled rules on the IR and write the findings.

    The report is text, JSON or SARIF 2.1.0 (`--format`). In SARIF, each URI
    is relative to the folder of the configuration file. The exit code is 1
    if a finding has the severity `error`, or the severity `warning` with
    `--fail-on warning` (PRD-VAL-005). The IDN rules run only if there is a
    baseline (PRD-VAL-011).

    The report gives the waived findings in a separate group. A waived
    finding does not change the exit code (PRD-VAL-009). `--date` gives the
    date of the expiry check of the waivers. The default is the commit date
    of `HEAD` (PRD-VAL-010).
    """
    configuration = read_configuration(args)
    validator = Validator(configuration)
    baseline = read_baseline_model(args, configuration)
    ir = read_model(configuration)
    result = validator.validate(ir, baseline, check_date(ir, configuration.root, args.date))
    findings, waived = result.findings, result.waived
    if args.format == "sarif":
        base = Path(os.path.relpath(configuration.root.resolve(), Path.cwd().resolve()))
        version = toolchain_version()
        report = sarif_report(findings, validator.rules, version, base.as_posix(), waived)
    elif args.format == "json":
        report = json_report(findings, validator.rules, waived)
    else:
        report = text_report(findings, validator.rules, waived)
    write_report(report, args.output)
    return Outcome.ERROR_FINDING if fails(findings, args.fail_on) else Outcome.SUCCESS


# trace: PRD-CORE-001, PRD-CORE-002, PRD-CORE-003, PRD-CORE-004, PRD-CORE-005, PRD-CORE-043
# trace: PRD-VAL-003, PRD-VAL-009
def run_generate(args: argparse.Namespace) -> Outcome:
    """Validate the model, then write the generated files through the file writer.

    - The validator runs all enabled rules on the IR. An error finding stops
      the command before it writes a file. The exit code is 1 (PRD-CORE-003,
      PRD-VAL-003). A waived finding does not stop the command (PRD-VAL-009).
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
    today = check_date(ir, configuration.root, args.date)
    errors = [finding for finding in validator.run(ir, today=today) if finding.severity == "error"]
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


# trace: PRD-TRACE-016, PRD-TRACE-018
def read_trace_baseline(args: argparse.Namespace, configuration: Configuration) -> Baseline:
    """Make the IR of the baseline of the impact and suspect reports.

    `--baseline` gives the baseline. If it does not, the key `trace.baseline`
    of the configuration file gives it. If neither gives it, the baseline is
    the newest release tag `v*` before `HEAD` (Q54). If there is no baseline,
    the command stops with exit code 2.
    """
    cwd = Path.cwd()
    ref: str | None = args.baseline if args.baseline is not None else configuration.trace.baseline
    if ref is None:
        repository_root(cwd)
        ref = newest_release_tag(cwd)
        if ref is None:
            raise ToolchainError(
                f"There is no baseline for the {args.report} report. "
                "The repository has no release tag v* before HEAD. "
                "Give a baseline with --baseline <git-ref>, "
                "or set the key trace.baseline in the configuration file."
            )
    LOG.debug("Baseline: %s.", ref)
    return load_baseline(ref, configuration, cwd)


# trace: PRD-CORE-001, PRD-CORE-006, PRD-TRACE-010, PRD-TRACE-012, PRD-TRACE-013
# trace: PRD-TRACE-016, PRD-TRACE-017, PRD-TRACE-018
def run_trace(args: argparse.Namespace) -> Outcome:
    """Write a trace report as HTML, CSV or JSON.

    The coverage and orphans reports read the model, the trace manifest
    `.dsml/trace.gen.json` and the trace comments in the hand-written files
    of the output folders and the test folders. A trace comment that the
    reader cannot read gives a warning on standard error. These reports use
    no baseline.

    The impact and suspect reports compare the model with a Git baseline
    (PRD-TRACE-016). The impact report also reads the trace manifest.

    The exit code is 0, also if the report has a requirement with the status
    `missing`, an orphan, a changed element or a suspect link.
    """
    if args.report in (COVERAGE, ORPHANS) and args.baseline is not None:
        raise ToolchainError(
            f"The {args.report} report uses no baseline. Remove the option --baseline."
        )
    configuration = read_configuration(args)
    if args.report in (COVERAGE, ORPHANS):
        report = coverage_orphans_report(args.report, configuration)
    else:
        report = change_report(args, configuration)
    writers = {"csv": csv_report, "html": html_report, "json": json_trace_report}
    write_report(writers[args.format](report), args.output)
    return Outcome.SUCCESS


# trace: PRD-TRACE-010, PRD-TRACE-012, PRD-TRACE-013, PRD-TRACE-018
def coverage_orphans_report(name: str, configuration: Configuration) -> Report:
    """Make the coverage report or the orphans report."""
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
        generated=tuple((entry.element, entry.path) for entry in read_trace(root)),
        comments=found.comments,
        files=tuple(hand_written_files(root, folders, generated)),
        model_commit=model_commit(root),
    )
    return coverage_report(data) if name == COVERAGE else orphans_report(data)


# trace: PRD-TRACE-013, PRD-TRACE-015, PRD-TRACE-016, PRD-TRACE-018
def change_report(args: argparse.Namespace, configuration: Configuration) -> Report:
    """Make the impact report or the suspect report."""
    baseline = read_trace_baseline(args, configuration)
    ir = read_model(configuration)
    root = configuration.root
    entries = read_trace(root)
    data = ChangeData(
        ir=ir,
        baseline=baseline.ir,
        model_commit=model_commit(root),
        baseline_commit=baseline.commit,
        generated=tuple((entry.element, entry.path) for entry in entries),
        addresses=tuple(
            (entry.element, entry.name) for entry in entries if entry.kind == SymbolKind.RESOURCE
        ),
    )
    return impact_report(data) if args.report == IMPACT else suspect_report(data)


# trace: PRD-CORE-001, PRD-CORE-002, PRD-CORE-006, PRD-CORE-011, PRD-IAC-038
def run_check_output(args: argparse.Namespace) -> Outcome:
    """Run the language tools on the generated code of the selected targets.

    `--application <name>` selects one application and `--infrastructure`
    selects the infrastructure. With no option, the command checks all
    applications of the model and the infrastructure folder of the
    configuration file. Only an application check reads the model.

    The report gives one line for each tool and target, sorted by target and
    tool. The exit code is 1 if a tool finds an error or a tool is missing.
    """
    configuration = read_configuration(args)
    every = args.application is None and not args.infrastructure
    applications: list[ApplicationCode] = []
    if args.application is not None or (every and configuration.model):
        ir = read_model(configuration)
        applications = select_applications(ir, configuration, args.application)
    infrastructure = args.infrastructure or (every and configuration.infrastructure is not None)
    if not applications and not infrastructure:
        raise ToolchainError(
            "There is no generated code to check. The model has no application, "
            "and the configuration file gives no infrastructure folder."
        )
    results = check_output(configuration, applications, infrastructure)
    write_report(check_report(results), args.output)
    return Outcome.SUCCESS if passed(results) else Outcome.ERROR_FINDING


# trace: PRD-AI-004, PRD-AI-005, PRD-AI-006
def run_skills(args: argparse.Namespace) -> Outcome:
    """Write the skills of the package into `.claude/skills/` or the folder of `--output`.

    The command replaces only the skill folders that it owns. The report has
    one line for each skill, sorted by name: `install <folder>`.
    """
    output: Path = skills.DEFAULT_OUTPUT if args.output is None else args.output
    found = skills.package_skills()
    skills.install(output, found)
    lines = [f"install {(output / skill.name).as_posix()}\n" for skill in found]
    write_report("".join(lines), None)
    return Outcome.SUCCESS


MCP_MISSING = (
    'The command "dsml mcp" needs the optional dependency group "mcp".\n'
    "Install the toolchain with this group, for example: "
    'uv tool install --python 3.14 "dsml[mcp] @ <wheel-file>".'
)
"""The message of `dsml mcp` if the MCP Python SDK is not installed (PRD-AI-009)."""


# trace: PRD-AI-008, PRD-AI-009, PRD-AI-010, PRD-AI-014
def run_mcp(args: argparse.Namespace) -> Outcome:
    """Start the local MCP server in the project folder of `--project`.

    Only this subcommand imports the MCP Python SDK. If the SDK is not
    installed, the command stops with exit code 2 and gives the install
    command (Q69).
    """
    project = Project.open(args.project)
    try:
        from dsml.mcp.server import serve
    except ModuleNotFoundError as error:
        if error.name is None or error.name.partition(".")[0] != "mcp":
            raise
        raise ToolchainError(MCP_MISSING) from error
    LOG.debug("Start the MCP server in %s.", project.root)
    serve(project, toolchain_version())
    return Outcome.SUCCESS


HANDLERS: dict[str, Handler] = {
    "check-output": run_check_output,
    "generate": run_generate,
    "init": run_init,
    "ir": run_ir,
    "mcp": run_mcp,
    "skills": run_skills,
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
