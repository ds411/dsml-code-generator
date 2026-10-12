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


# The phase 2 reference model "order portal" (story #160).
PORTAL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
PORTAL_NAMESPACE = "OrderPortal"


@pytest.fixture(scope="module")
def portal() -> Iterator[ParsedModel]:
    document = (PORTAL.relative_to(ROOT).as_posix(), PORTAL.read_text(encoding="utf-8"))
    with Engine() as engine:
        yield engine.parse_texts([library_document(), document])


# trace: PRD-TOP-011, PRD-DSML-021
def test_order_portal_parses_and_resolves(portal: ParsedModel) -> None:
    assert [str(item) for item in portal.diagnostics] == []


# trace: PRD-DSML-020, PRD-DSML-030, PRD-DSML-031, PRD-DSML-039, PRD-DSML-040
@pytest.mark.parametrize(
    ("element", "keyword"),
    [
        ("Clerk", "Stakeholder"),
        ("manageOrdersInBrowser", "Need"),
        ("showOrdersInPortal", "Requirement"),
        ("placeOrderInPortal", "Requirement"),
        ("PlaceOrder", "Operation"),
        ("orderApi", "Application"),
        ("orderPortal", "Application"),
        ("orderPortal::orderList", "View"),
        ("orderPortal::orderDetail", "View"),
        ("orderPortal::placeOrderForm", "View"),
        ("orderPortal::cancelOrderForm", "View"),
        ("portalSite", "StaticSite"),
        ("portalSiteAws", "AwsStaticSite"),
        ("showOrdersTest", "Verification"),
        ("placeOrderTest", "Verification"),
    ],
)
def test_order_portal_element_has_its_keyword(
    portal: ParsedModel, element: str, keyword: str
) -> None:
    assert portal.has_metadata(element, f"DSML::{keyword}", PORTAL_NAMESPACE)


# trace: PRD-DSML-020, PRD-DSML-031, PRD-DSML-032
@pytest.mark.parametrize(
    "expression",
    [
        "orderPortal.target == DSML::Target::react",
        "orderApi.target == DSML::Target::fastapi",
        "orderPortal.orderList.entity istype Order",
        "orderPortal.orderDetail.entity istype Order",
        "orderPortal.placeOrderForm.operation istype PlaceOrder",
        "orderPortal.cancelOrderForm.operation istype CancelOrder",
        "orderPortal.navigation#(1) == orderPortal.orderList",
        "orderPortal.navigation#(2) == orderPortal.placeOrderForm",
    ],
)
def test_order_portal_views_and_navigation(portal: ParsedModel, expression: str) -> None:
    assert portal.evaluate_bool(expression, PORTAL_NAMESPACE)


# trace: PRD-CORE-054
def test_formal_constraint_of_the_order_portal_holds(portal: ParsedModel) -> None:
    result = portal.evaluate_requirement(f"{PORTAL_NAMESPACE}::orderDataSafe")
    assert result == ConstraintResult(value="true")


# The phase 3 reference model "order web" (story #178).
WEB = ROOT / "docs" / "model" / "examples" / "order-web" / "order-web.sysml"
WEB_NAMESPACE = "OrderWeb"


@pytest.fixture(scope="module")
def web() -> Iterator[ParsedModel]:
    document = (WEB.relative_to(ROOT).as_posix(), WEB.read_text(encoding="utf-8"))
    with Engine() as engine:
        yield engine.parse_texts([library_document(), document])


# trace: PRD-TOP-011
def test_order_web_parses_and_resolves(web: ParsedModel) -> None:
    assert [str(item) for item in web.diagnostics] == []


# trace: PRD-DSML-020, PRD-DSML-027, PRD-DSML-028, PRD-DSML-031, PRD-DSML-033
# trace: PRD-DSML-039, PRD-DSML-040
@pytest.mark.parametrize(
    ("element", "keyword"),
    [
        ("Clerk", "Stakeholder"),
        ("manageOrdersOnWeb", "Need"),
        ("manageOrderData", "Requirement"),
        ("cancelOrderOnWeb", "Requirement"),
        ("AppRoles", "Roles"),
        ("Order", "Entity"),
        ("CancelOrder", "Operation"),
        ("orderWeb", "Application"),
        ("orderWeb::orders", "Exposed"),
        ("orderWeb::cancelOrder", "Exposed"),
        ("orderWeb::orderList", "View"),
        ("orderWeb::orderDetail", "View"),
        ("orderWeb::cancelOrderForm", "View"),
        ("webService", "ContainerService"),
        ("secrets", "SecretStore"),
        ("secretsAws", "AwsSecrets"),
        ("showOrdersTest", "Verification"),
        ("cancelOrderTest", "Verification"),
    ],
)
def test_order_web_element_has_its_keyword(web: ParsedModel, element: str, keyword: str) -> None:
    assert web.has_metadata(element, f"DSML::{keyword}", WEB_NAMESPACE)


# trace: PRD-DSML-020, PRD-DSML-031, PRD-DSML-032
@pytest.mark.parametrize(
    "expression",
    [
        "orderWeb.target == DSML::Target::nextjs",
        "orderWeb.orderList.entity istype Order",
        "orderWeb.orderDetail.entity istype Order",
        "orderWeb.cancelOrderForm.operation istype CancelOrder",
        "orderWeb.navigation#(1) == orderWeb.orderList",
    ],
)
def test_order_web_application_and_views(web: ParsedModel, expression: str) -> None:
    assert web.evaluate_bool(expression, WEB_NAMESPACE)


# trace: PRD-CORE-054
def test_formal_constraint_of_the_order_web_holds(web: ParsedModel) -> None:
    result = web.evaluate_requirement(f"{WEB_NAMESPACE}::orderDataSafe")
    assert result == ConstraintResult(value="true")
