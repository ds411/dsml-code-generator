# trace: PRD-CORE-011, PRD-IAC-038, PRD-APP-234, PRD-APP-306
"""Run the language tools on the generated code: the subcommand `dsml check-output`.

The tools of each phase 1 target are:

- FastAPI application: `ruff check`, `ruff format --check` and `pyright`.
  The tools run in the output folder of the application. pyright reads the
  virtual environment `.venv` of the project, thus `uv sync` must run first.
- React application and Next.js application: `tsc --noEmit`, `eslint .`
  and `steiger ./src`. The tools run in the output folder of the
  application. They come from the folder `node_modules/.bin` of the
  project, thus `pnpm install` must run first.
- Infrastructure: `tofu fmt -check` on the output folder, then
  `tofu init -backend=false`, `tofu validate` and `tflint` with the AWS rule
  set on each root module (PRD-IAC-038). A root module is a folder with the
  file `versions.gen.tf`.

`tofu init` writes the folder `.terraform` and a lock file. Thus the
infrastructure tools other than `tofu fmt` run on a temporary copy of the
output folder. The generated folder does not change.

The tools come from `PATH`. The tools of a React application and of a
Next.js application come first from `node_modules/.bin`, then from `PATH`.
A missing tool is an error with the tool name (PRD-CORE-011).
"""

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final

from dsml import versions
from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.ir.model import EnumValue, Ir

FASTAPI: Final = "fastapi"
"""The target of a FastAPI application in the model."""

REACT: Final = "react"
"""The target of a React application in the model."""

NEXTJS: Final = "nextjs"
"""The target of a Next.js application in the model."""

NODE_TOOLS: Final = PurePosixPath("node_modules/.bin")
"""The folder of the tools of a Node.js project, relative to its output folder."""

ROOT_MODULE_FILE: Final = "versions.gen.tf"
"""Each root module of the infrastructure has this file."""

TOOL_ENVIRONMENT: Final = {"NO_COLOR": "1", "TF_IN_AUTOMATION": "1", "TF_INPUT": "0"}
"""The environment variables that the command adds for the tools."""


# trace: PRD-CORE-011
class Status(StrEnum):
    """The result of one tool on one target."""

    PASS = "pass"
    ERROR = "error"
    NOT_RUN = "not run"


# trace: PRD-CORE-011
@dataclass(frozen=True, slots=True)
class Step:
    """One tool to run on one target.

    `target` is the folder of the target, relative to the folder of the
    configuration file. `needs` gives the tool of the same target, or the
    target and the tool, that must pass before this tool can run. If
    `tools` is not `None`, the step looks for the tool in this folder
    before `PATH`.
    """

    target: str
    tool: str
    argv: tuple[str, ...]
    folder: Path
    needs: tuple[str, str] | None = None
    tools: Path | None = None


# trace: PRD-CORE-011
@dataclass(frozen=True, slots=True)
class Result:
    """The result of one step. `output` is the text that the tool wrote."""

    target: str
    tool: str
    status: Status
    output: str = ""


# trace: PRD-CORE-011
@dataclass(frozen=True, slots=True)
class ApplicationCode:
    """An application to check: its name, its target and its output folder."""

    name: str
    target: str | None
    folder: PurePosixPath | None


# trace: PRD-CORE-005, PRD-CORE-011
def select_applications(
    ir: Ir, configuration: Configuration, name: str | None
) -> list[ApplicationCode]:
    """Give the applications of the model to check, sorted by name.

    With a name, the function gives only that application. It must be an
    application of the model.
    """
    found: dict[str, ApplicationCode] = {}
    for element in ir.elements:
        if element.kind != "Application":
            continue
        target = next(
            (
                attribute.value.literal
                for attribute in element.attributes
                if attribute.name == "target" and isinstance(attribute.value, EnumValue)
            ),
            None,
        )
        settings = configuration.application(element.name)
        folder = None if settings is None else settings.output
        found[element.name] = ApplicationCode(element.name, target, folder)
    if name is None:
        return [found[key] for key in sorted(found)]
    if name not in found:
        known = ", ".join(sorted(found)) if found else "none"
        raise ToolchainError(
            f'The model has no application "{name}". The applications of the model are: {known}.'
        )
    return [found[name]]


# trace: PRD-CORE-011
def check_output(
    configuration: Configuration,
    applications: Sequence[ApplicationCode],
    infrastructure: bool,
    environment: Mapping[str, str] | None = None,
) -> list[Result]:
    """Run the tools on the selected targets and give the results, sorted by target and tool.

    `environment` gives the environment of the tools. The default is the
    environment of the toolchain.
    """
    root = configuration.root
    env = {**(os.environ if environment is None else environment), **TOOL_ENVIRONMENT}
    results: list[Result] = []
    steps: list[Step] = []
    for application in applications:
        if application.target == FASTAPI:
            steps.extend(fastapi_steps(root, application))
        elif application.target == REACT:
            steps.extend(react_steps(root, application))
        elif application.target == NEXTJS:
            steps.extend(nextjs_steps(root, application))
        else:
            results.append(_not_supported(application))
    if not infrastructure:
        return sorted(results + run_steps(steps, env), key=_order)
    with tempfile.TemporaryDirectory(prefix="dsml-check-output-") as temporary:
        steps.extend(infrastructure_steps(configuration, Path(temporary)))
        results.extend(run_steps(steps, env))
    return sorted(results, key=_order)


def _order(result: Result) -> tuple[str, str]:
    return (result.target, result.tool)


def _not_supported(application: ApplicationCode) -> Result:
    target = application.target or "none"
    label = application.name if application.folder is None else application.folder.as_posix()
    return Result(
        label,
        target,
        Status.ERROR,
        f'This version cannot check the application "{application.name}". '
        f'It has no tools for the target "{target}".\n',
    )


# trace: PRD-CORE-011, PRD-APP-016
def fastapi_steps(root: Path, application: ApplicationCode) -> list[Step]:
    """Give the tools of one FastAPI application: ruff and pyright."""
    folder, target = _output_folder(root, application)
    return [
        Step(target, "ruff check", ("ruff", "check", "--no-cache"), folder),
        Step(target, "ruff format", ("ruff", "format", "--check", "--no-cache"), folder),
        Step(target, "pyright", ("pyright",), folder),
    ]


# trace: PRD-CORE-011, PRD-APP-016, PRD-APP-234
def react_steps(root: Path, application: ApplicationCode) -> list[Step]:
    """Give the tools of one React application: `tsc`, ESLint and Steiger."""
    return _node_steps(root, application)


# trace: PRD-CORE-011, PRD-APP-016, PRD-APP-306
def nextjs_steps(root: Path, application: ApplicationCode) -> list[Step]:
    """Give the tools of one Next.js application: `tsc`, ESLint and Steiger.

    The tools are the same as the tools of a React application. Steiger
    reads the generated `steiger.config.ts` of the Next.js project.
    """
    return _node_steps(root, application)


def _node_steps(root: Path, application: ApplicationCode) -> list[Step]:
    """Give `tsc`, ESLint and Steiger for one Node.js project.

    The tools come first from the folder `node_modules/.bin` of the project.
    The path of this folder is absolute, because the tools run in the output
    folder.
    """
    folder, target = _output_folder(root, application)
    tools = (folder / NODE_TOOLS).absolute()
    return [
        Step(target, "tsc", ("tsc", "--noEmit"), folder, tools=tools),
        Step(target, "eslint", ("eslint", "."), folder, tools=tools),
        Step(target, "steiger", ("steiger", "./src"), folder, tools=tools),
    ]


def _output_folder(root: Path, application: ApplicationCode) -> tuple[Path, str]:
    if application.folder is None:
        raise ToolchainError(
            f'The configuration file gives no output folder for the application "'
            f'{application.name}". Add the key applications.{application.name}.output.'
        )
    folder = root / application.folder
    if not folder.is_dir():
        raise ToolchainError(
            f'The output folder "{application.folder.as_posix()}" of the application '
            f'"{application.name}" does not exist. Run "dsml generate" first.'
        )
    return folder, application.folder.as_posix()


# trace: PRD-IAC-038
def tflint_configuration() -> str:
    """Give the tflint configuration with the AWS rule set of the version baseline."""
    version = versions.pinned_version("tflint-ruleset-aws")
    return (
        'plugin "aws" {\n'
        "  enabled = true\n"
        f'  version = "{version}"\n'
        '  source  = "github.com/terraform-linters/tflint-ruleset-aws"\n'
        "}\n"
    )


# trace: PRD-IAC-038
def root_modules(folder: Path) -> list[PurePosixPath]:
    """Give each root module of the infrastructure folder, relative to it and sorted.

    The function does not look in a folder with a name that starts with ".",
    for example `.terraform`.
    """
    found = {
        PurePosixPath(path.parent.relative_to(folder).as_posix())
        for path in folder.rglob(ROOT_MODULE_FILE)
        if path.is_file()
        and not any(part.startswith(".") for part in path.relative_to(folder).parts)
    }
    return sorted(found, key=lambda module: module.as_posix())


# trace: PRD-IAC-038
def infrastructure_steps(configuration: Configuration, temporary: Path) -> list[Step]:
    """Give the tools of the infrastructure. The function copies the folder to `temporary`.

    `tofu fmt -check` runs on the output folder. The other tools run on the
    copy, because `tofu init` writes files.
    """
    if configuration.infrastructure is None:
        raise ToolchainError(
            "The configuration file gives no infrastructure folder. "
            "Add the key infrastructure.output."
        )
    name = configuration.infrastructure
    folder = configuration.root / name
    if not folder.is_dir():
        raise ToolchainError(
            f'The infrastructure folder "{name.as_posix()}" does not exist. '
            'Run "dsml generate" first.'
        )
    modules = root_modules(folder)
    if not modules:
        raise ToolchainError(
            f'The infrastructure folder "{name.as_posix()}" has no root module. '
            f"A root module is a folder with the file {ROOT_MODULE_FILE}."
        )
    copy = temporary / "infrastructure"
    shutil.copytree(folder, copy, ignore=shutil.ignore_patterns(".terraform"))
    config = temporary / "tflint.hcl"
    config.write_text(tflint_configuration(), encoding="utf-8", newline="\n")
    label = name.as_posix()
    steps = [
        Step(
            label, "tofu fmt", ("tofu", "fmt", "-check", "-recursive", "-diff", "-no-color"), folder
        ),
        Step(label, "tflint --init", ("tflint", "--init", f"--config={config}"), copy),
    ]
    for module in modules:
        target = (name / module).as_posix()
        where = copy / module
        steps += [
            Step(
                target,
                "tofu init",
                ("tofu", "init", "-backend=false", "-input=false", "-no-color"),
                where,
            ),
            Step(
                target,
                "tofu validate",
                ("tofu", "validate", "-no-color"),
                where,
                (target, "tofu init"),
            ),
            Step(
                target,
                "tflint",
                (
                    "tflint",
                    f"--config={config}",
                    "--call-module-type=local",
                    "--format=compact",
                    "--no-color",
                ),
                where,
                (label, "tflint --init"),
            ),
        ]
    return steps


# trace: PRD-CORE-009, PRD-CORE-011
def run_steps(steps: Iterable[Step], environment: Mapping[str, str]) -> list[Result]:
    """Run the steps in their order and give one result for each step.

    A missing tool is an error with the tool name. A step does not run if
    the step that it needs did not pass. The tools get no input (PRD-CORE-009).
    """
    results: dict[tuple[str, str], Result] = {}
    for step in steps:
        results[(step.target, step.tool)] = _run(step, environment, results)
    return list(results.values())


def _run(
    step: Step, environment: Mapping[str, str], earlier: Mapping[tuple[str, str], Result]
) -> Result:
    if step.needs is not None and earlier[step.needs].status != Status.PASS:
        target, tool = step.needs
        return Result(
            step.target,
            step.tool,
            Status.NOT_RUN,
            f'The step did not run, because "{tool}" on "{target}" did not pass.\n',
        )
    program = step.argv[0]
    search = environment.get("PATH", os.defpath)
    if step.tools is not None:
        search = os.pathsep.join((str(step.tools), search))
        environment = {**environment, "PATH": search}
    executable = shutil.which(program, path=search)
    if executable is None:
        where = f'Put "{program}" on PATH.'
        if step.tools is not None:
            where = f'Run "pnpm install" in "{step.target}", or put "{program}" on PATH.'
        return Result(
            step.target,
            step.tool,
            Status.ERROR,
            f'The tool "{program}" is missing. {where}\n',
        )
    completed = subprocess.run(
        (executable, *step.argv[1:]),
        cwd=step.folder,
        env=dict(environment),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = completed.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")
    status = Status.PASS if completed.returncode == 0 else Status.ERROR
    if status == Status.ERROR and not output.strip():
        output = f"The tool stopped with exit code {completed.returncode}.\n"
    return Result(step.target, step.tool, status, output)


# trace: PRD-CORE-006, PRD-CORE-011
def text_report(results: Sequence[Result]) -> str:
    """Give the report: one line for each result, then a summary line.

    The report gives the output of each tool that did not pass, with an
    indent of four spaces.
    """
    lines: list[str] = []
    for result in results:
        lines.append(f"{result.status} {result.target}: {result.tool}")
        if result.status != Status.PASS:
            lines.extend(f"    {line}".rstrip() for line in result.output.strip("\n").splitlines())
    failed = sum(1 for result in results if result.status != Status.PASS)
    if failed == 0:
        lines.append("The tools found no error.")
    else:
        steps = "1 step" if failed == 1 else f"{failed} steps"
        lines.append(f"The check found errors. {steps} of {len(results)} did not pass.")
    return "".join(f"{line}\n" for line in lines)


# trace: PRD-CORE-002
def passed(results: Sequence[Result]) -> bool:
    """Give `True` if each tool passed."""
    return all(result.status == Status.PASS for result in results)
