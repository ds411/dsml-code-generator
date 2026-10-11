# trace: PRD-CORE-028, PRD-CORE-030, PRD-VAL-006, PRD-VAL-007
"""Write the golden findings of the reference models again.

Story #68 added the golden findings in tests/golden/validate/. The test
tests/test_rule_catalog.py compares the output of `dsml validate` with these
files, as text, JSON and SARIF. Run this script from the root of the
repository after a change that changes the findings, for example a new rule
or a change in a reference model:

    uv run python scripts/write_golden_findings.py

Then examine the differences with `git diff` before you commit them.

Each reference model has a configuration file in its folder. The SARIF
report gives the version of the toolchain, thus a new version also changes
the SARIF files.
"""

import sys
from pathlib import Path

from dsml.cli import main as dsml

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "validate"
REFERENCE_MODELS: dict[str, str] = {
    "order-service": "docs/model/examples/dsml.toml",
    "prd": "docs/model/prd/dsml.toml",
}
"""The configuration file of each reference model, relative to the repository root."""

FORMATS: dict[str, str] = {"text": "txt", "json": "json", "sarif": "sarif"}
"""The file extension of each format of `dsml validate`."""


def golden_file(name: str, report_format: str) -> Path:
    """Give the golden findings file of a reference model in one format."""
    return GOLDEN / f"{name}.findings.{FORMATS[report_format]}"


def validate(name: str, report_format: str, output: Path) -> int:
    """Run `dsml validate` on a reference model and write the findings to `output`.

    Give the exit code. The exit code 1 tells that there is an error finding.
    """
    return dsml(
        [
            "validate",
            "--config",
            REFERENCE_MODELS[name],
            "--format",
            report_format,
            "--output",
            str(output),
        ]
    )


def main() -> int:
    """Write the golden findings of each reference model in each format."""
    if Path.cwd().resolve() != ROOT:
        print(f"Run this script from the folder {ROOT}.", file=sys.stderr)
        return 2
    GOLDEN.mkdir(parents=True, exist_ok=True)
    for name in REFERENCE_MODELS:
        for report_format in FORMATS:
            output = golden_file(name, report_format)
            code = validate(name, report_format, output)
            if code not in (0, 1):
                print(f"dsml validate gave exit code {code} for the model {name}.", file=sys.stderr)
                return code
            print(f"Wrote {output.relative_to(ROOT).as_posix()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
