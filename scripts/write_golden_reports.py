# trace: PRD-CORE-030, PRD-TRACE-013, PRD-TRACE-017
"""Write the golden trace reports of the example model again.

Story #72 added the golden reports in tests/golden/trace/, and story #74
added the HTML reports. The test tests/test_trace_reports.py compares the
output of `dsml trace` with these files. Run this script from the root of
the repository after a change that changes the reports, for example a new
generator that writes trace manifest entries:

    uv run python scripts/write_golden_reports.py

Then examine the differences with `git diff` before you commit them.

The script writes the example project in a temporary folder that is not in
a Git repository. Thus the model commit of the golden reports is the text
for a folder that is not in a Git repository.
"""

import contextlib
import os
import shutil
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

from dsml.cli import main as dsml

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "trace"
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
REPORTS = ("coverage", "orphans")
FORMATS = ("csv", "html", "json")

CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.orderApi]
output = "app"

[trace]
tests = ["tests"]
"""

HAND_WRITTEN_FILES = {
    "app/features/order/read_order/test_endpoint.py": (
        "# trace: R-001, V-001\ndef test_order_status() -> None:\n    pass\n"
    ),
    "app/features/order/cancel_order/handler.py": (
        "# trace: OrderService::orderApi, R-404\nasync def handle() -> None:\n    pass\n"
    ),
    "tests/test_smoke.py": "def test_smoke() -> None:\n    pass\n",
}
"""The hand-written files of the example project.

- `test_endpoint.py` is the test file of the verification V-001.
- `handler.py` has a trace comment with the unknown ID R-404.
- `test_smoke.py` is a test file that no verification names.
"""


def write_project(folder: Path) -> None:
    """Write the example project: the configuration, the model and the hand-written files."""
    (folder / "dsml.toml").write_text(CONFIGURATION, encoding="utf-8", newline="\n")
    (folder / "model").mkdir()
    shutil.copyfile(EXAMPLE_MODEL, folder / "model" / EXAMPLE_MODEL.name)
    for name, text in HAND_WRITTEN_FILES.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def golden_file(report: str, report_format: str) -> Path:
    """Give the golden file of one report in one format."""
    return GOLDEN / f"order-service.{report}.{report_format}"


@contextlib.contextmanager
def outside_git() -> Generator[None]:
    """Make sure that Git does not find a repository above the temporary folder."""
    base = Path(tempfile.gettempdir())
    old = os.environ.get("GIT_CEILING_DIRECTORIES")
    os.environ["GIT_CEILING_DIRECTORIES"] = os.pathsep.join(
        sorted({str(base), str(base.resolve())})
    )
    try:
        yield
    finally:
        if old is None:
            del os.environ["GIT_CEILING_DIRECTORIES"]
        else:
            os.environ["GIT_CEILING_DIRECTORIES"] = old


def main() -> int:
    """Write each golden report with `dsml trace`."""
    GOLDEN.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary, outside_git():
        project = Path(temporary) / "project"
        project.mkdir()
        write_project(project)
        with contextlib.chdir(project):
            for report in REPORTS:
                for report_format in FORMATS:
                    output = golden_file(report, report_format)
                    code = dsml(
                        ["trace", report, "--format", report_format, "--output", str(output)]
                    )
                    if code != 0:
                        print(f"dsml trace gave exit code {code}.", file=sys.stderr)
                        return code
                    print(f"Wrote {output.relative_to(ROOT).as_posix()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
