# trace: PRD-CORE-030
"""Write the golden files of the Next.js generator again.

Story #180 added the golden output of the order web model
docs/model/examples/order-web/order-web.sysml in
tests/golden/nextjs/order-web/. The folder is the project folder of the
application orderWeb. It has the schema snapshot `.dsml/schema-snapshot.json`
of story #182, but no manifests in `.dsml/`. The script removes the folder
first, thus the generator writes the migrations again from no snapshot. The test
tests/test_nextjs_generator.py compares the output of the Next.js generator
with these files. The CI job "Next.js golden project" runs Prettier, tsc,
ESLint, Steiger, Vitest, "next build" and "docker build" on the golden
project. Run this script from the root of the repository after a change to
the generator or to its templates:

    uv run python scripts/write_golden_nextjs.py

Then examine the differences with `git diff` before you commit them.
"""

import shutil
import sys
from pathlib import Path

from dsml.adapter.convert import make_ir
from dsml.config import parse_configuration
from dsml.generate.generators import collect
from dsml.generate.nextjs import NextjsGenerator

ROOT = Path(__file__).resolve().parent.parent
WEB_MODEL = ROOT / "docs" / "model" / "examples" / "order-web" / "order-web.sysml"
WEB_GOLDEN = ROOT / "tests" / "golden" / "nextjs" / "order-web"
CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.orderWeb]
output = "order-web"
"""
"""The configuration file of the golden output. It is in the parent folder of the golden
folder, and the output folder is the golden folder. The output folder must not be the
folder of the configuration file, because the generator must not write into the manifest
folder `.dsml/` of the configuration file."""


def write_output(folder: Path) -> None:
    """Write the generated files and the create-once files of the order web into `folder`.

    The name of `folder` must be `order-web`.
    """
    configuration = parse_configuration(CONFIGURATION, folder.parent / "dsml.toml")
    ir = make_ir([WEB_MODEL], ROOT)
    for file in collect([NextjsGenerator()], ir, configuration, None):
        path = folder.parent / file.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file.content)


def main() -> int:
    """Write the golden output of the order web."""
    if Path.cwd().resolve() != ROOT:
        print(f"Run this script from the folder {ROOT}.", file=sys.stderr)
        return 2
    if WEB_GOLDEN.exists():
        shutil.rmtree(WEB_GOLDEN)
    WEB_GOLDEN.mkdir(parents=True)
    write_output(WEB_GOLDEN)
    print(f"Wrote {WEB_GOLDEN.relative_to(ROOT).as_posix()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
