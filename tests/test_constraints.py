"""Tests of the evaluation of the formal constraints (story #32).

Most tests start a private `sysml-grpc` child process. They use the example
model of the DSML PRD and the test model `tests/models/ir/constraints.sysml`,
which gives "true", "false" and "unknown" results.
"""

import re
from collections.abc import Iterator
from pathlib import Path

import jsonschema
import pytest
from jsonschema.protocols import Validator

from dsml.adapter import constraints
from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.ir.model import ConstraintResult, Ir, Location
from dsml.ir.schema import load_schema
from dsml.ir.writer import to_data, write_ir
from dsml.library import library_document

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = "docs/model/examples/order-service.sysml"
TEST_MODEL = "tests/models/ir/constraints.sysml"


def _convert(engine: Engine, file: str) -> Ir:
    parsed = engine.parse_texts(
        [library_document(), (file, (ROOT / file).read_text(encoding="utf-8"))]
    )
    assert [str(item) for item in parsed.diagnostics] == []
    return build_ir(parsed, [file])


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    with Engine() as started:
        yield started


@pytest.fixture(scope="module")
def example(engine: Engine) -> Ir:
    return _convert(engine, EXAMPLE)


@pytest.fixture(scope="module")
def test_model(engine: Engine) -> Ir:
    return _convert(engine, TEST_MODEL)


def _results(ir: Ir) -> dict[tuple[str, int, str], tuple[str, tuple[str, ...]]]:
    return {
        (item.requirement, item.index, item.environment): (item.value, item.missing_features)
        for item in ir.constraint_results
    }


def _validator() -> Validator:
    return jsonschema.Draft202012Validator(load_schema())


# Results ---------------------------------------------------------------------


# trace: PRD-CORE-054
def test_example_ir_holds_a_result_for_each_constraint_and_environment(example: Ir) -> None:
    location = Location(file=EXAMPLE, line=35, column=9)
    assert sorted(example.constraint_results, key=ConstraintResult.sort_key) == [
        ConstraintResult(
            requirement="R-002",
            index=1,
            environment=f"OrderService::{environment}",
            value="true",
            location=location,
        )
        for environment in ("dev", "prod", "staging")
    ]


# trace: PRD-CORE-054, PRD-DSML-018
def test_true_false_and_unknown_results_for_each_environment(test_model: Ir) -> None:
    assert _results(test_model) == {
        ("R-020", 1, "Store::dev"): ("false", ()),
        ("R-020", 1, "Store::prod"): ("true", ()),
        ("R-020", 2, "Store::dev"): ("unknown", ("apiAws.memory", "dbAws.instanceClass")),
        ("R-020", 2, "Store::prod"): ("unknown", ("apiAws.memory",)),
        ("R-020", 3, "Store::dev"): ("true", ()),
        ("R-020", 3, "Store::prod"): ("true", ()),
        ("R-021", 1, "Store::dev"): ("true", ()),
        ("R-021", 1, "Store::prod"): ("true", ()),
    }


def test_result_locations_point_to_the_constraints(test_model: Ir) -> None:
    lines = (ROOT / TEST_MODEL).read_text(encoding="utf-8").split("\n")
    for result in test_model.constraint_results:
        assert result.location.file == TEST_MODEL
        text = lines[result.location.line - 1][result.location.column - 1 :]
        assert text.startswith("require constraint")


def test_model_with_no_environment_has_no_results(engine: Engine) -> None:
    text = (ROOT / TEST_MODEL).read_text(encoding="utf-8")
    text = re.sub(r"#Environment part dev \{[^\n]*\}\n", "", text)
    text = re.sub(r"#Environment part prod \{.*?\n    \}\n", "", text, flags=re.DOTALL)
    text = text.replace("prod.dbProd.multiAz", "dbAws.multiAz")
    assert "#Environment" not in text
    parsed = engine.parse_texts([library_document(), (TEST_MODEL, text)])
    assert [str(item) for item in parsed.diagnostics] == []
    assert build_ir(parsed, [TEST_MODEL]).constraint_results == ()


# IR form ---------------------------------------------------------------------


# trace: PRD-CORE-022, PRD-CORE-025, PRD-CORE-028
def test_ir_with_results_passes_the_schema_and_is_stable(engine: Engine, test_model: Ir) -> None:
    _validator().validate(to_data(test_model))
    text = write_ir(test_model).decode()
    assert '"missingFeatures": [\n' in text
    assert not re.search(r"\w__\w", text)
    assert write_ir(_convert(engine, TEST_MODEL)) == write_ir(test_model)


# Expressions -----------------------------------------------------------------


def test_chains_skip_keywords_strings_comments_and_members() -> None:
    expression = (
        "a.b == \"x.y\" and not c::d.e /* f.g */ or h->size() > 1.5 and (i).j implies 'k l'.m // n"
    )
    found = [chain.text for chain in constraints._chains(expression)]  # pyright: ignore[reportPrivateUsage]
    assert found == ["a.b", "c::d.e", "h", "i", "'k l'.m"]


def test_replace_changes_only_the_head_of_a_chain() -> None:
    expression = "dbAws.multiAz == true and Store::dbAws.cpu > 1 and other.dbAws == 2"
    chains = list(constraints._chains(expression))  # pyright: ignore[reportPrivateUsage]
    substitutions = {"dbAws": "Store::prod::dbProd", "Store::dbAws": "Store::prod::dbProd"}
    assert constraints._replace(expression, chains, substitutions) == (  # pyright: ignore[reportPrivateUsage]
        "Store::prod::dbProd.multiAz == true and Store::prod::dbProd.cpu > 1 and other.dbAws == 2"
    )
