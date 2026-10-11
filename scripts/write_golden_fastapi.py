# trace: PRD-CORE-030
"""Write the golden files of the FastAPI generator again.

Story #75 added the golden output of the example model in
tests/golden/fastapi/order-service/. Story #84 added the golden output of
the test model tests/models/fastapi/shop.sysml in tests/golden/fastapi/shop/.
The tests tests/test_fastapi_generator.py and tests/test_fastapi_slices.py
compare the output of the FastAPI generator with these files. The CI job
"FastAPI golden project" runs ruff, pyright and pytest on each golden
project. Run this script from the root of the repository after a change to
the generator or to its templates:

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
SHOP_MODEL = ROOT / "tests" / "models" / "fastapi" / "shop.sysml"
GOLDEN = ROOT / "tests" / "golden" / "fastapi" / "order-service"
SHOP_GOLDEN = ROOT / "tests" / "golden" / "fastapi" / "shop"
CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.orderApi]
output = "services/order-api"
"""
"""The configuration file of the golden output of the example model."""

SHOP_CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.shopApi]
output = "services/shop-api"
"""
"""The configuration file of the golden output of the shop model."""

GOLDENS = (
    (GOLDEN, EXAMPLE_MODEL, CONFIGURATION),
    (SHOP_GOLDEN, SHOP_MODEL, SHOP_CONFIGURATION),
)
"""The golden folder, the model and the configuration file of each golden output."""


def write_output(
    folder: Path, model: Path = EXAMPLE_MODEL, configuration_text: str = CONFIGURATION
) -> None:
    """Write the output of the FastAPI generator for a model into `folder`.

    The folder gets the generated files and the manifests in `.dsml/`, but
    not the configuration file.
    """
    configuration = parse_configuration(configuration_text, folder / "dsml.toml")
    ir = make_ir([model], ROOT)
    files = collect([FastApiGenerator()], ir, configuration, None)
    apply_plan(folder, make_plan(folder, files, None))


def main() -> int:
    """Write the golden output of the example model and of the shop model."""
    if Path.cwd().resolve() != ROOT:
        print(f"Run this script from the folder {ROOT}.", file=sys.stderr)
        return 2
    for golden, model, configuration in GOLDENS:
        if golden.exists():
            shutil.rmtree(golden)
        golden.mkdir(parents=True)
        write_output(golden, model, configuration)
        print(f"Wrote {golden.relative_to(ROOT).as_posix()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
