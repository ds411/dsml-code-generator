# trace: PRD-CORE-030, PRD-IAC-001
"""Write the golden infrastructure files of the example model again.

Story #76 added the golden files in tests/golden/infrastructure/. The test
tests/test_infrastructure_generator.py compares the output of
`dsml generate --infrastructure` with these files. Run this script from the
root of the repository after a change that changes the infrastructure
output:

    uv run python scripts/write_golden_infrastructure.py

Then examine the differences with `git diff` before you commit them.

The example model has no secret store. Thus the script also writes the
golden files of the test model `tests/models/ir/solution-layers.sysml`
(story #79). This model is not valid for `dsml generate`, so the script calls
the generator directly. These golden files have the generated files and the
trace manifest, but not the manifest `.dsml/generated.json`.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath

from dsml.adapter.convert import make_ir
from dsml.cli import main as dsml
from dsml.config import Configuration
from dsml.generate.infrastructure.generator import InfrastructureGenerator
from dsml.generate.trace import TRACE_PATH, trace_bytes, trace_entries

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "infrastructure"
REFERENCE_MODELS: dict[str, Path] = {
    "order-service": ROOT / "docs" / "model" / "examples" / "order-service.sysml",
}
"""The model file of each reference model."""

TEST_MODELS: dict[str, Path] = {
    "shop": ROOT / "tests" / "models" / "ir" / "solution-layers.sysml",
}
"""The model file of each test model that the script gives to the generator directly."""

CONFIGURATION = """schema = 1

[model]
paths = ["model"]

[infrastructure]
output = "infra"
"""
"""The configuration file of the golden output."""

MODEL_FOLDER = "model"


def golden_folder(name: str) -> Path:
    """Give the golden folder of a reference model."""
    return GOLDEN / name


def read_tree(folder: Path) -> dict[str, bytes]:
    """Give the bytes of each file in a folder, by path relative to the folder."""
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def generate(name: str, work: Path, configuration: str = CONFIGURATION) -> dict[str, bytes]:
    """Run `dsml generate --infrastructure` on a reference model in the empty folder `work`.

    The result gives the bytes of each output file, with the manifests, by
    path relative to `work`. It does not include the model and the
    configuration file.
    """
    (work / MODEL_FOLDER).mkdir()
    model = REFERENCE_MODELS[name]
    shutil.copy(model, work / MODEL_FOLDER / model.name)
    (work / "dsml.toml").write_text(configuration, encoding="utf-8", newline="\n")
    previous = Path.cwd()
    os.chdir(work)
    try:
        code = dsml(["generate", "--infrastructure", "--output", os.devnull])
    finally:
        os.chdir(previous)
    if code != 0:
        raise RuntimeError(f"dsml generate gave exit code {code} for the model {name}.")
    return {
        path: content
        for path, content in read_tree(work).items()
        if path != "dsml.toml" and not path.startswith(f"{MODEL_FOLDER}/")
    }


def generate_test_model(name: str) -> dict[str, bytes]:
    """Give the generator output of a test model, and its trace manifest, by path."""
    model = TEST_MODELS[name]
    ir = make_ir([model.relative_to(ROOT)], ROOT)
    configuration = Configuration(infrastructure=PurePosixPath("infra"))
    files = InfrastructureGenerator().generate(ir, configuration, None)
    result = {file.path: file.content for file in files}
    result[TRACE_PATH] = trace_bytes(
        entry for file in files for entry in trace_entries(file.path, file.symbols)
    )
    return result


def _write(folder: Path, files: dict[str, bytes]) -> None:
    """Replace the golden folder with the files."""
    shutil.rmtree(folder, ignore_errors=True)
    for path, content in files.items():
        target = folder / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    print(f"Wrote {len(files)} files in {folder.relative_to(ROOT).as_posix()}.")


def main() -> int:
    """Write the golden files of each reference model."""
    if Path.cwd().resolve() != ROOT:
        print(f"Run this script from the folder {ROOT}.", file=sys.stderr)
        return 2
    for name in REFERENCE_MODELS:
        with tempfile.TemporaryDirectory() as work:
            files = generate(name, Path(work))
        _write(golden_folder(name), files)
    for name in TEST_MODELS:
        _write(golden_folder(name), generate_test_model(name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
