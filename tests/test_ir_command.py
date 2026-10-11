"""Tests of the subcommand `dsml ir` and of the golden IR files (story #33).

CI runs these tests on Linux x64, Linux arm64 and macOS arm64. Thus the
comparison with the golden IR files makes sure that the IR is byte-identical
on the three platforms (PRD-CORE-027, PRD-CORE-028, PRD-CORE-029).

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


@pytest.mark.parametrize("elements", [8, 20, 25])
def test_generated_model_has_the_given_number_of_elements(elements: int, tmp_path: Path) -> None:
    (tmp_path / "large-model.sysml").write_text(measure_ir.make_model(elements), encoding="utf-8")
    _, ir = measure_ir.run_ir(tmp_path)
    data = json.loads(ir)
    assert len(data["elements"]) == elements
    assert data["findings"] == []


def test_generated_model_needs_eight_or_more_elements() -> None:
    with pytest.raises(ValueError, match="8 or more elements"):
        measure_ir.make_model(7)
