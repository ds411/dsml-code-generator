# trace: PRD-CORE-030
"""Write the golden files of the FastAPI generator again.

Story #75 added the golden output of the example model in
tests/golden/fastapi/order-service/. The test
tests/test_fastapi_generator.py compares the output of the FastAPI generator
with these files. The CI job "FastAPI golden project" runs ruff, pyright and
pytest on the golden project. Run this script from the root of the
repository after a change to the generator or to its templates:

    uv run python scripts/write_golden_fastapi.py

Then examine the differences with `git diff` before you commit them.
"""

import shutil
import sys
from pathlib import Path

from dsml.adapter.convert import make_ir
from dsml.config import parse_configuration
from dsml.generate.fastapi import FastApiGenerator
from dsml.generate.generators import collect
from dsml.generate.writer import apply_plan, make_plan

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
GOLDEN = ROOT / "tests" / "golden" / "fastapi" / "order-service"
CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.orderApi]
output = "services/order-api"
"""
"""The configuration file of the golden output."""


def write_output(folder: Path) -> None:
    """Write the output of the FastAPI generator for the example model into `folder`.

    The folder gets the generated files and the manifests in `.dsml/`, but
    not the configuration file.
    """
    configuration = parse_configuration(CONFIGURATION, folder / "dsml.toml")
    ir = make_ir([EXAMPLE_MODEL], ROOT)
    files = collect([FastApiGenerator()], ir, configuration, None)
    apply_plan(folder, make_plan(folder, files, None))


def main() -> int:
    """Write the golden output of the example model."""
    if Path.cwd().resolve() != ROOT:
        print(f"Run this script from the folder {ROOT}.", file=sys.stderr)
        return 2
    if GOLDEN.exists():
        shutil.rmtree(GOLDEN)
    GOLDEN.mkdir(parents=True)
    write_output(GOLDEN)
    print(f"Wrote {GOLDEN.relative_to(ROOT).as_posix()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
