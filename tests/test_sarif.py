"""Tests of the SARIF 2.1.0 output of `dsml validate` (story #58)."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from conftest import RULE_MODELS
from jsonschema.protocols import Validator

from dsml.cli import main
from dsml.config import Configuration
from dsml.ir.model import Finding, Ir, Location
from dsml.validate.rule import Hit, Rule, RuleCheck, implements
from dsml.validate.sarif import relative_uri, sarif_report

SCHEMA_FILE = Path(__file__).resolve().parent / "schemas" / "sarif-schema-2.1.0.json"
SYN_002_REJECT = RULE_MODELS / "SYN-002" / "reject.sysml"


def _rule(rule: Rule) -> RuleCheck:
    @implements(rule)
    def check(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
        return iter(())

    return check


RULES = {
    check.rule.id: check
    for check in (
        _rule(Rule("ERR-001", "error", "An error finding.", "Do C.")),
        _rule(Rule("INF-001", "info", "An info finding.", "Do A.")),
        _rule(Rule("WRN-001", "warning", "A warning finding.", "Do B.")),
    )
}


def _validator() -> Validator:
    return jsonschema.Draft4Validator(json.loads(SCHEMA_FILE.read_text(encoding="utf-8")))


def _check_schema(text: str) -> Any:
    """Make sure that the text agrees with the SARIF 2.1.0 schema, and give its data."""
    data = json.loads(text)
    _validator().validate(data)
    return data


# trace: PRD-CORE-033
@pytest.mark.parametrize(
    ("file", "base", "uri"),
    [
        ("model/a.sysml", "", "model/a.sysml"),
        ("model/a.sysml", ".", "model/a.sysml"),
        ("project/model/a b.sysml", "project", "model/a%20b.sysml"),
        ("model/a.sysml", "project", "../model/a.sysml"),
    ],
)
def test_uri_is_relative_to_the_folder_of_the_configuration(file: str, base: str, uri: str) -> None:
    assert relative_uri(file, base) == uri


# trace: PRD-VAL-006
def test_sarif_has_the_rule_metadata_the_levels_and_the_locations() -> None:
    findings = (
        Finding("WRN-001", "info", "A warning finding."),
        Finding("ERR-001", "error", "Text.", Location("project/model/a.sysml", 3, 5), "Order"),
        Finding("WRN-001", "warning", "A warning finding.", Location("project/b.sysml", 1, 2)),
    )
    text = sarif_report(findings, RULES, "1.2.3", "project")
    data = _check_schema(text)
    assert data["version"] == "2.1.0"
    [run] = data["runs"]
    driver = run["tool"]["driver"]
    assert driver["name"] == "dsml"
    assert driver["version"] == "1.2.3"
    assert driver["rules"][0] == {
        "defaultConfiguration": {"level": "error"},
        "help": {"text": "Do C."},
        "id": "ERR-001",
        "name": "ERR001",
        "properties": {"category": "ERR"},
        "shortDescription": {"text": "An error finding."},
    }
    assert [rule["id"] for rule in driver["rules"]] == ["ERR-001", "INF-001", "WRN-001"]
    assert [rule["defaultConfiguration"]["level"] for rule in driver["rules"]] == [
        "error",
        "note",
        "warning",
    ]
    assert run["results"] == [
        {
            "level": "note",
            "message": {"text": "A warning finding."},
            "ruleId": "WRN-001",
            "ruleIndex": 2,
        },
        {
            "level": "error",
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": "model/a.sysml"},
                        "region": {"startColumn": 5, "startLine": 3},
                    }
                },
                {"logicalLocations": [{"fullyQualifiedName": "Order"}]},
            ],
            "message": {"text": "Text."},
            "ruleId": "ERR-001",
            "ruleIndex": 0,
        },
        {
            "level": "warning",
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": "b.sysml"},
                        "region": {"startColumn": 2, "startLine": 1},
                    }
                }
            ],
            "message": {"text": "A warning finding."},
            "ruleId": "WRN-001",
            "ruleIndex": 2,
        },
    ]


# trace: PRD-VAL-006
def test_sarif_of_a_finding_with_no_rule_metadata() -> None:
    data = _check_schema(sarif_report((Finding("ABC-001", "error", "Text."),), {}, "1.2.3"))
    assert data["runs"][0]["results"] == [
        {"level": "error", "message": {"text": "Text."}, "ruleId": "ABC-001"}
    ]


def _write_project(root: Path) -> None:
    """Write a configuration file and a model with a SYN-002 finding in `root`."""
    (root / "model").mkdir(parents=True)
    # Add @DsmlVersion on line 4, thus STR-001 gives no error.
    text = SYN_002_REJECT.read_text(encoding="utf-8").replace(
        "package SynReject {",
        "package SynReject { private import DSML::*; @DsmlVersion { major = 1; minor = 0; }",
    )
    (root / "model" / SYN_002_REJECT.name).write_text(text, encoding="utf-8")
    (root / "dsml.toml").write_text('schema = 1\n\n[model]\npaths = ["model"]\n', encoding="utf-8")


# trace: PRD-VAL-006, PRD-CORE-028, PRD-CORE-033
def test_validate_writes_sarif(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path / "project")
    monkeypatch.chdir(tmp_path)
    argv = ["validate", "--config", "project/dsml.toml", "--format", "sarif"]
    assert main(argv) == 0
    first = capsys.readouterr().out
    assert main(argv) == 0
    assert capsys.readouterr().out == first
    assert str(tmp_path) not in first
    assert "\r" not in first
    data = _check_schema(first)
    results = data["runs"][0]["results"]
    assert results
    for item in results:
        assert item["ruleId"] == "SYN-002"
        assert item["level"] == "warning"
        location = item["locations"][0]["physicalLocation"]
        assert location["artifactLocation"]["uri"] == "model/reject.sysml"
    assert main([*argv, "--fail-on", "warning"]) == 1
    assert capsys.readouterr().out == first


# trace: PRD-VAL-006, PRD-CORE-028
def test_validate_writes_sarif_to_a_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["validate", "--format", "sarif", "--output", "findings.sarif"]) == 0
    first = (tmp_path / "findings.sarif").read_bytes()
    assert main(["validate", "--format", "sarif", "--output", "findings.sarif"]) == 0
    assert (tmp_path / "findings.sarif").read_bytes() == first
    data = _check_schema(first.decode())
    uris = {
        item["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        for item in data["runs"][0]["results"]
    }
    assert uris == {"model/reject.sysml"}
