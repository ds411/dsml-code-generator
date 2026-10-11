"""Tests of the SYN findings and of the version check (story #29).

Each SYN rule has one model that it accepts and one model that it rejects
(PRD-VAL-008). The models are in `tests/models/rules/<rule>/`.
"""

import argparse
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from dsml import cli, versions
from dsml.adapter.engine import Diagnostic, Engine, EngineVersionError
from dsml.adapter.findings import syn_finding, syn_findings
from dsml.errors import ToolchainError
from dsml.ir.model import Finding, Location
from dsml.rules import RULES, SYN_001, SYN_002

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The test changes the connect function of the client through the adapter
# module, because only the adapter can import opensysml (PRD-CORE-020).
CONNECT = "dsml.adapter.engine.opensysml.connect"
RULE_MODELS = Path(__file__).resolve().parent / "models" / "rules"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    with Engine() as started:
        yield started


def _findings(engine: Engine, rule: str, name: str) -> tuple[Finding, ...]:
    path = RULE_MODELS / rule / name
    return syn_findings(engine.parse_files([path], PROJECT_ROOT).diagnostics)


def _diagnostic(severity: str, line: int = 4, column: int = 39) -> Diagnostic:
    return Diagnostic(
        file="models/a.sysml",
        line=line,
        column=column,
        end_line=line,
        end_column=column + 1,
        severity=severity,
        code="syntax",
        message="missing ';' at end of declaration",
    )


# trace: PRD-VAL-008
@pytest.mark.parametrize("rule", sorted(RULES))
def test_rule_accepts_its_accept_model(engine: Engine, rule: str) -> None:
    assert _findings(engine, rule, "accept.sysml") == ()


# trace: PRD-CORE-007, PRD-CORE-021, PRD-VAL-008
@pytest.mark.parametrize(
    ("name", "line", "column", "message"),
    [
        ("reject.sysml", 5, 39, "missing ';' at end of declaration (OpenSysML code: syntax)"),
        (
            "reject-unresolved.sysml",
            4,
            20,
            "unresolved reference: Unknown (OpenSysML code: unresolved)",
        ),
    ],
)
def test_syn_001_rejects_its_reject_models(
    engine: Engine, name: str, line: int, column: int, message: str
) -> None:
    file = f"tests/models/rules/SYN-001/{name}"
    assert _findings(engine, "SYN-001", name) == (
        Finding("SYN-001", "error", message, Location(file, line, column)),
    )


# trace: PRD-CORE-007, PRD-CORE-021, PRD-VAL-008
def test_syn_002_rejects_a_warning(engine: Engine) -> None:
    findings = _findings(engine, "SYN-002", "reject.sysml")
    file = "tests/models/rules/SYN-002/reject.sysml"
    assert findings
    assert {(item.rule, item.severity) for item in findings} == {("SYN-002", "warning")}
    assert {item.location.file for item in findings if item.location} == {file}
    assert all("(OpenSysML code: name-conflict)" in item.message for item in findings)


# trace: PRD-CORE-033
def test_finding_paths_are_relative_to_the_root(engine: Engine) -> None:
    for rule in RULES:
        for finding in _findings(engine, rule, "reject.sysml"):
            assert finding.location is not None
            assert finding.location.file.startswith("tests/models/rules/")


@pytest.mark.parametrize(
    ("severity", "rule"), [("error", "SYN-001"), ("warning", "SYN-002"), ("info", "SYN-002")]
)
def test_severity_selects_the_rule(severity: str, rule: str) -> None:
    finding = syn_finding(_diagnostic(severity))
    assert finding.rule == rule
    assert finding.severity == RULES[rule].severity
    assert finding.location == Location("models/a.sysml", 4, 39)


def test_location_starts_at_line_1_and_column_1() -> None:
    finding = syn_finding(_diagnostic("error", line=0, column=0))
    assert finding.location == Location("models/a.sysml", 1, 1)


def test_absolute_path_gives_an_error() -> None:
    diagnostic = Diagnostic("/home/a.sysml", 1, 1, 1, 2, "error", "syntax", "text")
    with pytest.raises(ValueError, match="relative POSIX path"):
        syn_finding(diagnostic)


# trace: PRD-VAL-007
def test_findings_are_sorted() -> None:
    findings = syn_findings(
        [_diagnostic("warning", 9, 1), _diagnostic("error", 9, 1), _diagnostic("error", 2, 5)]
    )
    assert [(item.location.line, item.rule) for item in findings if item.location] == [
        (2, "SYN-001"),
        (9, "SYN-001"),
        (9, "SYN-002"),
    ]


# trace: PRD-VAL-001, PRD-VAL-002, PRD-VAL-003
def test_syn_rules_have_the_metadata_of_the_catalog() -> None:
    assert (SYN_001.id, SYN_001.category, SYN_001.severity) == ("SYN-001", "SYN", "error")
    assert (SYN_002.id, SYN_002.category, SYN_002.severity) == ("SYN-002", "SYN", "warning")
    for rule in RULES.values():
        assert rule.message
        assert rule.fix_hint


class _FakeConnection:
    """A connection that gives a different `sysml-grpc` version."""

    def __init__(self, version: str) -> None:
        self.version = version
        self.closed = False

    def server_info(self) -> SimpleNamespace:
        return SimpleNamespace(version=self.version)

    def close(self) -> None:
        self.closed = True


def _connect(connection: _FakeConnection) -> Callable[..., _FakeConnection]:
    def connect(**_: object) -> _FakeConnection:
        return connection

    return connect


def _pin(version: str) -> Callable[[str], str]:
    def pinned_version(_: str) -> str:
        return version

    return pinned_version


# trace: PRD-CORE-019
def test_different_service_version_stops_the_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _FakeConnection("v0.9.1")
    monkeypatch.setattr(CONNECT, _connect(connection))
    with pytest.raises(EngineVersionError, match=r"sysml-grpc has version v0\.9\.1"):
        Engine()
    assert connection.closed


def _run_engine(args: argparse.Namespace) -> cli.Outcome:
    with Engine():
        return cli.Outcome.SUCCESS


# trace: PRD-CORE-002, PRD-CORE-019
def test_different_service_version_gives_exit_code_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(CONNECT, _connect(_FakeConnection("v0.9.1")))
    monkeypatch.setitem(cli.HANDLERS, "version", _run_engine)
    assert cli.main(["version"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "dsml: error: sysml-grpc has version v0.9.1. The toolchain must use version v0.9.2.\n"
    )


# trace: PRD-CORE-002, PRD-CORE-019
def test_different_client_version_gives_exit_code_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(versions, "pinned_version", _pin("0.9.1"))
    monkeypatch.setitem(cli.HANDLERS, "version", _run_engine)
    assert cli.main(["version"]) == 2
    assert "must use version 0.9.1" in capsys.readouterr().err


def test_engine_errors_are_toolchain_errors() -> None:
    assert issubclass(EngineVersionError, ToolchainError)
