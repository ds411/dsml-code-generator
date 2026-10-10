"""Tests of the OpenSysML 0.9.2 engine through the IR adapter (story #12).

These tests start a private `sysml-grpc` child process. If the binary is not
in the cache, the `opensysml` client downloads it one time.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from dsml import versions
from dsml.adapter.engine import (
    ConstraintResult,
    Diagnostic,
    Engine,
    EngineVersionError,
    ParsedModel,
    check_client_version,
    check_service_version,
)

MODELS = Path(__file__).resolve().parent / "models" / "opensysml"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    with Engine() as started:
        yield started


@pytest.fixture(scope="module")
def probe(engine: Engine) -> ParsedModel:
    return engine.parse_files([MODELS / "probe.sysml"], MODELS)


def _parse(engine: Engine, name: str) -> ParsedModel:
    return engine.parse_files([MODELS / name], MODELS)


# trace: PRD-CORE-017, PRD-CORE-018, PRD-CORE-019
def test_engine_has_the_pinned_version(engine: Engine) -> None:
    assert engine.service_version == "v0.9.2"


# trace: PRD-CORE-019
def test_check_versions_accept_the_pinned_version() -> None:
    check_client_version("0.9.2", "0.9.2")
    check_service_version("v0.9.2", "0.9.2")


# trace: PRD-CORE-019
def test_check_client_version_rejects_another_version() -> None:
    with pytest.raises(EngineVersionError, match=r"opensysml Python package has version 0\.9\.1"):
        check_client_version("0.9.1", "0.9.2")


# trace: PRD-CORE-019
@pytest.mark.parametrize(
    ("service", "text"),
    [("v0.9.3", "sysml-grpc has version v0.9.3"), ("", "sysml-grpc has version unknown")],
)
def test_check_service_version_rejects_another_version(service: str, text: str) -> None:
    with pytest.raises(EngineVersionError, match=text):
        check_service_version(service, "0.9.2")


# trace: PRD-CORE-019
def test_engine_stops_before_the_start_if_the_pin_is_different(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def pinned_version(name: str) -> str:
        return "0.9.1"

    monkeypatch.setattr(versions, "pinned_version", pinned_version)
    with pytest.raises(EngineVersionError, match=r"must use version 0\.9\.1"):
        Engine()


# trace: PRD-DSML-003, PRD-DSML-004
def test_probe_model_parses_and_resolves(probe: ParsedModel) -> None:
    assert probe.diagnostics == ()
    assert probe.ok


# trace: PRD-DSML-003
def test_keyword_gives_the_base_type(probe: ParsedModel) -> None:
    assert probe.has_metadata("auditDb", "RelationalDatabase", "Probe")
    assert probe.is_type("auditDb", "Database", "Probe")
    assert not probe.has_metadata("plain", "RelationalDatabase", "Probe")
    assert not probe.is_type("plain", "Database", "Probe")


# trace: PRD-DSML-003
def test_unknown_keyword_gives_an_error(engine: Engine) -> None:
    model = _parse(engine, "unknown-keyword.sysml")
    assert model.diagnostics == (
        Diagnostic(
            file="unknown-keyword.sysml",
            line=3,
            column=6,
            end_line=3,
            end_column=13,
            severity="error",
            code="unresolved",
            message="unresolved reference: Unknown",
        ),
    )


# trace: PRD-CORE-021
def test_syntax_error_gives_file_line_and_column(engine: Engine) -> None:
    model = _parse(engine, "syntax-error.sysml")
    assert not model.ok
    assert [str(item) for item in model.diagnostics] == [
        "syntax-error.sysml:4:39: error: missing ';' at end of declaration"
    ]
    assert model.diagnostics[0].code == "syntax"


def test_feature_chain_through_keyword_type_does_not_resolve(engine: Engine) -> None:
    """A known limit of OpenSysML 0.9.2. See docs/notes/opensysml-0.9.2.md.

    If a new OpenSysML version removes the limit, this test fails. Then
    update the notes and the DSML library.
    """
    model = _parse(engine, "feature-chain.sysml")
    assert [(item.line, item.code, item.message) for item in model.diagnostics] == [
        (14, "unresolved", "unresolved member: cpu")
    ]


def test_fixed_value_cannot_change(engine: Engine) -> None:
    model = _parse(engine, "value-override.sysml")
    assert [(item.line, item.code) for item in model.diagnostics] == [
        (10, "feature-value-overriding")
    ]


def test_diagnostics_have_no_absolute_path(engine: Engine) -> None:
    files = sorted(MODELS.glob("*.sysml"))
    model = engine.parse_files(files, MODELS)
    assert model.diagnostics
    assert {item.file for item in model.diagnostics} <= {path.name for path in files}


# trace: PRD-CORE-054
@pytest.mark.parametrize(
    ("constraint", "value"),
    [
        ("Probe::prodMultiAz", "true"),
        ("Probe::devMultiAz", "false"),
        ("Probe::prodStorage", "unknown"),
        ("Probe::enoughStorage::storageSet", "unknown"),
    ],
)
def test_constraint_result(probe: ParsedModel, constraint: str, value: str) -> None:
    assert probe.evaluate_constraint(constraint).value == value


# trace: PRD-CORE-054
def test_unknown_result_names_the_feature_with_no_value(probe: ParsedModel) -> None:
    result = probe.evaluate_constraint("Probe::prodStorage")
    assert result.value == "unknown"
    assert "orderDb.storage has no value" in result.detail


# trace: PRD-CORE-054
@pytest.mark.parametrize(
    ("requirement", "result"),
    [
        ("Probe::orderDataSafeDev", ConstraintResult("false")),
        ("Probe::orderDataSafeProd", ConstraintResult("true")),
    ],
)
def test_requirement_result_for_each_environment(
    probe: ParsedModel, requirement: str, result: ConstraintResult
) -> None:
    assert probe.evaluate_requirement(requirement) == result
