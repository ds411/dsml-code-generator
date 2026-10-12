# trace: PRD-CORE-030
"""Write the golden files of the React generator again.

Story #167 added the golden output of the order portal model
docs/model/examples/order-portal/order-portal.sysml in
tests/golden/react/order-portal/. The folder is the project folder of the
application orderPortal. It has no manifests in `.dsml/`: the phase 2 exit
story adds them. The test tests/test_react_generator.py compares the output
of the React generator with these files. The CI job "React golden project"
runs Prettier, tsc, ESLint, Steiger, Vitest and "pnpm build" on the golden
project. Run this script from the root of the repository after a change to
the generator or to its templates:

    uv run python scripts/write_golden_react.py

Then examine the differences with `git diff` before you commit them.

The script also writes the golden output of the external API model
tests/models/react/external-api/external-api.sysml (story #175) in
tests/golden/react/external-api/.
"""

import shutil
import sys
from pathlib import Path

from dsml.adapter.convert import make_ir
from dsml.config import parse_configuration
from dsml.generate.generators import collect
from dsml.generate.react import ReactGenerator

ROOT = Path(__file__).resolve().parent.parent
PORTAL_MODEL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
PORTAL_GOLDEN = ROOT / "tests" / "golden" / "react" / "order-portal"
EXTERNAL_MODEL = ROOT / "tests" / "models" / "react" / "external-api" / "external-api.sysml"
EXTERNAL_GOLDEN = ROOT / "tests" / "golden" / "react" / "external-api"
CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.orderPortal]
output = "."

[applications.petPortal]
output = "."
"""
"""The configuration file of the golden output. The output folder is the golden folder.

The application `petPortal` of the external API model (story #175) is in
the same file. A model has only one of the two applications.
"""


def write_output(folder: Path, model: Path = PORTAL_MODEL) -> None:
    """Write the output files of the React generator for a model into `folder`.

    The function writes the generated files and the create-once files, but
    no manifest.
    """
    configuration = parse_configuration(CONFIGURATION, folder / "dsml.toml")
    ir = make_ir([model], ROOT)
    for file in collect([ReactGenerator()], ir, configuration, None):
        path = folder / file.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file.content)


def main() -> int:
    """Write the golden output of the order portal."""
    if Path.cwd().resolve() != ROOT:
        print(f"Run this script from the folder {ROOT}.", file=sys.stderr)
        return 2
    for model, golden in ((PORTAL_MODEL, PORTAL_GOLDEN), (EXTERNAL_MODEL, EXTERNAL_GOLDEN)):
        if golden.exists():
            shutil.rmtree(golden)
        golden.mkdir(parents=True)
        write_output(golden, model)
        print(f"Wrote {golden.relative_to(ROOT).as_posix()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
