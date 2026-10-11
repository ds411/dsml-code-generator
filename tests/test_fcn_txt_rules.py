"""Tests of the FCN rules, the TXT rules and the project dictionary (story #65).

Each rule has one model that it accepts and one model that it rejects
(PRD-VAL-008). The models are in `tests/models/rules/<rule>/`.
"""

import ast
import re
from pathlib import Path
from types import ModuleType

import pytest
from conftest import RULE_MODELS, RunRule

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.config import Configuration, Rules
from dsml.ir.model import ConstraintResult, Element, Finding, Ir, Location
from dsml.library import library_document
from dsml.validate.dictionary import Term, dictionary, load_dictionary
from dsml.validate.engine import Validator
from dsml.validate.rules import fcn, registry, txt
from dsml.validate.rules.txt import sentences, word_count

ROOT = Path(__file__).resolve().parent.parent
TOP_LEVEL_PRD = ROOT / "docs" / "prd" / "00-top-level-prd.md"
RULE_IDS = ("FCN-001", "FCN-002", "TXT-001", "TXT-002", "TXT-003")


def _at(rule: str, line: int, column: int) -> Location:
    return Location(f"tests/models/rules/{rule}/reject.sysml", line, column)


# trace: PRD-VAL-015
@pytest.mark.parametrize(
    ("rule_id", "severity"),
    [
        ("FCN-001", "error"),
        ("FCN-002", "warning"),
        ("TXT-001", "warning"),
        ("TXT-002", "warning"),
        ("TXT-003", "warning"),
    ],
)
def test_registry_contains_the_rule_with_its_default_severity(rule_id: str, severity: str) -> None:
    assert registry()[rule_id].rule.severity == severity


# trace: PRD-VAL-008
@pytest.mark.parametrize("rule_id", RULE_IDS)
def test_rule_accepts_its_accept_model(run_rule: RunRule, rule_id: str) -> None:
    assert run_rule(rule_id, "accept.sysml") == ()


# trace: PRD-VAL-008, PRD-VAL-012, PRD-CORE-054
def test_fcn_001_rejects_its_reject_model(run_rule: RunRule) -> None:
    assert run_rule("FCN-001", "reject.sysml") == (
        Finding(
            "FCN-001",
            "error",
            'The formal constraint 1 of the requirement "R-001" is false in the environment "dev".',
            _at("FCN-001", 22, 9),
            "R-001",
        ),
    )


# trace: PRD-VAL-008, PRD-VAL-012, PRD-CORE-054
def test_fcn_002_rejects_its_reject_model_and_names_the_features(run_rule: RunRule) -> None:
    start = 'The formal constraint 1 of the requirement "R-001" is unknown in the environment'
    assert run_rule("FCN-002", "reject.sysml") == (
        Finding(
            "FCN-002",
            "warning",
            f'{start} "dev". These features have no value: apiAws.memory, dbAws.instanceClass.',
            _at("FCN-002", 26, 9),
            "R-001",
        ),
        Finding(
            "FCN-002",
            "warning",
            f'{start} "prod". These features have no value: apiAws.memory.',
            _at("FCN-002", 26, 9),
            "R-001",
        ),
    )


# trace: PRD-VAL-012, PRD-CORE-026
def test_fcn_rules_read_only_the_ir() -> None:
    location = Location("model/a.sysml", 3, 5)
    ir = Ir(
        elements=(Element("R-1", "Requirement", "speed", "P::speed", location, short_name="R-1"),),
        constraint_results=(
            ConstraintResult("R-1", 1, "P::dev", "false", location),
            ConstraintResult("R-1", 2, "P::dev", "unknown", location),
            ConstraintResult("R-1", 3, "P::dev", "true", location),
        ),
    )
    rules = {check.rule.id: check for check in fcn.RULES}
    findings = Validator(Configuration(), rules).run(ir)
    # The environment is not an element of the IR, so the message gives its identity.
    start = 'The formal constraint {} of the requirement "R-1" is {} in the environment "P::dev".'
    assert [(finding.rule, finding.message) for finding in findings] == [
        ("FCN-001", start.format(1, "false")),
        ("FCN-002", start.format(2, "unknown")),
    ]


# trace: PRD-CORE-020, PRD-CORE-026
@pytest.mark.parametrize("module", [fcn, txt])
def test_rule_modules_do_not_import_opensysml(module: ModuleType) -> None:
    source = Path(str(module.__file__)).read_text(encoding="utf-8")
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    assert not [name for name in names if name.split(".")[0] == "opensysml"]
    assert not [name for name in names if name.startswith("dsml.adapter")]


# trace: PRD-VAL-008, PRD-VAL-013, PRD-VAL-014
def test_txt_001_rejects_its_reject_model(run_rule: RunRule) -> None:
    assert run_rule("TXT-001", "reject.sysml") == (
        Finding(
            "TXT-001",
            "warning",
            'The sentence 2 in the text of the need "N-001" has 28 words. The limit is 25 words.',
            _at("TXT-001", 10, 5),
            "N-001",
        ),
        Finding(
            "TXT-001",
            "warning",
            'The sentence 1 in the text of the requirement "R-001" has 28 words. '
            "The limit is 25 words.",
            _at("TXT-001", 20, 5),
            "R-001",
        ),
    )


# trace: PRD-VAL-008, PRD-VAL-013
def test_txt_002_rejects_its_reject_model(run_rule: RunRule) -> None:
    def finding(element: str, line: int, words: str) -> Finding:
        message = f'The text of the requirement "{element}" uses {words} in place of "must".'
        return Finding("TXT-002", "warning", message, _at("TXT-002", line, 5), element)

    assert run_rule("TXT-002", "reject.sysml") == (
        finding("R-001", 7, '"shall"'),
        finding("R-002", 11, '"may" and "should"'),
        finding("R-003", 15, '"will"'),
    )


# trace: PRD-VAL-008, PRD-VAL-013
def test_txt_003_rejects_its_reject_model(run_rule: RunRule) -> None:
    assert run_rule("TXT-003", "reject.sysml") == (
        Finding(
            "TXT-003",
            "warning",
            'The text of the requirement "R-001" has 2 "must". It can contain more than one '
            "requirement.",
            _at("TXT-003", 7, 5),
            "R-001",
        ),
    )


# trace: PRD-VAL-013
@pytest.mark.parametrize("rule_id", ["TXT-001", "TXT-002", "TXT-003"])
def test_txt_rules_give_no_finding_when_the_set_is_off(rule_engine: Engine, rule_id: str) -> None:
    path = RULE_MODELS / rule_id / "reject.sysml"
    name = path.relative_to(ROOT).as_posix()
    parsed = rule_engine.parse_texts([library_document(), (name, path.read_text(encoding="utf-8"))])
    ir = build_ir(parsed, [name])
    txt_rules = {check.rule.id: check for check in txt.RULES}
    assert Validator(Configuration(), txt_rules).run(ir) == ()
    turned_on = Validator(Configuration(rules=Rules(optional=("TXT",))), txt_rules).run(ir)
    assert rule_id in {finding.rule for finding in turned_on}


# trace: PRD-VAL-013
def test_validate_gives_no_txt_finding_by_default() -> None:
    ir = Ir(
        elements=(
            Element(
                "R-1",
                "Requirement",
                "a",
                "P::a",
                Location("model/a.sysml", 1, 1),
                short_name="R-1",
                doc="The API shall log each request. It must log it. It must keep it.",
            ),
        )
    )
    assert not any(finding.rule.startswith("TXT") for finding in Validator(Configuration()).run(ir))
    turned_on = Validator(Configuration(rules=Rules(optional=("TXT",)))).run(ir)
    assert [finding.rule for finding in turned_on if finding.rule.startswith("TXT")] == [
        "TXT-002",
        "TXT-003",
    ]


# trace: PRD-VAL-014
@pytest.mark.parametrize(
    ("sentence", "count"),
    [
        ("The API must log each request.", 6),
        ("Each trace link and each suspect link goes into the report.", 9),
        ("The create-once file is a hand-written file - after that.", 7),
        ("The value is 1.5 GiB.", 5),
    ],
)
def test_word_count_counts_a_dictionary_term_as_one_word(sentence: str, count: int) -> None:
    assert word_count(sentence) == count


# trace: PRD-VAL-014
def test_sentences_ignore_code_and_line_ends() -> None:
    text = "The API must log.\nIt must use `a. b. c`! Is it\n  correct?"
    assert sentences(text) == ("The API must log.", "It must use CODE !", "Is it correct?")


# trace: PRD-VAL-014
def test_packaged_dictionary_agrees_with_the_top_level_prd() -> None:
    text = TOP_LEVEL_PRD.read_text(encoding="utf-8").split("## Project dictionary", 1)[1]
    rows = re.findall(r"^\| (.+?) \| Technical (noun|verb) \|", text, re.MULTILINE)
    assert rows
    assert dictionary() == tuple(Term(word, kind) for word, kind in rows)  # type: ignore[arg-type]


# trace: PRD-VAL-014
def test_dictionary_refuses_an_unknown_term_type() -> None:
    with pytest.raises(ValueError, match="has the type"):
        load_dictionary('[[term]]\nword = "x"\ntype = "adverb"\n')


# trace: PRD-VAL-014
@pytest.mark.parametrize("rule_id", ["TXT-001", "TXT-002", "TXT-003"])
def test_txt_messages_do_not_claim_ste_compliance(rule_id: str) -> None:
    rule = registry()[rule_id].rule
    for text in (rule.message, rule.fix_hint):
        assert "STE" not in text
        assert "compliance" not in text.lower()
