# trace: PRD-AI-011, PRD-AI-012, PRD-AI-013, PRD-AI-014, PRD-AI-018
"""MCP tools for the model: `init`, `validate` and `ir`.

Each tool makes the command line of its subcommand and calls `dsml.cli.main`.
Thus the tool and the subcommand use the same functions, and they give the
same report and the same exit code (PRD-AI-012). The tool gets the report
from standard output and gives it to the AI agent:

- Exit code 0 or 1: the tool gives the exit code and the report.
- Exit code 2: the tool gives an MCP tool error with the error message.

Before the tool calls the subcommand, it makes sure that each path is in the
project folder (PRD-AI-014). Only the tool `init` writes files. It writes
only the create-once starter files (PRD-AI-013).
"""

import argparse
import io
import json
import threading
from collections.abc import Sequence
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Annotated, Any, Final, Literal, TypedDict

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import Field

from dsml import cli, starter
from dsml.errors import ToolchainError
from dsml.mcp.project import Project

PREFIX: Final = f"{cli.PROG}: error: "
"""The start of each error line of the command `dsml`."""

LOCK: Final = threading.Lock()
"""The lock of standard output and standard error.

The server runs each tool in a worker thread. A tool replaces standard
output and standard error while its subcommand runs. Thus only one tool can
run a subcommand at a time.
"""

Target = Literal["fastapi", "react", "nextjs"]
"""The targets of `dsml init`. They are the same as `starter.TARGETS`."""


class Result(TypedDict):
    """The result of a tool: the exit code and the report of its subcommand."""

    exit_code: int
    """0 if the subcommand found no error. 1 if it found an error finding."""
    report: Any
    """The report. A JSON report is a JSON value. A different report is text."""


Config = Annotated[
    str | None,
    Field(
        description="The configuration file, relative to the project folder. "
        "The default is dsml.toml in the project folder."
    ),
]


# trace: PRD-CORE-002, PRD-AI-012, PRD-AI-014
def run(project: Project, argv: Sequence[str]) -> tuple[int, str]:
    """Run the command `dsml` with `argv`. Give the exit code and the report.

    The server starts in the project folder, so the current folder must be
    the project folder. Exit code 2 gives `ToolError` with the error lines
    of the command, with no prefix and no usage line.
    """
    if Path.cwd().resolve() != project.root:
        raise ToolError("The current folder of the server is not the project folder.")
    buffer = io.BytesIO()
    stdout = io.TextIOWrapper(buffer, encoding="utf-8", newline="")
    stderr = io.StringIO()
    with LOCK, redirect_stdout(stdout), redirect_stderr(stderr):
        code = cli.main(list(argv))
        stdout.flush()
    if code == cli.Outcome.FAILURE:
        lines = stderr.getvalue().splitlines()
        raise ToolError(
            "\n".join(line.removeprefix(PREFIX) for line in lines if line.startswith(PREFIX))
        )
    return code, buffer.getvalue().decode("utf-8")


# trace: PRD-AI-014
def check_path(project: Project, text: str | Path) -> None:
    """Make sure that the path `text` is in the project folder. If not, raise `ToolError`."""
    try:
        project.path(text)
    except ToolchainError as error:
        raise ToolError(str(error)) from error


# trace: PRD-AI-014
def config_options(project: Project, config: str | None) -> list[str]:
    """Give the option `--config` of the command line. The file must be in the project folder."""
    if config is None:
        return []
    check_path(project, config)
    return ["--config", config]


# trace: PRD-AI-014
def check_model_paths(project: Project, config: str | None) -> None:
    """Make sure that each model path of the configuration file is in the project folder.

    The function reads the configuration file with the function of the CLI.
    If the file has an error, the function does nothing: the subcommand then
    gives the error.
    """
    try:
        configuration = cli.read_configuration(
            argparse.Namespace(config=None if config is None else Path(config))
        )
    except ToolchainError:
        return
    for entry in configuration.model:
        check_path(project, configuration.root / entry)


# trace: PRD-AI-011, PRD-AI-013, PRD-AI-014, PRD-CORE-042, PRD-CORE-044
def init(project: Project, target: Target, config: str | None) -> Result:
    """Run `dsml init`. Each starter file must be in the project folder."""
    options = config_options(project, config)
    root = Path() if config is None else Path(config).parent
    for name in starter.starter_files(target):
        if name != starter.CONFIG_FILE:
            check_path(project, root / name)
    code, report = run(project, ["init", "--target", target, *options])
    return {"exit_code": code, "report": report}


# trace: PRD-AI-011, PRD-AI-012, PRD-AI-014, PRD-CORE-001, PRD-VAL-005, PRD-VAL-010
def validate(
    project: Project,
    report_format: str,
    fail_on: str,
    baseline: str | None,
    check_date: str | None,
    config: str | None,
) -> Result:
    """Run `dsml validate`. A JSON or SARIF report is a JSON value in the result."""
    options = config_options(project, config)
    check_model_paths(project, config)
    argv = ["validate", "--format", report_format, "--fail-on", fail_on, *options]
    if baseline is not None:
        argv += ["--baseline", baseline]
    if check_date is not None:
        argv += ["--date", check_date]
    code, report = run(project, argv)
    return {"exit_code": code, "report": report if report_format == "text" else json.loads(report)}


# trace: PRD-AI-011, PRD-AI-012, PRD-AI-014, PRD-CORE-001, PRD-CORE-028
def ir(
    project: Project,
    model: Sequence[str],
    config: str | None,
    parts: Sequence[str] | None,
    kinds: Sequence[str] | None,
    names: Sequence[str] | None,
) -> Result:
    """Run `dsml ir`, then keep only the selected parts of the IR.

    With no selection, the report is the full IR, the same as `dsml ir`.
    `kinds` and `names` select elements. A link stays if its source or its
    target is a selected element. `parts` selects the top-level parts.
    """
    options = config_options(project, config)
    for path in model:
        check_path(project, path)
    if not model:
        check_model_paths(project, config)
    code, report = run(project, ["ir", *options, *(["--", *model] if model else [])])
    data: dict[str, Any] = json.loads(report)
    return {"exit_code": code, "report": select(data, parts, kinds, names)}


# trace: PRD-AI-011
def select(
    data: dict[str, Any],
    parts: Sequence[str] | None,
    kinds: Sequence[str] | None,
    names: Sequence[str] | None,
) -> dict[str, Any]:
    """Keep only the selected parts and elements of the IR `data`.

    An element is selected if its kind is in `kinds`, and if its identity,
    name or qualified name is in `names`. An empty selection selects all.
    The order of the IR does not change.
    """
    if kinds or names:
        elements = [
            element
            for element in data["elements"]
            if (not kinds or element["kind"] in kinds)
            and (
                not names
                or {element["identity"], element["name"], element["qualifiedName"]} & set(names)
            )
        ]
        keys = {
            key for element in elements for key in (element["identity"], element["qualifiedName"])
        }
        data = data | {
            "elements": elements,
            "links": [
                link for link in data["links"] if link["source"] in keys or link["target"] in keys
            ],
        }
    if parts:
        data = {key: value for key, value in data.items() if key == "irVersion" or key in parts}
    return data


# trace: PRD-AI-011, PRD-AI-018
def register(server: MCPServer[Any], project: Project) -> None:
    """Add the tools `init`, `validate` and `ir` to the server. The server operates in `project`."""

    @server.tool(
        name="init",
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=False, idempotent_hint=True
        ),
    )
    def init_tool(
        target: Annotated[Target, Field(description="The target of the starter files.")] = (
            "fastapi"
        ),
        config: Config = None,
    ) -> Result:
        """Write a starter configuration file and a starter model, the same as "dsml init".

        The tool writes the configuration file to dsml.toml, or to the path of "config".
        It writes the model into the folder "model" next to the configuration file.
        It writes only a file that does not exist. It does not change a file that exists.
        The report has one line for each file.
        """
        return init(project, target, config)

    @server.tool(name="validate", annotations=ToolAnnotations(read_only_hint=True))
    def validate_tool(
        format: Annotated[
            Literal["text", "json", "sarif"],
            Field(description="The format of the findings. JSON gives structured data."),
        ] = "json",
        fail_on: Annotated[
            Literal["error", "warning"],
            Field(description="The exit code is 1 if a finding has this severity or a higher one."),
        ] = "error",
        baseline: Annotated[
            str | None,
            Field(description="A Git reference of the baseline model for the identity rules."),
        ] = None,
        date: Annotated[
            str | None,
            Field(
                description="The date of the expiry check of the waivers, in the form YYYY-MM-DD. "
                "The default is the commit date of HEAD."
            ),
        ] = None,
        config: Config = None,
    ) -> Result:
        """Validate the model and give the findings, the same as "dsml validate".

        The model files come from the configuration file.
        With the JSON format, the report has the findings, the waived findings and a summary.
        The exit code is 0 if the validator found no error finding, and 1 if it found one.
        Correct each error finding, then use the tool again.
        """
        return validate(project, format, fail_on, baseline, date, config)

    @server.tool(name="ir", annotations=ToolAnnotations(read_only_hint=True))
    def ir_tool(
        model: Annotated[
            list[str] | None,
            Field(
                description="The SysML v2 files of the model, relative to the project folder. "
                "If you give no file, the files come from the configuration file."
            ),
        ] = None,
        config: Config = None,
        parts: Annotated[
            list[Literal["constraintResults", "elements", "files", "findings", "links"]] | None,
            Field(description="Give only these parts of the IR. The default is all parts."),
        ] = None,
        kinds: Annotated[
            list[str] | None,
            Field(description='Give only the elements of these kinds, for example "Requirement".'),
        ] = None,
        names: Annotated[
            list[str] | None,
            Field(
                description="Give only the elements with these identities, names "
                "or qualified names."
            ),
        ] = None,
    ) -> Result:
        """Give the IR of the model as JSON, the same as "dsml ir".

        The IR is the intermediate representation that the validator and the generators read.
        To make the IR of a large model smaller, select parts, kinds or names.
        A link stays in the IR if its source or its target is a selected element.
        The exit code is 1 if the IR has an error finding, for example a syntax error.
        """
        return ir(project, model or [], config, parts, kinds, names)
