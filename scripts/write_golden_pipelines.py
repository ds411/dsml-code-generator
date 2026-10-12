# trace: PRD-CORE-030, PRD-CICD-001
"""Write the golden files of the pipeline generator again.

Stories #83, #87 and #89 added the golden output of the example model in
tests/golden/pipelines/order-service/. Story #165 added the golden output
of the phase 2 reference model in tests/golden/pipelines/order-portal/. The
tests tests/test_pipeline_generator.py and tests/test_pipeline_deploy.py
compare the output of the pipeline generator with these files. The CI step
"Lint the golden workflows" runs actionlint on the golden workflows. Run
this script from the root of the repository after a change to the generator
or to its templates:

    uv run python scripts/write_golden_pipelines.py

Then examine the differences with `git diff` before you commit them.
"""

import shutil
import sys
from pathlib import Path

from dsml.adapter.convert import make_ir
from dsml.config import parse_configuration
from dsml.generate.generators import collect
from dsml.generate.pipelines.generator import PipelineGenerator
from dsml.generate.writer import apply_plan, make_plan

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
PORTAL_MODEL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
GOLDEN = ROOT / "tests" / "golden" / "pipelines" / "order-service"
CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.orderApi]
output = "services/order-api"

[infrastructure]
output = "infra"

[pipelines]
output = ".github/workflows"
"""
"""The configuration file of the golden output of the example model."""

PORTAL_CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.orderApi]
output = "services/order-api"

[applications.orderPortal]
output = "apps/order-portal"

[infrastructure]
output = "infra"

[pipelines]
output = ".github/workflows"
"""
"""The configuration file of the golden output of the order portal."""

MODELS = {
    "order-portal": (PORTAL_MODEL, PORTAL_CONFIGURATION),
    "order-service": (EXAMPLE_MODEL, CONFIGURATION),
}
"""The model file and the configuration file of each golden output, by folder name."""


def golden_folder(name: str) -> Path:
    """Give the folder of the golden output of a model."""
    return ROOT / "tests" / "golden" / "pipelines" / name


def write_output(folder: Path, name: str = "order-service") -> None:
    """Write the output of the pipeline generator for a model into `folder`.

    The folder gets the generated files and the manifests in `.dsml/`, but
    not the configuration file.
    """
    model, text = MODELS[name]
    configuration = parse_configuration(text, folder / "dsml.toml")
    ir = make_ir([model], ROOT)
    files = collect([PipelineGenerator()], ir, configuration, None)
    apply_plan(folder, make_plan(folder, files, None))


def main() -> int:
    """Write the golden output of each model."""
    if Path.cwd().resolve() != ROOT:
        print(f"Run this script from the folder {ROOT}.", file=sys.stderr)
        return 2
    for name in sorted(MODELS):
        golden = golden_folder(name)
        if golden.exists():
            shutil.rmtree(golden)
        golden.mkdir(parents=True)
        write_output(golden, name)
        print(f"Wrote {golden.relative_to(ROOT).as_posix()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
