"""Tests of the safe names for generated code (story #37)."""

import pytest

from dsml.generate.names import camel_case, kebab_case, pascal_case, python_name, snake_case, words


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("OrderService", ["order", "service"]),
        ("orderService", ["order", "service"]),
        ("order_service", ["order", "service"]),
        ("order-service", ["order", "service"]),
        ("order service", ["order", "service"]),
        ("HTTPServer", ["http", "server"]),
        ("userID", ["user", "id"]),
        ("v2Api", ["v2", "api"]),
        ("R-001", ["r", "001"]),
        ("ABC123", ["abc123"]),
        ("OrderService::CancelOrder", ["order", "service", "cancel", "order"]),
    ],
)
def test_words(name: str, expected: list[str]) -> None:
    assert words(name) == expected


def test_name_forms() -> None:
    assert snake_case("CancelOrder") == "cancel_order"
    assert kebab_case("CancelOrder") == "cancel-order"
    assert pascal_case("cancel_order") == "CancelOrder"
    assert pascal_case("HTTPServer") == "HttpServer"
    assert camel_case("cancel_order") == "cancelOrder"
    assert python_name("CancelOrder") == "cancel_order"


@pytest.mark.parametrize(
    ("name", "expected"), [("class", "class_"), ("Import", "import_"), ("type", "type_")]
)
def test_python_name_of_a_keyword(name: str, expected: str) -> None:
    assert python_name(name) == expected


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("", "has no letter or digit"),
        ("--", "has no letter or digit"),
        ("1st", "start with a digit"),
    ],
)
def test_name_errors(name: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        snake_case(name)
