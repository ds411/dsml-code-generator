"""Tests of `dsml check-output` with fake tools on PATH (story #134).

Each fake tool is a shell script. It writes its arguments and its folder to
a log file. It stops with exit code 1 and a message if the environment
variable `FAKE_FAIL` has its name and its first argument, for example
`tofu-validate`.
"""

import os
from collections.abc import Callable
from pathlib import Path, PurePosixPath

import pytest

from dsml import cli
from dsml.check_output import (
    ApplicationCode,
    Result,
    Status,
    check_output,
    root_modules,
    select_applications,
    text_report,
    tflint_configuration,
)
from dsml.cli import main
from dsml.config import Application, Configuration
from dsml.errors import ToolchainError
from dsml.ir.model import Attribute, Element, EnumValue, Ir, Location
from dsml.versions import pinned_version

TOOLS = ("pyright", "ruff", "tflint", "tofu")
FAKE_TOOL = """#!/bin/sh
tool="${0##*/}"
echo "$tool $* | $PWD" >> "$FAKE_LOG"
name="$tool-$1"
case " $FAKE_FAIL " in
  *" $name "*) echo "$name found an error"; exit 1 ;;
esac
if [ "$name" = "tofu-init" ]; then mkdir -p .terraform; fi
exit 0
"""
ROOT_MODULES = ("infra/envs/dev", "infra/envs/prod")


@pytest.fixture
def fake_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Put the fake tools on PATH. Give the log file."""
    bin_folder = tmp_path / "bin"
    bin_folder.mkdir()
    for tool in TOOLS:
        script = bin_folder / tool
        script.write_text(FAKE_TOOL, encoding="utf-8")
        script.chmod(0o755)
    log = tmp_path / "tools.log"
    monkeypatch.setenv("PATH", str(bin_folder))
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.delenv("FAKE_FAIL", raising=False)
    return log


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make a project with an application folder and two root modules."""
    root = tmp_path / "project"
    (root / "services" / "orders" / "app").mkdir(parents=True)
    for module in ROOT_MODULES:
        (root / module).mkdir(parents=True)
        (root / module / "versions.gen.tf").write_text("terraform {}\n", encoding="utf-8")
    (root / "infra" / "modules" / "network").mkdir(parents=True)
    (root / "infra" / "modules" / "network" / "main.gen.tf").write_text("", encoding="utf-8")
    (root / "dsml.toml").write_text(
        'schema = 1\n\n[model]\npaths = ["model.sysml"]\n\n'
        '[applications.orders]\noutput = "services/orders"\n\n'
        '[infrastructure]\noutput = "infra"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(root)
    return root


def configuration(root: Path) -> Configuration:
    return Configuration(
        path=root / "dsml.toml",
        applications=(Application("orders", PurePosixPath("services/orders")),),
        infrastructure=PurePosixPath("infra"),
    )


ORDERS = ApplicationCode("orders", "fastapi", PurePosixPath("services/orders"))


def application(name: str, target: str) -> Element:
    return Element(
        identity=f"id-{name}",
        kind="Application",
        name=name,
        qualified_name=f"Model::{name}",
        location=Location("model.sysml", 1, 1),
        attributes=(Attribute("target", EnumValue("Target", target)),),
    )


def model_of(ir: Ir) -> Callable[[Configuration], Ir]:
    """Give a `read_model` that gives this IR, with no OpenSysML."""

    def read_model(_configuration: Configuration) -> Ir:
        return ir

    return read_model


def statuses(results: list[Result]) -> list[str]:
    return [f"{result.status} {result.target}: {result.tool}" for result in results]


def test_all_tools_pass(project: Path, fake_tools: Path) -> None:
    results = check_output(configuration(project), [ORDERS], infrastructure=True)
    assert statuses(results) == [
        "pass infra: tflint --init",
        "pass infra: tofu fmt",
        "pass infra/envs/dev: tflint",
        "pass infra/envs/dev: tofu init",
        "pass infra/envs/dev: tofu validate",
        "pass infra/envs/prod: tflint",
        "pass infra/envs/prod: tofu init",
        "pass infra/envs/prod: tofu validate",
        "pass services/orders: pyright",
        "pass services/orders: ruff check",
        "pass services/orders: ruff format",
    ]
    assert text_report(results).endswith(
        "pass services/orders: ruff format\nThe tools found no error.\n"
    )


def test_tools_get_the_arguments_of_prd_iac_038(project: Path, fake_tools: Path) -> None:
    check_output(configuration(project), [ORDERS], infrastructure=True)
    lines = fake_tools.read_text(encoding="utf-8").splitlines()
    calls = [line.split(" | ")[0].strip() for line in lines]
    assert "ruff check --no-cache" in calls
    assert "ruff format --check --no-cache" in calls
    assert "pyright" in calls
    assert "tofu fmt -check -recursive -diff -no-color" in calls
    assert calls.count("tofu init -backend=false -input=false -no-color") == 2
    assert calls.count("tofu validate -no-color") == 2
    lint = [call for call in calls if call.startswith("tflint --config=")]
    assert len(lint) == 2
    assert all(
        call.endswith("--call-module-type=local --format=compact --no-color") for call in lint
    )
    folders = {line.split(" | ")[0].strip(): line.split(" | ")[1] for line in lines}
    assert Path(folders["ruff check --no-cache"]) == project / "services" / "orders"
    assert Path(folders["tofu fmt -check -recursive -diff -no-color"]) == project / "infra"


def test_infrastructure_tools_run_on_a_copy(project: Path, fake_tools: Path) -> None:
    check_output(configuration(project), [], infrastructure=True)
    assert not any(path.name == ".terraform" for path in project.rglob("*"))
    lines = fake_tools.read_text(encoding="utf-8").splitlines()
    init = [line.split(" | ")[1] for line in lines if line.startswith("tofu init")]
    assert [Path(folder).parts[-2:] for folder in init] == [("envs", "dev"), ("envs", "prod")]
    assert all(not Path(folder).is_relative_to(project) for folder in init)


def test_tool_error_gives_the_output_of_the_tool(
    project: Path, fake_tools: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_FAIL", "ruff-format")
    results = check_output(configuration(project), [ORDERS], infrastructure=False)
    assert statuses(results) == [
        "pass services/orders: pyright",
        "pass services/orders: ruff check",
        "error services/orders: ruff format",
    ]
    assert text_report(results) == (
        "pass services/orders: pyright\n"
        "pass services/orders: ruff check\n"
        "error services/orders: ruff format\n"
        "    ruff-format found an error\n"
        "The check found errors. 1 step of 3 did not pass.\n"
    )


def test_validate_does_not_run_after_an_init_error(
    project: Path, fake_tools: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_FAIL", "tofu-init")
    results = check_output(configuration(project), [], infrastructure=True)
    found = {(result.target, result.tool): result for result in results}
    validate = found[("infra/envs/dev", "tofu validate")]
    assert validate.status == Status.NOT_RUN
    assert '"tofu init" on "infra/envs/dev" did not pass' in validate.output
    assert found[("infra/envs/dev", "tflint")].status == Status.PASS


def test_missing_tool_is_an_error_with_the_tool_name(
    project: Path, fake_tools: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (Path(os.environ["PATH"]) / "tflint").unlink()
    results = check_output(configuration(project), [], infrastructure=True)
    found = {(result.target, result.tool): result for result in results}
    assert found[("infra", "tflint --init")].status == Status.ERROR
    assert found[("infra", "tflint --init")].output == (
        'The tool "tflint" is missing. Put "tflint" on PATH.\n'
    )
    assert found[("infra/envs/dev", "tflint")].status == Status.NOT_RUN
    assert found[("infra/envs/dev", "tofu validate")].status == Status.PASS


def test_root_modules_are_the_folders_with_versions_gen_tf(project: Path) -> None:
    hidden = project / "infra" / "envs" / "dev" / ".terraform" / "modules" / "copy"
    hidden.mkdir(parents=True)
    (hidden / "versions.gen.tf").write_text("", encoding="utf-8")
    assert [module.as_posix() for module in root_modules(project / "infra")] == [
        "envs/dev",
        "envs/prod",
    ]


def test_tflint_configuration_has_the_pinned_aws_rule_set() -> None:
    text = tflint_configuration()
    assert f'version = "{pinned_version("tflint-ruleset-aws")}"' in text
    assert 'source  = "github.com/terraform-linters/tflint-ruleset-aws"' in text


def test_application_of_a_later_phase_is_an_error(project: Path, fake_tools: Path) -> None:
    web = ApplicationCode("web", "react", None)
    results = check_output(configuration(project), [web], infrastructure=False)
    assert statuses(results) == ["error web: react"]
    assert 'Its target "react" is not a phase 1 target.' in results[0].output


def test_select_applications_gives_the_target_and_the_folder(project: Path) -> None:
    ir = Ir(elements=(application("orders", "fastapi"), application("web", "react")))
    found = select_applications(ir, configuration(project), None)
    assert found == [ORDERS, ApplicationCode("web", "react", None)]
    assert select_applications(ir, configuration(project), "web") == [found[1]]
    with pytest.raises(ToolchainError, match='The model has no application "shop"'):
        select_applications(ir, configuration(project), "shop")


def test_command_gives_exit_code_0_and_the_report(
    project: Path,
    fake_tools: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ir = Ir(elements=(application("orders", "fastapi"),))
    monkeypatch.setattr(cli, "read_model", model_of(ir))
    assert main(["check-output", "--application", "orders"]) == 0
    assert capsys.readouterr().out == (
        "pass services/orders: pyright\n"
        "pass services/orders: ruff check\n"
        "pass services/orders: ruff format\n"
        "The tools found no error.\n"
    )


def test_command_with_no_option_checks_all_targets(
    project: Path, fake_tools: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ir = Ir(elements=(application("orders", "fastapi"),))
    monkeypatch.setattr(cli, "read_model", model_of(ir))
    assert main(["check-output", "--output", "report.txt"]) == 0
    report = (project / "report.txt").read_text(encoding="utf-8")
    assert "pass infra/envs/prod: tofu validate\n" in report
    assert "pass services/orders: pyright\n" in report


def test_command_infrastructure_does_not_read_the_model(
    project: Path, fake_tools: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_model(_configuration: Configuration) -> Ir:
        raise AssertionError("The command read the model.")

    monkeypatch.setattr(cli, "read_model", no_model)
    assert main(["check-output", "--infrastructure", "--output", "report.txt"]) == 0


def test_command_gives_exit_code_1_for_a_missing_tool(
    project: Path, fake_tools: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (Path(os.environ["PATH"]) / "tofu").unlink()
    assert main(["check-output", "--infrastructure"]) == 1
    out = capsys.readouterr().out
    assert 'The tool "tofu" is missing. Put "tofu" on PATH.' in out
    assert out.endswith("did not pass.\n")


def test_command_gives_exit_code_1_for_a_tool_error(
    project: Path,
    fake_tools: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("FAKE_FAIL", "tofu-validate")
    assert main(["check-output", "--infrastructure"]) == 1
    out = capsys.readouterr().out
    assert "error infra/envs/dev: tofu validate\n    tofu-validate found an error\n" in out


def test_missing_infrastructure_key_gives_exit_code_2(
    project: Path, fake_tools: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / "dsml.toml").write_text("schema = 1\n", encoding="utf-8")
    assert main(["check-output", "--infrastructure"]) == 2
    assert capsys.readouterr().err == (
        "dsml: error: The configuration file gives no infrastructure folder. "
        "Add the key infrastructure.output.\n"
    )


def test_missing_output_folder_gives_exit_code_2(
    project: Path, fake_tools: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / "dsml.toml").write_text(
        'schema = 1\n\n[infrastructure]\noutput = "deploy"\n', encoding="utf-8"
    )
    assert main(["check-output", "--infrastructure"]) == 2
    assert 'The infrastructure folder "deploy" does not exist.' in capsys.readouterr().err
