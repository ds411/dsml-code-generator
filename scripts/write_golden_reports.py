# trace: PRD-CORE-030, PRD-TRACE-013, PRD-TRACE-017, PRD-TRACE-018
"""Write the golden trace reports of the example model and of the reference models again.

Story #72 added the golden coverage and orphans reports in
tests/golden/trace/. Story #74 added the HTML reports, and story #73 added
the golden impact and suspect reports. The tests tests/test_trace_reports.py
and tests/test_trace_changes.py compare the output of `dsml trace` with
these files. Run this script from the root of the repository after a change
that changes the reports, for example a new generator that writes trace
manifest entries:

    uv run python scripts/write_golden_reports.py

Then examine the differences with `git diff` before you commit them.

For the coverage and orphans reports, the script writes the example project
in a temporary folder that is not in a Git repository. Thus the model commit
of these reports is the text for a folder that is not in a Git repository.

For the impact and suspect reports, the script makes a temporary Git
repository. The first commit has the example project and the tag `v1.0.0`.
The second commit changes the requirement R-001 and the entity `Order`, and
adds a trace manifest. The commits have fixed authors and dates, thus the
commit hashes in the reports are the same at each run.

The phase 2 exit story (#177) added the golden reports of the order portal
model docs/model/examples/order-portal/order-portal.sysml as
tests/golden/trace/order-portal.*. The project of these reports has the
full output of `dsml generate`: the FastAPI application, the React
application, the infrastructure and the workflows. Thus the reports give
the generated files of the real trace manifest. The test folder of the
project has the Vitest tests of tests/react/, as in the CI job "React
golden project". The verifications V-003 and V-004 name these files.
Thus the orphans report has no test file without a verification.

The Git repository of the impact and suspect reports of the order portal
does not commit the output of `dsml generate`: its `.gitignore` names the
output folders. Thus a change to a generator does not change the commit
hashes in these reports. The script runs `dsml generate` after the second
commit, so the impact report reads the trace manifest of the changed model.

The phase 3 exit story (#189) added the golden reports of the order web
model docs/model/examples/order-web/order-web.sysml as
tests/golden/trace/order-web.*, in the same way. The project has the full
output: the Next.js application, the infrastructure and the workflows. The
test folder of the application has the Vitest tests of tests/nextjs/, as in
the CI job "Next.js golden project".
"""

import contextlib
import dataclasses
import functools
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Generator
from pathlib import Path

from dsml.cli import main as dsml
from dsml.generate.trace import TRACE_PATH, SymbolKind, TraceEntry, trace_bytes

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "trace"
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
PORTAL_MODEL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
WEB_MODEL = ROOT / "docs" / "model" / "examples" / "order-web" / "order-web.sysml"
EXAMPLE = "order-service"
PORTAL = "order-portal"
WEB = "order-web"
REPORTS = ("coverage", "orphans")
CHANGE_REPORTS = ("impact", "suspect")
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

[trace]
tests = ["apps/order-portal/tests"]
"""
"""The configuration file of the order portal project: all output of the model."""

WEB_CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.orderWeb]
output = "apps/order-web"

[infrastructure]
output = "infra"

[pipelines]
output = ".github/workflows"

[trace]
tests = ["apps/order-web/tests"]
"""
"""The configuration file of the order web project: all output of the model."""


@dataclasses.dataclass(frozen=True)
class FullModel:
    """A reference model with the full output of `dsml generate` in its report projects."""

    model: Path
    configuration: str
    tests: Path
    """The folder of the Vitest tests in the repository."""
    test_folders: tuple[str, ...]
    """The folders of `tests` that the project has in the test folder of the application."""
    test_folder: str
    """The test folder of the application in the project."""
    ignore: str
    """The `.gitignore` of the Git repository of the impact and suspect reports.

    The repository keeps only the configuration and the model.
    """
    changes: tuple[tuple[str, str], ...]
    """The changes of the second commit of the Git repository."""


FULL_MODELS = {
    PORTAL: FullModel(
        PORTAL_MODEL,
        PORTAL_CONFIGURATION,
        ROOT / "tests" / "react",
        ("app", "features", "field-rules", "shared", "widgets"),
        "apps/order-portal/tests",
        "/.dsml/\n/.github/\n/apps/\n/infra/\n/services/\n",
        (
            (
                "The portal must have a form that places an order.",
                "The portal must have a form that places an order with a note.",
            ),
            ("maxLength = 500;", "maxLength = 1000;"),
        ),
    ),
    WEB: FullModel(
        WEB_MODEL,
        WEB_CONFIGURATION,
        ROOT / "tests" / "nextjs",
        ("auth", "features", "pages", "routes", "widgets"),
        "apps/order-web/tests",
        "/.dsml/\n/.github/\n/apps/\n/infra/\n",
        (
            (
                "The web application must have a form that cancels an order.",
                "The web application must have a form that cancels an open order.",
            ),
            ("maxLength = 500;", "maxLength = 1000;"),
        ),
    ),
}
"""The order portal (story #177) and the order web (story #189).

The changes of the second commit change the requirement R-004 and the field
`Order::note` of each model.
"""


def generate(folder: Path) -> int:
    """Run `dsml generate` in the folder, and give the exit code."""
    with contextlib.chdir(folder):
        return dsml(["generate", "--output", os.devnull])


def write_full_files(folder: Path, name: str, tests: bool = True) -> None:
    """Write the configuration, the model and, if `tests` is true, the Vitest tests."""
    reference = FULL_MODELS[name]
    (folder / "dsml.toml").write_text(reference.configuration, encoding="utf-8", newline="\n")
    (folder / "model").mkdir()
    shutil.copyfile(reference.model, folder / "model" / reference.model.name)
    if not tests:
        return
    for test_folder in reference.test_folders:
        shutil.copytree(reference.tests / test_folder, folder / reference.test_folder / test_folder)


def write_full_project(folder: Path, name: str) -> None:
    """Write the project of a reference model and run `dsml generate` in it."""
    write_full_files(folder, name)
    if generate(folder) != 0:
        raise RuntimeError(f"dsml generate did not write the output of the model {name}.")


def write_full_change_project(folder: Path, name: str) -> None:
    """Write the Git repository of the impact and suspect reports of a reference model.

    The first commit has the configuration, the model and `.gitignore`, and
    the tag `v1.0.0`. The second commit changes the model. Then the function
    runs `dsml generate`. The output is not in a commit. These reports do not
    read the test files, thus the repository has no tests.
    """
    reference = FULL_MODELS[name]
    git(folder, "init", "--quiet", "--initial-branch=main")
    write_full_files(folder, name, tests=False)
    (folder / ".gitignore").write_text(reference.ignore, encoding="utf-8", newline="\n")
    commit(folder, f"Add the {name.replace('-', ' ')} project.")
    git(folder, "tag", BASELINE_TAG)
    change_model(folder, reference.model, reference.changes)
    commit(folder, "Change R-004 and Order::note.")
    if generate(folder) != 0:
        raise RuntimeError(f"dsml generate did not write the output of the model {name}.")


BASELINE_TAG = "v1.0.0"
"""The release tag of the first commit of the Git repository of the impact and suspect reports."""

MODEL_CHANGES = (
    (
        "The API must return the status of an order.",
        "The API must return the status and the total of an order.",
    ),
    (
        "    #Entity part def Order {\n",
        "    #Entity part def Order {\n        doc /* An order of a customer. */\n",
    ),
    ("maxLength = 500;", "maxLength = 1000;"),
)
"""The changes of the second commit: the requirement R-001 and the entity `Order`."""

TRACE_ENTRIES = (
    TraceEntry("OrderService::Order", "app/models_gen.py", SymbolKind.CLASS, "Order", 3, 9),
    TraceEntry(
        "OrderService::apiServiceAws",
        "infra/envs/prod/main.gen.tf",
        SymbolKind.RESOURCE,
        "aws_ecs_service.api_service",
        1,
        5,
    ),
    TraceEntry("OrderService::orderApi", "app/main_gen.py", SymbolKind.FUNCTION, "main", 1, 4),
    TraceEntry(
        "OrderService::orderDbAws",
        "infra/envs/prod/main.gen.tf",
        SymbolKind.RESOURCE,
        "aws_db_instance.order_db",
        7,
        12,
    ),
)
"""The trace manifest of the second commit. No generator wrote these entries."""

GIT_ENVIRONMENT = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}
"""The Git settings that make the same commit hashes at each run."""


def git(folder: Path, *args: str) -> str:
    """Run a Git command in the folder with fixed settings, and give its output."""
    result = subprocess.run(
        ["git", "-C", str(folder), *args],
        capture_output=True,
        check=True,
        env={**os.environ, **GIT_ENVIRONMENT},
        text=True,
    )
    return result.stdout.strip()


def commit(folder: Path, message: str) -> str:
    """Commit all files of the work tree, and give the commit hash."""
    git(folder, "add", "--all")
    git(folder, "commit", "--quiet", "--allow-empty", "--no-gpg-sign", "-m", message)
    return git(folder, "rev-parse", "HEAD")


def change_model(
    folder: Path, model: Path = EXAMPLE_MODEL, changes: tuple[tuple[str, str], ...] = MODEL_CHANGES
) -> None:
    """Make the changes in the copy of a model. The default is the change of the example model."""
    path = folder / "model" / model.name
    text = path.read_text(encoding="utf-8")
    for old, new in changes:
        if old not in text:
            raise ValueError(f"The model {model.name} does not contain {old!r}.")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_change_project(folder: Path) -> None:
    """Write the Git repository of the impact and suspect reports.

    The first commit has the example project and the tag `v1.0.0`. The
    second commit changes the model and adds the trace manifest.
    """
    git(folder, "init", "--quiet", "--initial-branch=main")
    write_project(folder)
    commit(folder, "Add the example project.")
    git(folder, "tag", BASELINE_TAG)
    change_model(folder)
    manifest = folder / TRACE_PATH
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_bytes(trace_bytes(TRACE_ENTRIES))
    commit(folder, "Change R-001 and Order.")


def golden_file(report: str, report_format: str, name: str = EXAMPLE) -> Path:
    """Give the golden file of one report in one format for a reference model."""
    return GOLDEN / f"{name}.{report}.{report_format}"


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
        projects: list[tuple[str, Callable[[Path], None], Callable[[Path], None]]] = [
            (EXAMPLE, write_project, write_change_project)
        ]
        for full in FULL_MODELS:
            projects.append(
                (
                    full,
                    functools.partial(write_full_project, name=full),
                    functools.partial(write_full_change_project, name=full),
                )
            )
        for name, write, write_change in projects:
            project = Path(temporary) / name / "project"
            project.mkdir(parents=True)
            write(project)
            code = _write_reports(project, REPORTS, name)
            if code != 0:
                return code
            repository = Path(temporary) / name / "repository"
            repository.mkdir()
            write_change(repository)
            code = _write_reports(repository, CHANGE_REPORTS, name)
            if code != 0:
                return code
    return 0


def _write_reports(project: Path, reports: tuple[str, ...], name: str) -> int:
    with contextlib.chdir(project):
        for report in reports:
            for report_format in FORMATS:
                output = golden_file(report, report_format, name)
                code = dsml(["trace", report, "--format", report_format, "--output", str(output)])
                if code != 0:
                    print(f"dsml trace gave exit code {code}.", file=sys.stderr)
                    return code
                print(f"Wrote {output.relative_to(ROOT).as_posix()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
