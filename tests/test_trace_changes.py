"""Tests of `dsml trace` with the impact and suspect reports (story #73).

Each test with Git makes a temporary Git repository. The tests use only the
local `git` command and no network (PRD-TOP-004).
"""

import contextlib
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_trace_reports import write_golden_reports

from dsml.cli import main
from dsml.ir.model import Element, ElementKind, Ir, Link, LinkType, Location
from dsml.trace.changes import (
    ADDED,
    CHANGED,
    REMOVED,
    ChangeData,
    changed_elements,
    impact_report,
    suspect_report,
)

script: Any = write_golden_reports
MODEL = Path("model") / script.EXAMPLE_MODEL.name


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A Git repository with the example project in a commit with the tag `v1.0.0`."""
    folder = tmp_path / "repository"
    folder.mkdir()
    monkeypatch.chdir(folder)
    with script.outside_git():
        script.git(folder, "init", "--quiet", "--initial-branch=main")
        script.write_project(folder)
        script.commit(folder, "Add the example project.")
        script.git(folder, "tag", "v1.0.0")
        yield folder


def _replace(folder: Path, old: str, new: str) -> None:
    path = folder / MODEL
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def _report(*args: str) -> dict[str, Any]:
    output = Path("report.json")
    assert main(["trace", *args, "--format", "json", "--output", str(output)]) == 0
    data: dict[str, Any] = json.loads(output.read_bytes())
    output.unlink()
    return data


def _rows(data: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {row[key]: row for row in data["rows"]}


# trace: PRD-CORE-030, PRD-TRACE-013, PRD-TRACE-017
@pytest.mark.parametrize("report_format", script.FORMATS)
@pytest.mark.parametrize("report", script.CHANGE_REPORTS)
def test_report_of_changed_example_model_agrees_with_golden_file(
    report: str, report_format: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "repository"
    folder.mkdir()
    monkeypatch.chdir(folder)
    output = tmp_path / f"report.{report_format}"
    with script.outside_git():
        script.write_change_project(folder)
        assert main(["trace", report, "--format", report_format, "--output", str(output)]) == 0
    golden: Path = script.golden_file(report, report_format)
    assert output.read_bytes() == golden.read_bytes(), (
        f"The {report} report is not the same as {golden.relative_to(script.ROOT)}. "
        "If the change is correct, run scripts/write_golden_reports.py."
    )


# trace: PRD-TRACE-015, PRD-TRACE-016, PRD-TRACE-018
def test_reports_of_changed_requirement(repository: Path) -> None:
    baseline = script.git(repository, "rev-parse", "HEAD")
    _replace(repository, "Get order status", "Get the order status")
    head = script.commit(repository, "Change R-001.")
    impact = _report("impact")
    assert impact["modelCommit"] == head
    assert impact["baselineCommit"] == baseline
    assert impact["rows"] == [
        {
            "change": "changed",
            "element": "R-001",
            "generatedFiles": [],
            "hclAddresses": [],
            "needs": ["N-001"],
            "requirements": ["R-001"],
            "verifications": ["V-001"],
        }
    ]
    suspect = _report("suspect")
    assert suspect["baselineCommit"] == baseline
    assert [(row["linkType"], row["source"], row["target"]) for row in suspect["rows"]] == [
        ("frame", "R-001", "N-001"),
        ("satisfy", "OrderService::orderApi", "R-001"),
        ("verify", "V-001", "R-001"),
    ]
    assert [row["changedEnds"] for row in suspect["rows"]] == [["source"], ["target"], ["target"]]


# trace: PRD-TRACE-015, PRD-TRACE-016
def test_reports_of_changed_entity(repository: Path) -> None:
    _replace(repository, "minValue = 0;", "minValue = 1;")
    script.commit(repository, "Change the entity Order.")
    impact = _rows(_report("impact"), "element")
    assert list(impact) == ["OrderService::Order::total"]
    row = impact["OrderService::Order::total"]
    assert (row["needs"], row["requirements"], row["verifications"]) == (
        ["N-001"],
        ["R-001"],
        ["V-001"],
    )
    suspect = _report("suspect")["rows"]
    assert [(row["linkType"], row["source"], row["target"]) for row in suspect] == [
        ("allocate", "OrderService::orderApi", "OrderService::apiService"),
        ("satisfy", "OrderService::orderApi", "R-001"),
    ]
    assert all(row["changedElements"] == ["OrderService::Order::total"] for row in suspect)


# trace: PRD-TRACE-015
def test_change_in_work_tree_counts_and_no_change_gives_no_row(repository: Path) -> None:
    assert _report("impact", "--baseline", "v1.0.0")["rows"] == []
    assert _report("suspect", "--baseline", "v1.0.0")["rows"] == []
    _replace(repository, "package OrderService {\n", "package OrderService {\n\n")
    assert _report("impact", "--baseline", "v1.0.0")["rows"] == []
    _replace(repository, "attribute note : String [0..1] { @FieldRules { maxLength = 500; } }", "")
    impact = _rows(_report("impact", "--baseline", "v1.0.0"), "element")
    assert list(impact) == ["OrderService::Order::note"]
    assert impact["OrderService::Order::note"]["change"] == "removed"


# trace: PRD-TRACE-016
def test_default_baseline_is_newest_release_tag_before_head(repository: Path) -> None:
    _replace(repository, "Get order status", "Get the order status")
    newest = script.commit(repository, "Change R-001.")
    script.git(repository, "tag", "v1.1.0")
    script.git(repository, "tag", "trace-baseline", "v1.0.0")
    _replace(repository, "Track orders", "Track the orders")
    head = script.commit(repository, "Change N-001.")
    script.git(repository, "tag", "v1.2.0")
    impact = _report("impact")
    assert (impact["modelCommit"], impact["baselineCommit"]) == (head, newest)
    assert list(_rows(impact, "element")) == ["N-001"]
    config = repository / "dsml.toml"
    config.write_text(
        config.read_text("utf-8") + 'baseline = "trace-baseline"\n', "utf-8", newline="\n"
    )
    assert list(_rows(_report("impact"), "element")) == ["N-001", "R-001"]
    impact = _report("impact", "--baseline", "v1.1.0")
    assert impact["baselineCommit"] == newest


# trace: PRD-TRACE-016
@pytest.mark.parametrize("report", ["impact", "suspect"])
def test_no_baseline_gives_exit_code_2(
    report: str, repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script.git(repository, "tag", "--delete", "v1.0.0")
    assert main(["trace", report, "--format", "json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f"dsml: error: There is no baseline for the {report} report. "
        "The repository has no release tag v* before HEAD. "
        "Give a baseline with --baseline <git-ref>, "
        "or set the key trace.baseline in the configuration file.\n"
    )


# trace: PRD-TRACE-016
def test_baseline_that_does_not_exist_gives_exit_code_2(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["trace", "suspect", "--format", "csv", "--baseline", "v9.9.9"]) == 2
    assert capsys.readouterr().err == (
        'dsml: error: The Git reference "v9.9.9" does not exist in the local repository.\n'
    )


@pytest.fixture(scope="module")
def portal_repository(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The Git repository of the changed order portal model, with the output of `dsml generate`."""
    folder = tmp_path_factory.mktemp("order-portal") / "repository"
    folder.mkdir()
    with script.outside_git():
        script.write_portal_change_project(folder)
    return folder


# trace: PRD-CORE-030, PRD-TRACE-013, PRD-TRACE-015, PRD-TRACE-016, PRD-TRACE-017
@pytest.mark.parametrize("report_format", script.FORMATS)
@pytest.mark.parametrize("report", script.CHANGE_REPORTS)
def test_report_of_changed_order_portal_agrees_with_golden_file(
    report: str, report_format: str, portal_repository: Path, tmp_path: Path
) -> None:
    output = tmp_path / f"report.{report_format}"
    with script.outside_git(), contextlib.chdir(portal_repository):
        assert main(["trace", report, "--format", report_format, "--output", str(output)]) == 0
    golden: Path = script.golden_file(report, report_format, script.PORTAL)
    assert output.read_bytes() == golden.read_bytes(), (
        f"The {report} report is not the same as {golden.relative_to(script.ROOT)}. "
        "If the change is correct, run scripts/write_golden_reports.py."
    )


# trace: PRD-TRACE-015, PRD-TRACE-016
def test_impact_report_of_order_portal_gives_the_react_files() -> None:
    data = json.loads(script.golden_file("impact", "json", script.PORTAL).read_bytes())
    rows = _rows(data, "element")
    assert sorted(rows) == ["OrderPortal::Order::note", "R-004"]
    assert rows["R-004"]["verifications"] == ["V-004"]
    note = rows["OrderPortal::Order::note"]["generatedFiles"]
    assert "apps/order-portal/src/entities/order/model/order.gen.ts" in note
    assert "services/order-api/app/shared/db/models/order_gen.py" in note


# trace: PRD-TRACE-018
@pytest.mark.parametrize("name", [script.EXAMPLE, script.PORTAL])
@pytest.mark.parametrize("report_format", script.FORMATS)
@pytest.mark.parametrize("report", script.CHANGE_REPORTS)
def test_golden_report_gives_both_commits_and_no_date_or_time(
    report: str, report_format: str, name: str
) -> None:
    text = script.golden_file(report, report_format, name).read_text("utf-8")
    commits = re.findall(r"\b[0-9a-f]{40}\b", text)
    assert len(set(commits)) == 2
    assert not re.search(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}", text)


def _location(line: int) -> Location:
    return Location(file="model.sysml", line=line, column=1)


def _element(
    identity: str, kind: ElementKind, line: int = 1, owner: str | None = None, doc: str = ""
) -> Element:
    return Element(
        identity=identity,
        kind=kind,
        name=identity.rsplit("::", 1)[-1],
        qualified_name=identity,
        location=_location(line),
        owner=owner,
        doc=doc or None,
    )


def _link(link_type: LinkType, source: str, target: str) -> Link:
    return Link(type=link_type, source=source, target=target, location=_location(1))


def _ir(*elements: Element, links: tuple[Link, ...] = ()) -> Ir:
    return Ir(files=("model.sysml",), elements=elements, links=links)


# trace: PRD-TRACE-015
def test_changed_elements_give_added_changed_and_removed() -> None:
    baseline = _ir(
        _element("A", "Entity", line=1),
        _element("B", "Entity", doc="old"),
        _element("C", "Entity"),
    )
    ir = _ir(
        _element("A", "Entity", line=9),
        _element("B", "Entity", doc="new"),
        _element("D", "Entity"),
    )
    assert changed_elements(ir, baseline) == {"B": CHANGED, "C": REMOVED, "D": ADDED}


# trace: PRD-TRACE-013, PRD-TRACE-015
def test_removed_element_uses_links_of_baseline() -> None:
    links = (
        _link("frame", "R-001", "N-001"),
        _link("satisfy", "api", "R-001"),
        _link("verify", "V-001", "R-001"),
    )
    common = (
        _element("N-001", "Need"),
        _element("R-001", "Requirement"),
        _element("V-001", "Verification"),
    )
    baseline = _ir(*common, _element("api", "Application"), links=links)
    data = ChangeData(
        ir=_ir(*common, links=(links[0], links[2])),
        baseline=baseline,
        model_commit="abc",
        baseline_commit="def",
        generated=(("api", "app/main_gen.py"),),
    )
    impact = impact_report(data)
    assert impact.rows == (
        ("api", REMOVED, ("N-001",), ("R-001",), ("V-001",), ("app/main_gen.py",), ()),
    )
    assert (impact.model_commit, impact.baseline_commit) == ("abc", "def")
    assert suspect_report(data).rows == ()
