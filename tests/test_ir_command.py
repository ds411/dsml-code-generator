"""Tests of the subcommand `dsml ir` and of the golden IR files (story #33).

CI runs these tests on Linux x64 (Q62). The comparison with the golden IR
files makes sure that the IR does not change (PRD-CORE-027, PRD-CORE-028,
PRD-CORE-029).

Most tests start a private `sysml-grpc` child process. If the binary is not
in the cache, the `opensysml` client downloads it one time.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import jsonschema
import pytest
from jsonschema.protocols import Validator

from dsml.cli import main
from dsml.ir.schema import load_schema

ROOT = Path(__file__).resolve().parent.parent
SYN_001 = ROOT / "tests" / "models" / "rules" / "SYN-001"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "write_golden_ir", ROOT / "scripts/write_golden_ir.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


write_golden_ir: Any = _load_script()
REFERENCE_MODELS: dict[str, tuple[str, ...]] = write_golden_ir.REFERENCE_MODELS


def _validator() -> Validator:
    return jsonschema.Draft202012Validator(load_schema())


@pytest.fixture(autouse=True)
def _in_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)


# trace: PRD-CORE-027, PRD-CORE-028, PRD-CORE-029
@pytest.mark.parametrize("name", sorted(REFERENCE_MODELS))
def test_ir_of_reference_model_agrees_with_golden_file(name: str, tmp_path: Path) -> None:
    output = tmp_path / "ir.json"
    assert main(["ir", *REFERENCE_MODELS[name], "--output", str(output)]) == 0
    golden: Path = write_golden_ir.golden_file(name)
    assert output.read_bytes() == golden.read_bytes(), (
        f"The IR of the model {name} is not the same as {golden.relative_to(ROOT)}. "
        "If the change is correct, run scripts/write_golden_ir.py."
    )


@pytest.mark.parametrize("name", sorted(REFERENCE_MODELS))
def test_golden_file_agrees_with_the_ir_schema(name: str) -> None:
    golden: Path = write_golden_ir.golden_file(name)
    data = json.loads(golden.read_bytes())
    _validator().validate(data)
    assert data["files"] == list(REFERENCE_MODELS[name])
    assert data["elements"]
    assert data["findings"] == []


# trace: PRD-CORE-006
def test_ir_writes_to_standard_output() -> None:
    files = REFERENCE_MODELS["order-service"]
    result = subprocess.run(
        [sys.executable, "-m", "dsml", "ir", *files],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert result.stderr == b""
    assert result.stdout == write_golden_ir.golden_file("order-service").read_bytes()


def test_order_of_the_files_does_not_change_the_ir(tmp_path: Path) -> None:
    files = REFERENCE_MODELS["prd"]
    output = tmp_path / "ir.json"
    assert main(["ir", *reversed(files), "--output", str(output)]) == 0
    assert output.read_bytes() == write_golden_ir.golden_file("prd").read_bytes()


# trace: PRD-DSML-039, PRD-DSML-040
def test_ir_of_order_web_allocates_the_nextjs_application_to_a_container_service() -> None:
    data = json.loads(write_golden_ir.golden_file("order-web").read_bytes())
    kinds = {element["identity"]: element["kind"] for element in data["elements"]}
    links = {(link["type"], link["source"], link["target"]) for link in data["links"]}
    application = "OrderWeb::orderWeb"
    target = next(
        attribute["value"]["literal"]
        for element in data["elements"]
        if element["identity"] == application
        for attribute in element["attributes"]
        if attribute["name"] == "target"
    )
    assert target == "nextjs"
    assert ("allocate", application, "OrderWeb::webService") in links
    assert kinds["OrderWeb::webService"] == "ContainerService"
    uses = sorted(
        kinds[t] for kind, source, t in links if (kind, source) == ("uses", "OrderWeb::webService")
    )
    assert uses == ["RelationalDatabase", "SecretStore", "UserDirectory"]
    assert data["findings"] == []


# trace: PRD-CORE-002
def test_syn_error_gives_exit_code_1_and_the_ir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "ir.json"
    model = (SYN_001 / "reject.sysml").relative_to(ROOT).as_posix()
    assert main(["ir", model, "--output", str(output)]) == 1
    assert capsys.readouterr().err == ""
    data = json.loads(output.read_bytes())
    assert data["files"] == [model]
    assert [finding["rule"] for finding in data["findings"]] == ["SYN-001"]


# trace: PRD-CORE-002
def test_model_with_no_error_gives_exit_code_0(capsys: pytest.CaptureFixture[str]) -> None:
    model = (SYN_001 / "accept.sysml").relative_to(ROOT).as_posix()
    assert main(["ir", model]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["findings"] == []


# trace: PRD-CORE-002
def test_ir_with_no_model_file_gives_exit_code_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["ir"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("dsml: error: Give one or more model files ")


# trace: PRD-CORE-002, PRD-CORE-033
def test_model_file_outside_the_current_folder_gives_exit_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    model = tmp_path / "model.sysml"
    model.write_text("package Model;\n", encoding="utf-8")
    assert main(["ir", str(model)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"dsml: error: The model file {model} is not in the folder {ROOT}.\n"


# trace: PRD-CORE-002
def test_missing_model_file_gives_exit_code_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["ir", "missing.sysml"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("dsml: error: Cannot read the model file missing.sysml: ")


def _load_measure_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("measure_ir", ROOT / "scripts/measure_ir.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


measure_ir: Any = _load_measure_script()


# trace: PRD-TOP-012
@pytest.mark.parametrize("elements", [23, 29, 36])
def test_generated_model_has_the_given_number_of_elements(elements: int, tmp_path: Path) -> None:
    (tmp_path / "large-model.sysml").write_text(measure_ir.make_model(elements), encoding="utf-8")
    _, ir = measure_ir.run_ir(tmp_path)
    data = json.loads(ir)
    assert len(data["elements"]) == elements
    assert data["findings"] == []


def test_generated_model_needs_twenty_three_or_more_elements() -> None:
    with pytest.raises(ValueError, match="23 or more elements"):
        measure_ir.make_model(22)


# trace: PRD-TOP-012
def test_generated_model_validates_and_generates_all_parts(tmp_path: Path) -> None:
    measure_ir.write_project(tmp_path, 30)
    _, findings = measure_ir.run_validate(tmp_path)
    assert findings.decode().splitlines()[-1] == "Findings: 0 errors, 0 warnings, 0 info."
    for _ in range(2):
        _, output = measure_ir.run_generate(tmp_path)
        files = [line.removeprefix("add ") for line in output.decode().splitlines()]
        assert all(line.startswith("add ") for line in output.decode().splitlines())
        assert "services/items/app/main_gen.py" in files
        assert "infra/modules/container-service/main.gen.tf" in files
        assert ".github/workflows/pr.gen.yml" in files


# trace: PRD-TOP-012
@pytest.mark.parametrize(
    ("validate", "generate", "elements", "failed"),
    [
        (9_999.0, 9_999.0, 1000, []),
        (10_000.0, 9_999.0, 1000, ["dsml validate"]),
        (9_999.0, 12_000.0, 1000, ["dsml generate"]),
        (10_000.0, 10_000.0, 500, ["dsml validate", "dsml generate"]),
        (60_000.0, 60_000.0, 10_000, []),
    ],
)
def test_limit_of_validate_and_generate(
    validate: float, generate: float, elements: int, failed: list[str]
) -> None:
    medians = {"dsml ir": 20_000.0, "dsml validate": validate, "dsml generate": generate}
    assert measure_ir.over_limit(medians, elements) == failed
