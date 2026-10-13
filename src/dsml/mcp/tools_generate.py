# trace: PRD-AI-011, PRD-AI-012, PRD-AI-013, PRD-AI-014, PRD-AI-018
"""MCP tools for generation and reports: `generate`, `check_output`, `trace` and `version`.

Each tool runs its subcommand through `dsml.cli.main`, the function of the
command `dsml`. Thus the tool and the subcommand give the same result for
the same model, configuration and toolchain version (PRD-AI-012). The tool
does not copy the logic of the subcommand.

The tool catches the report that the subcommand writes to standard output,
and the messages that it writes to standard error. The tool gives them as
structured data. A lock lets only one subcommand run at a time, because the
catch replaces `sys.stdout` and `sys.stderr` of the process.

The tools have no `--output` option and no `--overwrite` option
(PRD-AI-011). Thus only `generate` writes files, and it stops on a changed
generated file (PRD-AI-013).
"""

import io
import os
import re
import threading
from collections.abc import Sequence
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field

from dsml.cli import main
from dsml.errors import ToolchainError
from dsml.mcp.project import Project

_LOCK = threading.Lock()
"""Only one subcommand runs at a time, because the catch of its output replaces `sys.stdout`."""

DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
"""The form of the option `--date`: YYYY-MM-DD."""

EXIT_CODES = (
    " The exit code is the exit code of the subcommand: 0 for success, "
    "1 for an error finding or a difference, and 2 for a usage error or an internal error."
)
"""The text about the exit code in the description of each tool."""

Config = Annotated[
    str | None,
    Field(
        description=(
            "The configuration file, relative to the project folder. "
            "The default is dsml.toml in the project folder."
        )
    ),
]


# trace: PRD-AI-012
@dataclass(frozen=True)
class Run:
    """The result of one subcommand."""

    exit_code: int
    """The exit code of the subcommand."""
    report: str
    """The text that the subcommand wrote to standard output."""
    messages: list[str]
    """The lines that the subcommand wrote to standard error."""


# trace: PRD-AI-012, PRD-AI-014
def run_command(project: Project, argv: Sequence[str]) -> Run:
    """Run the command `dsml` with `argv` and catch its output.

    The current folder must be the project folder, because the subcommand
    reads its paths relative to the current folder (PRD-AI-014).
    """
    if Path.cwd().resolve() != project.root:
        raise ToolError("The current folder of the server is not the project folder.")
    with _LOCK:
        stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", newline="")
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(list(argv))
        stdout.flush()
        buffer = stdout.buffer
        assert isinstance(buffer, io.BytesIO)
        report = buffer.getvalue().decode("utf-8")
    return Run(exit_code, report, stderr.getvalue().splitlines())


# trace: PRD-AI-014
def config_options(project: Project, config: str | None) -> list[str]:
    """Give the option `--config` for the configuration file in the project folder.

    A path outside the project folder gives a tool error (PRD-AI-014).
    """
    if config is None:
        return []
    try:
        path = project.path(config)
    except ToolchainError as error:
        raise ToolError(str(error)) from error
    return [f"--config={os.path.relpath(path, project.root)}"]


# trace: PRD-CORE-004
class FileChange(BaseModel):
    """One file that a run adds, changes or deletes."""

    action: Literal["add", "change", "delete"]
    path: str = Field(description="The path of the file, relative to the configuration file.")


# trace: PRD-CORE-003, PRD-CORE-004, PRD-CORE-043
class GenerateResult(BaseModel):
    """The result of the tool `generate`."""

    exit_code: int
    changes: list[FileChange] = Field(
        description=(
            "Each file that the run added, changed or deleted. "
            "In check mode, each file that a normal run adds, changes or deletes."
        )
    )
    messages: list[str] = Field(
        description="The error findings, the changed generated files and the other messages."
    )


# trace: PRD-CORE-011
class CheckStep(BaseModel):
    """The result of one language tool on one target."""

    target: str = Field(description="The folder of the target, relative to the configuration file.")
    tool: str
    status: Literal["pass", "error", "not run"]
    output: list[str] = Field(description="The output of a tool that did not pass, line by line.")


# trace: PRD-CORE-011
class CheckOutputResult(BaseModel):
    """The result of the tool `check_output`."""

    exit_code: int
    steps: list[CheckStep]
    summary: str = Field(description="The last line of the report.")
    messages: list[str]


# trace: PRD-TRACE-010, PRD-TRACE-016
class TraceResult(BaseModel):
    """The result of the tool `trace`."""

    exit_code: int
    report: str = Field(description="The text of the report, in the format that you selected.")
    messages: list[str] = Field(description="The warnings, for example a bad trace comment.")


# trace: PRD-CORE-001
class VersionResult(BaseModel):
    """The result of the tool `version`."""

    toolchain: str
    dsml_library: str
    opensysml: str
    ir_schema: str


_STEP = re.compile(r"^(pass|error|not run) (.+): ([^:]+)$")
"""A line of the check-output report with the result of one tool on one target."""


# trace: PRD-CORE-004
def file_changes(report: str) -> list[FileChange]:
    """Read the report of `dsml generate`: one line `<action> <path>` for each file."""
    changes: list[FileChange] = []
    for line in report.splitlines():
        action, _, path = line.partition(" ")
        changes.append(FileChange.model_validate({"action": action, "path": path}))
    return changes


# trace: PRD-CORE-011
def check_steps(report: str) -> tuple[list[CheckStep], str]:
    """Read the report of `dsml check-output`. Give the steps and the summary line.

    A step line has the form `<status> <target>: <tool>`. The output of a
    tool that did not pass follows its step line, with an indent of four
    spaces. The last line is the summary.
    """
    lines = report.splitlines()
    if not lines:
        return [], ""
    steps: list[CheckStep] = []
    for line in lines[:-1]:
        if line.startswith("    ") or line == "":
            if steps:
                steps[-1].output.append(line.removeprefix("    "))
            continue
        match = _STEP.match(line)
        if match is None:
            raise ToolError(f'The tool cannot read this line of the report: "{line}".')
        steps.append(
            CheckStep.model_validate(
                {"status": match[1], "target": match[2], "tool": match[3], "output": []}
            )
        )
    return steps, lines[-1]


# trace: PRD-CORE-001
def version_fields(report: str) -> VersionResult:
    """Read the report of `dsml version`: one line `<component>: <version>` for each component."""
    values = dict(line.split(": ", 1) for line in report.splitlines())
    return VersionResult(
        toolchain=values["toolchain"],
        dsml_library=values["DSML library"],
        opensysml=values["OpenSysML"],
        ir_schema=values["IR schema"],
    )


# trace: PRD-AI-011, PRD-AI-012, PRD-AI-013, PRD-AI-014, PRD-AI-018
def register(server: MCPServer[Any], project: Project) -> None:
    """Add the contents of this module to the server. The server operates in `project`."""

    # trace: PRD-CORE-003, PRD-CORE-004, PRD-CORE-005, PRD-CORE-042, PRD-CORE-043
    # trace: PRD-AI-013
    @server.tool(
        name="generate",
        description=(
            "Validate the model, then write the generated files, like the command dsml generate. "
            "An error finding stops the tool before it writes a file. "
            "In check mode, the tool writes no file. It gives each file that a normal run "
            "adds, changes or deletes. "
            "If a generated file is different from its hash in the manifest, the tool writes "
            "no file and gives the changed files. The tool has no overwrite option. "
            "The tool does not change a hand-written file." + EXIT_CODES
        ),
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False
        ),
    )
    def generate(
        check: Annotated[
            bool, Field(description="If true, write no file and give the list of changes.")
        ] = False,
        application: Annotated[
            str | None, Field(description="Generate only the files of this application.")
        ] = None,
        infrastructure: Annotated[
            bool, Field(description="Generate only the infrastructure files.")
        ] = False,
        pipelines: Annotated[bool, Field(description="Generate only the pipeline files.")] = False,
        date: Annotated[
            str | None,
            Field(
                description=(
                    "The date of the expiry check of the waivers, in the form YYYY-MM-DD. "
                    "The default is the commit date of HEAD."
                ),
                pattern=DATE_PATTERN,
            ),
        ] = None,
        config: Config = None,
    ) -> GenerateResult:
        argv = ["generate", *config_options(project, config)]
        if application is not None:
            argv.append(f"--application={application}")
        if infrastructure:
            argv.append("--infrastructure")
        if pipelines:
            argv.append("--pipelines")
        if check:
            argv.append("--check")
        if date is not None:
            argv.append(f"--date={date}")
        run = run_command(project, argv)
        return GenerateResult(
            exit_code=run.exit_code, changes=file_changes(run.report), messages=run.messages
        )

    # trace: PRD-CORE-011
    @server.tool(
        name="check_output",
        description=(
            "Run the language tools on the generated code, like the command dsml check-output. "
            "The tool gives the result of each tool on each target. "
            "With no option, the tool checks all applications and the infrastructure. "
            "The tool does not change a file in the project folder." + EXIT_CODES
        ),
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
        ),
    )
    def check_output(
        application: Annotated[
            str | None, Field(description="Check only the code of this application.")
        ] = None,
        infrastructure: Annotated[
            bool, Field(description="Check only the infrastructure code.")
        ] = False,
        config: Config = None,
    ) -> CheckOutputResult:
        argv = ["check-output", *config_options(project, config)]
        if application is not None:
            argv.append(f"--application={application}")
        if infrastructure:
            argv.append("--infrastructure")
        run = run_command(project, argv)
        steps, summary = check_steps(run.report)
        return CheckOutputResult(
            exit_code=run.exit_code, steps=steps, summary=summary, messages=run.messages
        )

    # trace: PRD-TRACE-010, PRD-TRACE-012, PRD-TRACE-013, PRD-TRACE-016, PRD-TRACE-018
    @server.tool(
        name="trace",
        description=(
            "Make a trace report, like the command dsml trace. "
            "The report coverage gives the status of each requirement. "
            "The report orphans gives the elements and files with no trace. "
            "The reports impact and suspect compare the model with a Git baseline. "
            "The default format is json." + EXIT_CODES
        ),
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
        ),
    )
    def trace(
        report: Annotated[
            Literal["coverage", "orphans", "impact", "suspect"],
            Field(description="The report to make."),
        ],
        format: Annotated[
            Literal["json", "csv", "html"], Field(description="The format of the report.")
        ] = "json",
        baseline: Annotated[
            str | None,
            Field(
                description=(
                    "The Git reference of the baseline of the reports impact and suspect. "
                    "The default is the key trace.baseline of the configuration file, "
                    "or the newest release tag before HEAD."
                )
            ),
        ] = None,
        config: Config = None,
    ) -> TraceResult:
        argv = ["trace", report, f"--format={format}", *config_options(project, config)]
        if baseline is not None:
            argv.append(f"--baseline={baseline}")
        run = run_command(project, argv)
        return TraceResult(exit_code=run.exit_code, report=run.report, messages=run.messages)

    # trace: PRD-CORE-001
    @server.tool(
        name="version",
        description=(
            "Give the versions of the toolchain, the DSML library, OpenSysML and the IR schema, "
            "like the command dsml version."
        ),
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
        ),
    )
    def version() -> VersionResult:
        run = run_command(project, ["version"])
        return version_fields(run.report)
