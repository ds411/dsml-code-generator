"""Tests of the conversion of the application, infrastructure and verification layers (story #31).

These tests start a private `sysml-grpc` child process. They use the example
model of the DSML PRD and the test model `tests/models/ir/solution-layers.sysml`,
which uses the forms that the example model does not use. Story #159 added the
test models `tests/models/ir/views.sysml` and
`tests/models/ir/view-references.sysml` for the views, the navigation and the
static sites.
"""

import re
from collections.abc import Iterator
from pathlib import Path

import jsonschema
import pytest
from jsonschema.protocols import Validator

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.adapter.solution import ENTITY, LITERALS, NAVIGATION, OPERATION
from dsml.ir.environments import environments, realization_attributes
from dsml.ir.model import (
    Annotation,
    Attribute,
    BooleanValue,
    Element,
    EnumValue,
    Finding,
    IntegerValue,
    Ir,
    Link,
    ListValue,
    Location,
    Multiplicity,
    ReferenceValue,
    StringValue,
    Value,
)
from dsml.ir.operations import CRUD_DEFAULTS
from dsml.ir.schema import load_schema
from dsml.ir.writer import to_data, write_ir
from dsml.library import library_document

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = "docs/model/examples/order-service.sysml"
TEST_MODEL = "tests/models/ir/solution-layers.sysml"
VIEWS_MODEL = "tests/models/ir/views.sysml"
VIEW_REFERENCES_MODEL = "tests/models/ir/view-references.sysml"
VIEWS_GOLDEN = ROOT / "tests/golden/ir/views.ir.json"
_FILES = {"example": EXAMPLE, "test_model": TEST_MODEL, "views": VIEWS_MODEL}


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


@pytest.fixture(scope="module")
def views(engine: Engine) -> Ir:
    return _convert(engine, VIEWS_MODEL)


# The kinds of the needs and requirements layers (story #30).
_NEEDS_KINDS = {"Package", "Stakeholder", "Need", "Requirement"}
_SOLUTION_LINKS = {"satisfy", "allocate", "realizes", "uses", "calls", "verify"}


def _links(ir: Ir) -> set[Link]:
    return {link for link in ir.links if link.type in _SOLUTION_LINKS}


def _element(ir: Ir, identity: str) -> Element:
    found = [element for element in ir.elements if element.identity == identity]
    assert len(found) == 1, identity
    return found[0]


def _values(element: Element) -> dict[str, Value]:
    return {attribute.name: attribute.value for attribute in element.attributes}


def _enum(enumeration: str, *literals: str) -> ListValue:
    return ListValue(tuple(EnumValue(enumeration, literal) for literal in literals))


def _validator() -> Validator:
    return jsonschema.Draft202012Validator(load_schema())


def at(file: str, line: int, column: int) -> Location:
    return Location(file, line, column)


# Elements -------------------------------------------------------------------


# trace: PRD-CORE-024, PRD-DSML-020, PRD-DSML-022, PRD-DSML-027, PRD-DSML-028
# trace: PRD-DSML-033, PRD-DSML-035, PRD-DSML-037, PRD-DSML-041, PRD-DSML-043, PRD-DSML-045
def test_example_ir_holds_each_element_of_the_three_layers(example: Ir) -> None:
    kinds = {
        element.identity: element.kind
        for element in example.elements
        if element.kind not in _NEEDS_KINDS
    }
    assert kinds == {
        "OrderService::AppRoles": "Roles",
        "OrderService::OrderStatus": "Enumeration",
        "OrderService::Order": "Entity",
        "OrderService::Order::id": "Field",
        "OrderService::Order::status": "Field",
        "OrderService::Order::total": "Field",
        "OrderService::Order::note": "Field",
        "OrderService::CancelOrder": "Operation",
        "OrderService::CancelOrder::orderId": "Parameter",
        "OrderService::CancelOrder::order": "Parameter",
        "OrderService::orderApi": "Application",
        "OrderService::orderApi::orders": "Exposed",
        "OrderService::orderApi::cancelOrder": "Exposed",
        "OrderService::network": "Network",
        "OrderService::apiService": "ContainerService",
        "OrderService::orderDb": "RelationalDatabase",
        "OrderService::users": "UserDirectory",
        "OrderService::networkAws": "AwsVpc",
        "OrderService::apiServiceAws": "AwsEcsService",
        "OrderService::orderDbAws": "AwsRdsPostgres",
        "OrderService::usersAws": "AwsCognito",
        "OrderService::tooling": "ToolingAccount",
        "OrderService::dev": "Environment",
        "OrderService::staging": "Environment",
        "OrderService::prod": "Environment",
        "OrderService::prod::apiServiceProd": "Override",
        "OrderService::prod::orderDbProd": "Override",
        "V-001": "Verification",
        "V-002": "Verification",
    }


# trace: PRD-CORE-024, PRD-TRACE-001, PRD-TRACE-002, PRD-TRACE-003
def test_example_ir_holds_each_link_of_the_three_layers(example: Ir) -> None:
    file = EXAMPLE
    assert _links(example) == {
        Link("satisfy", "OrderService::orderApi", "R-001", at(file, 66, 5)),
        Link("uses", "OrderService::apiService", "OrderService::orderDb", at(file, 73, 5)),
        Link("uses", "OrderService::apiService", "OrderService::users", at(file, 74, 5)),
        Link("allocate", "OrderService::orderApi", "OrderService::apiService", at(file, 75, 5)),
        Link("realizes", "OrderService::networkAws", "OrderService::network", at(file, 82, 5)),
        Link(
            "realizes", "OrderService::apiServiceAws", "OrderService::apiService", at(file, 83, 5)
        ),
        Link("realizes", "OrderService::orderDbAws", "OrderService::orderDb", at(file, 84, 5)),
        Link("realizes", "OrderService::usersAws", "OrderService::users", at(file, 85, 5)),
        Link("satisfy", "OrderService::prod::orderDbProd", "R-002", at(file, 97, 5)),
        Link("verify", "V-001", "R-001", at(file, 104, 21)),
        Link("verify", "V-002", "R-002", at(file, 110, 21)),
    }


# trace: PRD-CORE-024, PRD-TRACE-001, PRD-DSML-030, PRD-DSML-040
def test_test_model_links(test_model: Ir) -> None:
    file = TEST_MODEL
    assert _links(test_model) == {
        Link("calls", "Shop::shopWeb", "Shop::shopApi", at(file, 54, 5)),
        Link("satisfy", "Shop::shopApi", "R-010", at(file, 55, 5)),
        Link("uses", "Shop::api", "Shop::secrets", at(file, 60, 5)),
        Link("allocate", "Shop::shopApi", "Shop::api", at(file, 61, 5)),
        Link("realizes", "Shop::netAws", "Shop::net", at(file, 66, 5)),
        Link("realizes", "Shop::apiAws", "Shop::api", at(file, 67, 5)),
        Link("realizes", "Shop::secretsAws", "Shop::secrets", at(file, 68, 5)),
        Link("satisfy", "Shop::apiAws", "R-010", at(file, 69, 5)),
        Link("verify", "V-010", "R-010", at(file, 86, 21)),
    }


# trace: PRD-CORE-024, PRD-CORE-033
@pytest.mark.parametrize("model", sorted(_FILES))
def test_each_element_and_link_has_a_source_location(
    model: str, request: pytest.FixtureRequest
) -> None:
    ir: Ir = request.getfixturevalue(model)
    file = _FILES[model]
    lines = (ROOT / file).read_text(encoding="utf-8").splitlines()
    for item in (*ir.elements, *ir.links):
        assert item.location.file == file
        text = lines[item.location.line - 1]
        # The location is the first character of the declaration or of its metadata prefix.
        assert text[: item.location.column - 1].strip() in ("", "objective {"), item


def test_element_locations_point_to_their_declarations(example: Ir) -> None:
    expected = {
        "OrderService::Order": (42, 5),
        "OrderService::Order::total": (45, 9),
        "OrderService::orderApi::orders": (58, 9),
        "OrderService::prod::apiServiceProd": (94, 9),
        "V-001": (100, 5),
        "V-002": (106, 5),
    }
    for identity, (line, column) in expected.items():
        assert _element(example, identity).location == at(EXAMPLE, line, column)


# Attributes -----------------------------------------------------------------


# trace: PRD-CORE-024, PRD-DSML-020, PRD-DSML-028, PRD-DSML-029
def test_application_and_operation_attributes(example: Ir) -> None:
    assert _values(_element(example, "OrderService::orderApi")) == {
        "target": EnumValue("DSML::Target", "fastapi")
    }
    assert _values(_element(example, "OrderService::CancelOrder")) == {
        "method": EnumValue("DSML::HttpMethod", "post"),
        "path": StringValue("/orders/{orderId}/cancel"),
    }


# trace: PRD-DSML-027, PRD-DSML-029, PRD-DSML-033
def test_exposed_entity_has_crud_roles_and_crud_defaults(example: Ir) -> None:
    orders = _element(example, "OrderService::orderApi::orders")
    assert orders.types == ("OrderService::Order",)
    assert orders.multiplicity == Multiplicity(0, None)
    assert _values(orders) == {
        "crud": _enum("DSML::CrudKind", "create", "read", "list"),
        "allowedRoles": _enum("OrderService::AppRoles", "clerk", "admin"),
        "public": BooleanValue(False),
        CRUD_DEFAULTS: ListValue(
            (
                ListValue(
                    (
                        EnumValue("DSML::CrudKind", "create"),
                        EnumValue("DSML::HttpMethod", "post"),
                        StringValue("/{entities}"),
                    )
                ),
                ListValue(
                    (
                        EnumValue("DSML::CrudKind", "read"),
                        EnumValue("DSML::HttpMethod", "get"),
                        StringValue("/{entities}/{id}"),
                    )
                ),
                ListValue(
                    (
                        EnumValue("DSML::CrudKind", "list"),
                        EnumValue("DSML::HttpMethod", "get"),
                        StringValue("/{entities}"),
                    )
                ),
            )
        ),
    }
    crud = next(attribute for attribute in orders.attributes if attribute.name == "crud")
    assert crud.location == at(EXAMPLE, 59, 13)


# trace: PRD-DSML-033
def test_exposed_operation_with_one_role_gives_a_list(example: Ir) -> None:
    cancel = _element(example, "OrderService::orderApi::cancelOrder")
    assert cancel.types == ("OrderService::CancelOrder",)
    assert _values(cancel) == {
        "allowedRoles": _enum("OrderService::AppRoles", "admin"),
        "public": BooleanValue(False),
    }


# trace: PRD-DSML-022, PRD-DSML-023, PRD-DSML-024, PRD-DSML-025
def test_fields_have_types_multiplicities_and_field_rules(example: Ir) -> None:
    key = _element(example, "OrderService::Order::id")
    assert key.types == ("DSML::Uuid",)
    assert key.multiplicity == Multiplicity(1, 1)
    assert key.annotations == (Annotation("Key", (), at(EXAMPLE, 43, 9)),)
    total = _element(example, "OrderService::Order::total")
    assert total.annotations == (
        Annotation(
            "FieldRules",
            (Attribute("minValue", IntegerValue(0), at(EXAMPLE, 45, 55)),),
            at(EXAMPLE, 45, 41),
        ),
    )
    note = _element(example, "OrderService::Order::note")
    assert note.multiplicity == Multiplicity(0, 1)
    assert [(item.name, item.value) for item in note.annotations[0].attributes] == [
        ("maxLength", IntegerValue(500))
    ]
    status = _element(example, "OrderService::Order::status")
    assert status.types == ("OrderService::OrderStatus",)


# trace: PRD-DSML-022, PRD-DSML-033
def test_enumerations_give_their_literals_in_model_order(example: Ir) -> None:
    assert _values(_element(example, "OrderService::OrderStatus")) == {
        LITERALS: _enum("OrderService::OrderStatus", "open", "shipped", "cancelled")
    }
    assert _values(_element(example, "OrderService::AppRoles")) == {
        LITERALS: _enum("OrderService::AppRoles", "clerk", "admin")
    }


# trace: PRD-DSML-028
def test_operation_parameters_have_directions(test_model: Ir) -> None:
    directions = {
        element.name: (element.direction, element.types)
        for element in test_model.elements
        if element.kind == "Parameter"
    }
    assert directions == {
        "productId": ("in", ("DSML::Uuid",)),
        "amount": ("inout", ("ScalarValues::Integer",)),
        "product": ("out", ("Shop::Product",)),
    }


# trace: PRD-DSML-025, PRD-DSML-026, PRD-DSML-034
def test_relations_rules_and_destructive_changes(test_model: Ir) -> None:
    category = _element(test_model, "Shop::Product::category")
    assert (category.kind, category.types, category.multiplicity) == (
        "Relation",
        ("Shop::Category",),
        Multiplicity(0, 1),
    )
    related = _element(test_model, "Shop::Product::related")
    assert (related.kind, related.multiplicity) == ("Relation", Multiplicity(0, None))
    name = _element(test_model, "Shop::Product::name")
    assert {item.name: item.value for item in name.annotations[0].attributes} == {
        "minLength": IntegerValue(1),
        "maxLength": IntegerValue(80),
        "pattern": StringValue("^[A-Z]"),
    }
    price = _element(test_model, "Shop::Product::price")
    assert {item.name: item.value for item in price.annotations[0].attributes} == {
        "precision": IntegerValue(10),
        "scale": IntegerValue(2),
    }
    label = _element(test_model, "Shop::Product::label")
    assert [(item.name, item.attributes) for item in label.annotations] == [
        ("Destructive", (Attribute("renamedFrom", StringValue("title"), at(TEST_MODEL, 28, 58)),))
    ]
    assert _element(test_model, "Shop::Product").doc == "A product that the shop sells."


# trace: PRD-DSML-027, PRD-DSML-029, PRD-DSML-033
def test_public_entity_and_other_crud_defaults(test_model: Ir) -> None:
    products = _values(_element(test_model, "Shop::shopApi::products"))
    assert products["public"] == BooleanValue(True)
    assert products[CRUD_DEFAULTS] == ListValue(
        (
            ListValue(
                (
                    EnumValue("DSML::CrudKind", "update"),
                    EnumValue("DSML::HttpMethod", "patch"),
                    StringValue("/{entities}/{id}"),
                )
            ),
            ListValue(
                (
                    EnumValue("DSML::CrudKind", "delete"),
                    EnumValue("DSML::HttpMethod", "delete"),
                    StringValue("/{entities}/{id}"),
                )
            ),
        )
    )
    assert "allowedRoles" not in products


# trace: PRD-DSML-045, PRD-DSML-046, PRD-DSML-048, PRD-DSML-049
def test_verification_attributes(example: Ir, test_model: Ir) -> None:
    assert _values(_element(example, "V-001")) == {
        "title": StringValue("Order status API test"),
        "method": EnumValue("DSML::VerificationMethod", "test"),
        "testFiles": ListValue((StringValue("app/features/order/read_order/test_endpoint.py"),)),
    }
    verification = _element(test_model, "V-010")
    assert verification.short_name == "V-010"
    assert verification.qualified_name == "Shop::listProductsTest"
    assert _values(verification)["testFiles"] == ListValue(
        (StringValue("tests/test_products.py"), StringValue("tests/test_catalog.py"))
    )
    assert _values(verification)["testCases"] == ListValue(
        (StringValue("tests/test_products.py::test_list"),)
    )


# trace: PRD-DSML-038, PRD-DSML-041, PRD-DSML-043
def test_infrastructure_attributes(example: Ir) -> None:
    assert _values(_element(example, "OrderService::apiServiceAws")) == {
        "cpu": IntegerValue(512),
        "memory": IntegerValue(1024),
        "desiredCount": IntegerValue(1),
    }
    assert _values(_element(example, "OrderService::orderDbAws")) == {
        "instanceClass": StringValue("db.t4g.micro"),
        "multiAz": BooleanValue(False),
    }
    assert _values(_element(example, "OrderService::tooling")) == {
        "accountId": StringValue("111111111111"),
        "region": StringValue("eu-west-1"),
    }
    assert _values(_element(example, "OrderService::prod")) == {
        "accountId": StringValue("444444444444"),
        "region": StringValue("eu-west-1"),
        "domain": StringValue("orders.example.com"),
    }


# Environments ---------------------------------------------------------------


# trace: PRD-DSML-041, PRD-DSML-042
def test_overrides_hold_only_the_changed_attributes(example: Ir) -> None:
    override = _element(example, "OrderService::prod::apiServiceProd")
    assert override.owner == "OrderService::prod"
    assert override.types == ("OrderService::apiServiceAws",)
    assert override.attributes == (Attribute("desiredCount", IntegerValue(3), at(EXAMPLE, 94, 58)),)
    assert _values(_element(example, "OrderService::prod::orderDbProd")) == {
        "multiAz": BooleanValue(True)
    }


# trace: PRD-DSML-041, PRD-DSML-042, PRD-CORE-026
@pytest.mark.parametrize(
    ("environment", "desired_count", "multi_az"),
    [
        ("OrderService::dev", 1, False),
        ("OrderService::staging", 1, False),
        ("OrderService::prod", 3, True),
    ],
)
def test_ir_gives_the_values_of_each_environment(
    example: Ir, environment: str, desired_count: int, multi_az: bool
) -> None:
    values = realization_attributes(example, environment)
    assert values["OrderService::apiServiceAws"]["desiredCount"].value == IntegerValue(
        desired_count
    )
    assert values["OrderService::apiServiceAws"]["cpu"].value == IntegerValue(512)
    assert values["OrderService::orderDbAws"]["multiAz"].value == BooleanValue(multi_az)
    assert values["OrderService::orderDbAws"]["instanceClass"].value == StringValue("db.t4g.micro")


def test_environment_values_of_the_test_model(test_model: Ir) -> None:
    assert [element.identity for element in environments(test_model)] == [
        "Shop::dev",
        "Shop::prod",
    ]
    prod = realization_attributes(test_model, "Shop::prod")
    assert {name: item.value for name, item in prod["Shop::apiAws"].items()} == {
        "cpu": IntegerValue(1024),
        "memory": IntegerValue(2048),
        "desiredCount": IntegerValue(2),
    }
    assert prod["Shop::netAws"]["natGatewayCount"].value == IntegerValue(2)
    dev = realization_attributes(test_model, "Shop::dev")
    assert dev["Shop::netAws"]["natGatewayCount"].value == IntegerValue(1)
    assert dev["Shop::secretsAws"] == {}


def test_unknown_environment_is_an_error(example: Ir) -> None:
    with pytest.raises(KeyError, match="no environment"):
        realization_attributes(example, "OrderService::qa")


# IR form --------------------------------------------------------------------


# trace: PRD-CORE-022, PRD-CORE-025
@pytest.mark.parametrize("model", sorted(_FILES))
def test_ir_passes_the_schema_and_has_no_internal_id(
    model: str, request: pytest.FixtureRequest
) -> None:
    ir: Ir = request.getfixturevalue(model)
    _validator().validate(to_data(ir))
    text = write_ir(ir).decode()
    # OpenSysML internal IDs have the form "Package__name" or "Package___4012".
    assert not re.search(r"\w__\w", text)
    assert "@id" not in text
    assert "sysx:" not in text


# trace: PRD-CORE-028
def test_two_conversions_give_the_same_bytes(engine: Engine, example: Ir) -> None:
    assert write_ir(_convert(engine, EXAMPLE)) == write_ir(example)


# Views, navigation and static sites (story #159) ------------------------------


# trace: PRD-CORE-024, PRD-DSML-031, PRD-DSML-035, PRD-DSML-037
def test_views_and_static_sites_are_elements(views: Ir) -> None:
    kinds = {
        element.identity: (element.kind, element.owner)
        for element in views.elements
        if element.kind in ("View", "StaticSite", "AwsStaticSite")
    }
    assert kinds == {
        "Portal::orderPortal::orderList": ("View", "Portal::orderPortal"),
        "Portal::orderPortal::orderDetail": ("View", "Portal::orderPortal"),
        "Portal::orderPortal::placeOrderForm": ("View", "Portal::orderPortal"),
        "Portal::adminPortal::orderAdmin": ("View", "Portal::adminPortal"),
        "Portal::portalSite": ("StaticSite", "Portal"),
        "Portal::adminSite": ("StaticSite", "Portal"),
        "Portal::portalSiteAws": ("AwsStaticSite", "Portal"),
        "Portal::adminSiteAws": ("AwsStaticSite", "Portal"),
    }
    assert views.findings == ()


# trace: PRD-CORE-024, PRD-DSML-031, PRD-DSML-033
def test_views_have_kind_reference_roles_and_public(views: Ir) -> None:
    roles = "Portal::PortalRoles"
    order_list = _element(views, "Portal::orderPortal::orderList")
    assert order_list.doc == "The list of the orders."
    assert sorted(order_list.attributes, key=Attribute.sort_key) == [
        Attribute(ENTITY, ReferenceValue("Portal::Order"), at(VIEWS_MODEL, 40, 13)),
        Attribute("kind", EnumValue("DSML::ViewKind", "list"), at(VIEWS_MODEL, 39, 13)),
        Attribute("public", BooleanValue(True), at(VIEWS_MODEL, 41, 13)),
    ]
    assert _values(_element(views, "Portal::orderPortal::orderDetail")) == {
        "kind": EnumValue("DSML::ViewKind", "detail"),
        ENTITY: ReferenceValue("Portal::Order"),
        "allowedRoles": _enum(roles, "clerk", "admin"),
        "public": BooleanValue(False),
    }
    # One role gives a list with one item.
    assert _values(_element(views, "Portal::orderPortal::placeOrderForm")) == {
        "kind": EnumValue("DSML::ViewKind", "form"),
        OPERATION: ReferenceValue("Portal::PlaceOrder"),
        "allowedRoles": _enum(roles, "clerk"),
        "public": BooleanValue(False),
    }


# trace: PRD-CORE-024, PRD-CORE-031, PRD-DSML-032
def test_navigation_keeps_the_order_of_the_model(views: Ir) -> None:
    portal = _element(views, "Portal::orderPortal")
    navigation = {item.name: item for item in portal.attributes}[NAVIGATION]
    assert navigation == Attribute(
        NAVIGATION,
        ListValue(
            (
                ReferenceValue("Portal::orderPortal::placeOrderForm"),
                ReferenceValue("Portal::orderPortal::orderList"),
                ReferenceValue("Portal::orderPortal::orderDetail"),
            )
        ),
        at(VIEWS_MODEL, 53, 9),
    )
    # The canonical JSON also keeps the order of the model.
    text = write_ir(views).decode()
    first = text.index('"target": "Portal::orderPortal::placeOrderForm"')
    assert first < text.index('"target": "Portal::orderPortal::orderList"')
    # One view gives a list with one item.
    admin = _values(_element(views, "Portal::adminPortal"))
    assert admin[NAVIGATION] == ListValue((ReferenceValue("Portal::adminPortal::orderAdmin"),))
    # An application with no navigation has no navigation attribute.
    assert NAVIGATION not in _values(_element(views, "Portal::orderApi"))


# trace: PRD-TRACE-001, PRD-DSML-037, PRD-DSML-039, PRD-DSML-040
def test_static_site_links(views: Ir) -> None:
    file = VIEWS_MODEL
    assert {link for link in _links(views) if "Site" in link.source + link.target} == {
        Link("uses", "Portal::portalSite", "Portal::users", at(file, 72, 5)),
        Link("uses", "Portal::adminSite", "Portal::users", at(file, 73, 5)),
        Link("allocate", "Portal::orderPortal", "Portal::portalSite", at(file, 75, 5)),
        Link("allocate", "Portal::adminPortal", "Portal::adminSite", at(file, 76, 5)),
        Link("realizes", "Portal::portalSiteAws", "Portal::portalSite", at(file, 83, 5)),
        Link("realizes", "Portal::adminSiteAws", "Portal::adminSite", at(file, 84, 5)),
    }


# trace: PRD-CORE-027, PRD-CORE-028, PRD-CORE-031
def test_views_ir_agrees_with_its_golden_file(views: Ir) -> None:
    assert write_ir(views) == VIEWS_GOLDEN.read_bytes(), (
        f"The IR of {VIEWS_MODEL} is not the same as {VIEWS_GOLDEN.relative_to(ROOT)}. "
        "If the change is correct, run scripts/write_golden_ir.py."
    )


# trace: PRD-CORE-021, PRD-DSML-031
def test_view_with_a_wrong_reference_gives_syn_001(engine: Engine) -> None:
    file = VIEW_REFERENCES_MODEL
    parsed = engine.parse_texts(
        [library_document(), (file, (ROOT / file).read_text(encoding="utf-8"))]
    )
    ir = build_ir(parsed, [file])
    hint = 'Give it with "ref :>> {0} : <{1}>;".'
    # OpenSysML gives only a warning for the reference to a part definition
    # that is not an entity.
    assert [(item.rule, item.location) for item in ir.findings if item.rule == "SYN-002"] == [
        ("SYN-002", at(file, 30, 21))
    ]
    assert sorted(
        (item for item in ir.findings if item.rule == "SYN-001"), key=Finding.sort_key
    ) == [
        Finding(
            "SYN-001",
            "error",
            'The list view "Wrong::web::noEntity" must refer to one entity with the keyword '
            "#Entity. " + hint.format("entity", "Entity"),
            at(file, 24, 9),
            "Wrong::web::noEntity",
        ),
        Finding(
            "SYN-001",
            "error",
            'The detail view "Wrong::web::wrongTarget" must refer to one entity with the '
            "keyword #Entity. " + hint.format("entity", "Entity"),
            at(file, 30, 13),
            "Wrong::web::wrongTarget",
        ),
        Finding(
            "SYN-001",
            "error",
            'The form view "Wrong::web::noOperation" must refer to one operation with the '
            "keyword #Operation. " + hint.format("operation", "Operation"),
            at(file, 33, 9),
            "Wrong::web::noOperation",
        ),
    ]
    # The IR keeps the elements, because the parse gave no error.
    assert _values(_element(ir, "Wrong::web::wrongTarget"))[ENTITY] == ReferenceValue("Wrong::Note")
    _validator().validate(to_data(ir))
