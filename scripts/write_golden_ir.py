# trace: PRD-CORE-027, PRD-CORE-029
"""Write the golden IR files of the reference models again.

Story #33 added the golden IR files in tests/golden/ir/. The test
tests/test_ir_command.py compares the output of `dsml ir` with these files.
Run this script from the root of the repository after a change that changes
the IR, for example a new OpenSysML version (PRD-CORE-027):

    uv run python scripts/write_golden_ir.py

Then examine the differences with `git diff` before you commit them.
"""

import sys
from pathlib import Path

from dsml.cli import main as dsml

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "ir"
REFERENCE_MODELS: dict[str, tuple[str, ...]] = {
    "order-service": ("docs/model/examples/order-service.sysml",),
    "prd": tuple(
        sorted(
            path.relative_to(ROOT).as_posix() for path in (ROOT / "docs/model/prd").glob("*.sysml")
        )
    ),
}
"""The model files of each reference model, relative to the repository root."""


def golden_file(name: str) -> Path:
    """Give the golden IR file of a reference model."""
    return GOLDEN / f"{name}.ir.json"


def main() -> int:
    """Write the golden IR file of each reference model with `dsml ir`."""
    if Path.cwd().resolve() != ROOT:
        print(f"Run this script from the folder {ROOT}.", file=sys.stderr)
        return 2
    GOLDEN.mkdir(parents=True, exist_ok=True)
    for name, files in REFERENCE_MODELS.items():
        output = golden_file(name)
        code = dsml(["ir", *files, "--output", str(output.relative_to(ROOT))])
        if code != 0:
            print(f"dsml ir gave exit code {code} for the model {name}.", file=sys.stderr)
            return code
        print(f"Wrote {output.relative_to(ROOT).as_posix()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
