"""Tests of `dsml trace` with the coverage and orphans reports (story #72)."""

import dataclasses
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from dsml.cli import main
from dsml.ir.model import (
    Attribute,
    Element,
    ElementKind,
    Ir,
    Link,
    LinkType,
    ListValue,
    Location,
    StringValue,
)
from dsml.trace.comments import TraceComment
from dsml.trace.commit import NO_COMMIT, NOT_IN_REPOSITORY, model_commit
from dsml.trace.report import Report, csv_report, json_report
from dsml.trace.reports import (
    ELEMENT_WITHOUT_REQUIREMENT,
    MISSING,
    NEED_WITHOUT_REQUIREMENT,
    REQUIREMENT_WITHOUT_NEED,
    SATISFIED,
    TEST_FILE_WITHOUT_VERIFICATION,
    UNKNOWN_TRACE_ID,
    VERIFIED,
    TraceData,
    coverage_report,
    is_test_file,
    orphans_report,
    requirement_status,
)

ROOT = Path(__file__).resolve().parent.parent


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "write_golden_reports", ROOT / "scripts/write_golden_reports.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


write_golden_reports: Any = _load_script()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """The example project in a folder that is not in a Git repository."""
    folder = tmp_path / "project"
    folder.mkdir()
    write_golden_reports.write_project(folder)
    monkeypatch.chdir(folder)
    with write_golden_reports.outside_git():
        yield folder


def _location(line: int) -> Location:
    return Location(file="model.sysml", line=line, column=1)


def _element(identity: str, kind: ElementKind, line: int, short: bool = False) -> Element:
    name = identity.rsplit("::", 1)[-1]
    return Element(
        identity=identity,
        kind=kind,
        name=name,
        qualified_name=f"M::{name}" if short else identity,
        location=_location(line),
        short_name=identity if short else None,
    )


def _link(link_type: LinkType, source: str, target: str) -> Link:
    return Link(type=link_type, source=source, target=target, location=_location(1))


def _ir() -> Ir:
    """A model with one requirement of each status and one item of each orphan category.

    - R-001 is satisfied by `M::api` and verified by V-001: `verified`.
    - R-002 is satisfied by `M::db` and has no verification: `satisfied`.
    - R-003 has no satisfying element: `missing`. It frames no need.
    - N-002 has no requirement. `M::network` satisfies no requirement.
    """
    return Ir(
        files=("model.sysml",),
        elements=(
            _element("M::api", "Application", 20),
            _element("M::apiService", "ContainerService", 21),
            _element("M::db", "RelationalDatabase", 22),
            _element("M::network", "Network", 23),
            _element("M::Order", "Entity", 24),
            _element("M::Order::id", "Field", 25),
            _element("N-001", "Need", 2, short=True),
            _element("N-002", "Need", 3, short=True),
            _element("R-001", "Requirement", 10, short=True),
            _element("R-002", "Requirement", 11, short=True),
            _element("R-003", "Requirement", 12, short=True),
            _element("V-001", "Verification", 30, short=True),
        ),
        links=(
            _link("allocate", "M::api", "M::apiService"),
            _link("frame", "R-001", "N-001"),
            _link("frame", "R-002", "N-001"),
            _link("satisfy", "M::api", "R-001"),
            _link("satisfy", "M::db", "R-002"),
            _link("satisfy", "M::Order", "R-001"),
            _link("verify", "V-001", "R-001"),
        ),
    )


def _rows(report: Report) -> dict[str, tuple[object, ...]]:
    return {str(row[0]): row for row in report.rows}


# trace: PRD-CORE-030, PRD-TRACE-013, PRD-TRACE-017
@pytest.mark.parametrize("report_format", write_golden_reports.FORMATS)
@pytest.mark.parametrize("report", write_golden_reports.REPORTS)
def test_report_of_example_model_agrees_with_golden_file(
    report: str, report_format: str, project: Path
) -> None:
    output = project / "report.out"
    assert main(["trace", report, "--format", report_format, "--output", str(output)]) == 0
    golden: Path = write_golden_reports.golden_file(report, report_format)
    assert output.read_bytes() == golden.read_bytes(), (
        f"The {report} report is not the same as {golden.relative_to(ROOT)}. "
        "If the change is correct, run scripts/write_golden_reports.py."
    )


# trace: PRD-CORE-006
def test_report_goes_to_standard_output(
    project: Path, capsysbinary: pytest.CaptureFixture[bytes]
) -> None:
    assert main(["trace", "coverage", "--format", "json"]) == 0
    golden: Path = write_golden_reports.golden_file("coverage", "json")
    assert capsysbinary.readouterr().out == golden.read_bytes()


# trace: PRD-TRACE-014
def test_requirement_status_has_three_values() -> None:
    assert requirement_status((), ()) == MISSING
    assert requirement_status((), ("V-001",)) == MISSING
    assert requirement_status(("M::api",), ()) == SATISFIED
    assert requirement_status(("M::api",), ("V-001",)) == VERIFIED


# trace: PRD-TRACE-013, PRD-TRACE-014
def test_coverage_report_gives_each_requirement_one_status() -> None:
    comments = (
        TraceComment("app/handler.py", 12, ("R-001",), "handle", 13),
        TraceComment("app/handler.py", 3, ("M::R-001", "R-002"), None, None),
        TraceComment("tests/test_api.py", 1, ("R-001",), None, None),
    )
    generated = (
        ("M::api", "app/api_gen.py"),
        ("M::apiService", "infra/service.gen.tf"),
        ("R-001", "app/routes_gen.py"),
        ("M::db", "infra/db.gen.tf"),
        ("M::unknown", "app/old_gen.py"),
    )
    report = coverage_report(TraceData(_ir(), generated, comments, (), "abc"))
    assert report.model_commit == "abc"
    assert _rows(report) == {
        "R-001": (
            "R-001",
            ("N-001",),
            ("M::Order", "M::api"),
            ("app/api_gen.py", "app/routes_gen.py", "infra/service.gen.tf"),
            ("app/handler.py:3", "app/handler.py:12", "tests/test_api.py:1"),
            ("V-001",),
            VERIFIED,
        ),
        "R-002": (
            "R-002",
            ("N-001",),
            ("M::db",),
            ("infra/db.gen.tf",),
            ("app/handler.py:3",),
            (),
            SATISFIED,
        ),
        "R-003": ("R-003", (), (), (), (), (), MISSING),
    }


# trace: PRD-TRACE-012, PRD-TRACE-013
def test_orphans_report_lists_each_category() -> None:
    comments = (
        TraceComment("app/handler.py", 4, ("R-001", "R-404", "M::'api'"), "handle", 5),
        TraceComment("tests/test_api.py", 1, ("V-001", "Unknown::name"), None, None),
    )
    files = (
        "app/handler.py",
        "tests/conftest.py",
        "tests/test_api.py",
        "tests/test_other.py",
        "web/app.test.ts",
    )
    ir = _ir()
    named = Attribute("testFiles", ListValue((StringValue("tests/test_api.py"),)))
    ir = Ir(
        files=ir.files,
        elements=(*ir.elements[:-1], dataclasses.replace(ir.elements[-1], attributes=(named,))),
        links=ir.links,
    )
    report = orphans_report(TraceData(ir, (), comments, files, "abc"))
    assert report.rows == (
        (ELEMENT_WITHOUT_REQUIREMENT, "M::network", "model.sysml:23"),
        (NEED_WITHOUT_REQUIREMENT, "N-002", "model.sysml:3"),
        (REQUIREMENT_WITHOUT_NEED, "R-003", "model.sysml:12"),
        (TEST_FILE_WITHOUT_VERIFICATION, "tests/test_other.py", "tests/test_other.py"),
        (TEST_FILE_WITHOUT_VERIFICATION, "web/app.test.ts", "web/app.test.ts"),
        (UNKNOWN_TRACE_ID, "R-404", "app/handler.py:4"),
        (UNKNOWN_TRACE_ID, "Unknown::name", "tests/test_api.py:1"),
    )


# trace: PRD-TRACE-012
def test_trace_comment_with_unknown_id_is_in_orphans_report(project: Path) -> None:
    output = project / "orphans.json"
    assert main(["trace", "orphans", "--format", "json", "--output", str(output)]) == 0
    rows = json.loads(output.read_bytes())["rows"]
    assert {
        "category": UNKNOWN_TRACE_ID,
        "item": "R-404",
        "location": "app/features/order/cancel_order/handler.py:1",
    } in rows
    known = [row for row in rows if row["item"] in ("R-001", "V-001", "OrderService::orderApi")]
    assert known == []


def test_test_file_names() -> None:
    assert is_test_file("tests/test_api.py")
    assert is_test_file("tests/api_test.py")
    assert is_test_file("web/src/app.test.tsx")
    assert is_test_file("web/src/app.spec.ts")
    assert not is_test_file("tests/conftest.py")
    assert not is_test_file("tests/helpers.py")
    assert not is_test_file("infra/test.tf")


# trace: PRD-TRACE-018
def test_report_gives_model_commit_and_no_date_or_time(project: Path) -> None:
    for report_format in write_golden_reports.FORMATS:
        for report in write_golden_reports.REPORTS:
            text = write_golden_reports.golden_file(report, report_format).read_text("utf-8")
            assert NOT_IN_REPOSITORY in text
            assert "date" not in text.lower()
            assert "time" not in text.lower()
    data = json.loads(write_golden_reports.golden_file("coverage", "json").read_bytes())
    assert sorted(data) == [
        "baselineCommit",
        "columns",
        "modelCommit",
        "report",
        "reportVersion",
        "rows",
    ]
    assert data["modelCommit"] == NOT_IN_REPOSITORY
    assert data["baselineCommit"] is None


def _git(folder: Path, *args: str) -> str:
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=folder,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


# trace: PRD-TRACE-018
def test_report_gives_commit_of_git_repository(project: Path) -> None:
    _git(project, "init", "--quiet")
    assert model_commit(project) == NO_COMMIT
    _git(project, "add", ".")
    _git(project, "commit", "--quiet", "--message", "Add the model")
    head = _git(project, "rev-parse", "HEAD")
    assert len(head) == 40
    assert model_commit(project) == head
    output = project / "report.json"
    assert main(["trace", "coverage", "--format", "json", "--output", str(output)]) == 0
    assert json.loads(output.read_bytes())["modelCommit"] == head
    assert main(["trace", "coverage", "--format", "csv", "--output", str(output)]) == 0
    assert output.read_text("utf-8").splitlines()[1] == f"# model commit: {head}"


def test_folder_outside_git_repository_has_no_commit(project: Path) -> None:
    assert model_commit(project) == NOT_IN_REPOSITORY


# trace: PRD-TRACE-017
def test_html_format_is_not_available(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["trace", "coverage"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "dsml: error: The format html is not available in this version. "
        "Use --format json or --format csv.\n"
    )


def test_baseline_option_is_not_available(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["trace", "orphans", "--format", "json", "--baseline", "v1.0.0"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "dsml: error: The option --baseline is not available in this version.\n"


def test_trace_comment_problem_is_a_warning(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / "tests" / "test_bad.py").write_text("# trace: R-001, !\nx = 1\n", "utf-8")
    assert main(["trace", "coverage", "--format", "csv"]) == 0
    assert capsys.readouterr().err == (
        "dsml: warning: tests/test_bad.py:1: The trace comment has an item that is not "
        'a short name or a qualified name: "!".\n'
    )


# trace: PRD-TRACE-013, PRD-CORE-028
def test_report_model_sorts_rows_and_writes_both_formats() -> None:
    report = Report(
        "example",
        ("id", "items"),
        (("b", ("y", "x")), ('a, "q"', ()), ("b", ("y", "x"))),
        "abc",
        "def",
    )
    assert report.rows == (('a, "q"', ()), ("b", ("y", "x")))
    assert csv_report(report) == (
        "# report: example\n"
        "# model commit: abc\n"
        "# baseline commit: def\n"
        "id,items\n"
        '"a, ""q""",\n'
        "b,y; x\n"
    )
    assert json.loads(json_report(report)) == {
        "baselineCommit": "def",
        "columns": ["id", "items"],
        "modelCommit": "abc",
        "report": "example",
        "reportVersion": 1,
        "rows": [{"id": 'a, "q"', "items": []}, {"id": "b", "items": ["y", "x"]}],
    }


def test_report_model_rejects_row_with_wrong_cell_count() -> None:
    with pytest.raises(ValueError, match="has 1 cells"):
        Report("example", ("id", "items"), (("a",),), "abc")
