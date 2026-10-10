"""Tests of the example model of the DSML PRD (story #14).

These tests start a private `sysml-grpc` child process. If the binary is not
in the cache, the `opensysml` client downloads it one time.
"""

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from dsml.adapter.engine import ConstraintResult, Engine, ParsedModel
from dsml.library import library_document

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
DSML_PRD = ROOT / "docs" / "prd" / "01-dsml-prd.md"
NAMESPACE = "OrderService"


@pytest.fixture(scope="module")
def example() -> Iterator[ParsedModel]:
    with Engine() as engine:
        yield engine.parse_texts([library_document(), _example_document()])


def _example_document() -> tuple[str, str]:
    """Give the example as a (name, text) pair, with a name relative to the root."""
    return (EXAMPLE.relative_to(ROOT).as_posix(), EXAMPLE.read_text(encoding="utf-8"))


# trace: PRD-DSML-004, PRD-DSML-008, PRD-TOP-011
def test_example_model_parses_and_resolves(example: ParsedModel) -> None:
    assert [str(item) for item in example.diagnostics] == []


# trace: PRD-DSML-008
def test_example_model_without_the_library_does_not_resolve() -> None:
    """The library gives the keywords. Without it, the names do not resolve."""
    with Engine() as engine:
        model = engine.parse_texts([_example_document()])
    assert model.diagnostics
    assert {item.code for item in model.diagnostics} == {"unresolved"}


def test_example_in_the_dsml_prd_agrees_with_the_model_file() -> None:
    text = DSML_PRD.read_text(encoding="utf-8")
    match = re.search(
        r"^## Example model\n.*?^```sysml\n(.*?)^```$", text, re.MULTILINE | re.DOTALL
    )
    assert match is not None, "The DSML PRD must have a SysML block under 'Example model'."
    assert match.group(1) == EXAMPLE.read_text(encoding="utf-8")


# trace: PRD-DSML-003, PRD-DSML-009
@pytest.mark.parametrize(
    ("element", "keyword"),
    [
        ("ShopOwner", "Stakeholder"),
        ("trackOrders", "Need"),
        ("getOrderStatus", "Requirement"),
        ("orderDataSafe", "Requirement"),
        ("AppRoles", "Roles"),
        ("Order", "Entity"),
        ("Order::id", "Key"),
        ("CancelOrder", "Operation"),
        ("orderApi", "Application"),
        ("orderApi::orders", "Exposed"),
        ("orderApi::cancelOrder", "Exposed"),
        ("network", "Network"),
        ("apiService", "ContainerService"),
        ("orderDb", "RelationalDatabase"),
        ("users", "UserDirectory"),
        ("networkAws", "AwsVpc"),
        ("apiServiceAws", "AwsEcsService"),
        ("orderDbAws", "AwsRdsPostgres"),
        ("usersAws", "AwsCognito"),
        ("tooling", "ToolingAccount"),
        ("dev", "Environment"),
        ("staging", "Environment"),
        ("prod", "Environment"),
        ("prod::apiServiceProd", "Override"),
        ("prod::orderDbProd", "Override"),
    ],
)
def test_example_element_has_its_keyword(example: ParsedModel, element: str, keyword: str) -> None:
    assert example.has_metadata(element, f"DSML::{keyword}", NAMESPACE)


# trace: PRD-DSML-042
@pytest.mark.parametrize(
    "expression",
    [
        "apiServiceAws.desiredCount == 1",
        "prod.apiServiceProd.desiredCount == 3",
        "prod.apiServiceProd.cpu == 512",
        "orderDbAws.multiAz == false",
        "prod.orderDbProd.multiAz == true",
        'prod.orderDbProd.instanceClass == "db.t4g.micro"',
    ],
)
def test_environment_override_changes_only_its_attribute(
    example: ParsedModel, expression: str
) -> None:
    assert example.evaluate_bool(expression, NAMESPACE)


# trace: PRD-CORE-054
def test_formal_constraint_of_the_example_holds(example: ParsedModel) -> None:
    result = example.evaluate_requirement(f"{NAMESPACE}::orderDataSafe")
    assert result == ConstraintResult(value="true")
