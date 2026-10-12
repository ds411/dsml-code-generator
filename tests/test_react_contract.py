"""The contract test of the React client of the order portal (story #176).

The test compares the golden React client of the order portal with the
golden `openapi.gen.json` of the FastAPI application that it calls
(PRD-APP-005). For each operation of the client, the method, the path,
the parameters, the request body and the response must agree. For each
field, the type, the optional state and the field rules must agree with
the Zod schema (PRD-APP-211). The helper modules are in `tests/contract/`.

The negative tests change a copy of the OpenAPI document or of the React
files. Each change must give a difference.
"""

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from contract.openapi import openapi_operations
from contract.react_client import client_operations, read_client
from contract.shapes import ContractError, compare

ROOT = Path(__file__).resolve().parent.parent
CLIENT = ROOT / "tests" / "golden" / "react" / "order-portal"
API = ROOT / "tests" / "golden" / "fastapi" / "order-portal" / "services" / "order-api"
DOCUMENT = API / "openapi.gen.json"
ENTITY_MODEL = "src/entities/order/model/order.gen.ts"
PLACE_ORDER = "src/features/place-order/api/place-order.gen.ts"

type Document = dict[str, Any]


@pytest.fixture(scope="module")
def document() -> Document:
    return json.loads(DOCUMENT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client() -> dict[str, str]:
    return read_client(CLIENT)


def contract_differences(client: dict[str, str], document: Document) -> list[str]:
    return compare(client_operations(client), openapi_operations(document))


# trace: PRD-APP-005, PRD-APP-211
def test_client_agrees_with_openapi_gen_json(client: dict[str, str], document: Document) -> None:
    assert contract_differences(client, document) == []


# trace: PRD-APP-005
def test_client_sends_each_operation_of_the_api(client: dict[str, str], document: Document) -> None:
    """The test finds each operation of the client, thus the comparison is not empty."""
    ours = sorted(operation.label() for operation in client_operations(client))
    theirs = sorted(operation.label() for operation in openapi_operations(document))
    assert ours == [
        "GET /orders",
        "GET /orders/{}",
        "POST /orders",
        "POST /orders/place",
        "POST /orders/{}/cancel",
    ]
    assert sorted(set(theirs) - set(ours)) == ["GET /healthz"]


def _rename_path(data: Document) -> None:
    paths = data["paths"]
    paths["/orders/{orderId}/cancellation"] = paths.pop("/orders/{orderId}/cancel")


def _change_method(data: Document) -> None:
    item = data["paths"]["/orders/place"]
    item["put"] = item.pop("post")


def _change_max_length(data: Document) -> None:
    data["components"]["schemas"]["CreateOrderInput"]["properties"]["note"]["anyOf"][0][
        "maxLength"
    ] = 400


def _change_minimum(data: Document) -> None:
    total = data["components"]["schemas"]["CreateOrderInput"]["properties"]["total"]
    total["anyOf"][0]["minimum"] = 1


def _change_type(data: Document) -> None:
    data["components"]["schemas"]["ReadOrderOutput"]["properties"]["total"]["type"] = "number"


def _make_optional(data: Document) -> None:
    data["components"]["schemas"]["CreateOrderInput"]["required"] = ["total"]


def _add_value(data: Document) -> None:
    status = data["components"]["schemas"]["ListOrderOutput"]["properties"]["status"]
    status["enum"].append("returned")


def _add_field(data: Document) -> None:
    data["components"]["schemas"]["CancelOrderOutput"]["properties"]["reason"] = {"type": "string"}


def _change_path_parameter(data: Document) -> None:
    parameter = data["paths"]["/orders/{orderId}/cancel"]["post"]["parameters"][0]
    parameter["schema"]["type"] = "integer"
    del parameter["schema"]["format"]


def _change_default(data: Document) -> None:
    data["paths"]["/orders"]["get"]["parameters"][0]["schema"]["default"] = 20


def _allow_other_fields(data: Document) -> None:
    del data["components"]["schemas"]["PlaceOrderBody"]["additionalProperties"]


NEGATIVE_CASES: dict[str, tuple[Callable[[Document], None], list[str]]] = {
    "changed path": (
        _rename_path,
        [
            "POST /orders/{}/cancel: the OpenAPI document has no such operation. The React "
            "client sends it in src/features/cancel-order/api/cancel-order.gen.ts (cancelOrder)."
        ],
    ),
    "changed method": (
        _change_method,
        [
            "POST /orders/place: the OpenAPI document has no such operation. The React "
            "client sends it in src/features/place-order/api/place-order.gen.ts (placeOrder)."
        ],
    ),
    "changed maxLength": (
        _change_max_length,
        [
            "POST /orders request body properties note maxLength: the React client has 500. "
            "The OpenAPI document has 400."
        ],
    ),
    "changed minimum": (
        _change_minimum,
        [
            "POST /orders request body properties total minimum: the React client has 0. "
            "The OpenAPI document has 1."
        ],
    ),
    "changed type": (
        _change_type,
        [
            "GET /orders/{} response properties total type: the React client has 'string'. "
            "The OpenAPI document has 'number'."
        ],
    ),
    "changed optional state": (
        _make_optional,
        [
            "POST /orders request body required: the React client has ['status', 'total']. "
            "The OpenAPI document has ['total']."
        ],
    ),
    "changed enumeration": (
        _add_value,
        [
            "GET /orders response properties items items properties status enum: the React "
            "client has ['cancelled', 'open', 'shipped']. The OpenAPI document has "
            "['cancelled', 'open', 'returned', 'shipped']."
        ],
    ),
    "added field": (
        _add_field,
        [
            "POST /orders/{}/cancel response properties: the OpenAPI document has reason = "
            "{'type': 'string'}. The React client does not have it."
        ],
    ),
    "changed path parameter": (
        _change_path_parameter,
        [
            "POST /orders/{}/cancel path parameter 1 schema: the React client has "
            "format = 'uuid'. The OpenAPI document does not have it.",
            "POST /orders/{}/cancel path parameter 1 schema type: the React client has "
            "'string'. The OpenAPI document has 'integer'.",
        ],
    ),
    "changed default": (
        _change_default,
        ["GET /orders query limit default: the React client has 50. The OpenAPI document has 20."],
    ),
    "other fields": (
        _allow_other_fields,
        [
            "POST /orders/place request body strict: the React client has True. "
            "The OpenAPI document has False."
        ],
    ),
}


# trace: PRD-APP-005, PRD-APP-211
@pytest.mark.parametrize("case", sorted(NEGATIVE_CASES))
def test_changed_openapi_document_gives_a_difference(
    case: str, client: dict[str, str], document: Document
) -> None:
    change, expected = NEGATIVE_CASES[case]
    changed = copy.deepcopy(document)
    change(changed)
    assert contract_differences(client, changed) == expected


# trace: PRD-APP-005, PRD-APP-211
def test_changed_zod_rule_gives_a_difference(client: dict[str, str], document: Document) -> None:
    text = client[ENTITY_MODEL]
    assert text.count(".max(500)") == 1
    changed = client | {ENTITY_MODEL: text.replace(".max(500)", ".max(400)")}
    assert contract_differences(changed, document) == [
        "POST /orders request body properties note maxLength: the React client has 400. "
        "The OpenAPI document has 500."
    ]


# trace: PRD-APP-005
def test_unsent_input_field_gives_a_difference(client: dict[str, str], document: Document) -> None:
    text = client[PLACE_ORDER]
    body = "body: {\n      total: data.total,\n    },"
    assert text.count(body) == 1
    changed = client | {PLACE_ORDER: text.replace(body, "body: {},")}
    assert contract_differences(changed, document) == [
        "POST /orders/place: the React client does not send the input field 'total'.",
        "POST /orders/place request body properties: the OpenAPI document has total = "
        "{'type': 'decimal'}. The React client does not have it.",
        "POST /orders/place request body required: the React client has []. "
        "The OpenAPI document has ['total'].",
    ]


def test_unknown_zod_function_stops_the_test(client: dict[str, str]) -> None:
    """A new form of the generated code cannot pass with no comparison."""
    text = client[ENTITY_MODEL]
    changed = client | {ENTITY_MODEL: text.replace("z.guid()", "z.cuid()", 1)}
    with pytest.raises(ContractError, match=r"z\.cuid"):
        client_operations(changed)


def test_unknown_openapi_keyword_stops_the_test(document: Document) -> None:
    """A new form of the OpenAPI document cannot pass with no comparison."""
    changed = copy.deepcopy(document)
    changed["components"]["schemas"]["ReadOrderOutput"]["properties"]["total"]["const"] = "1"
    with pytest.raises(ContractError, match="'const'"):
        openapi_operations(changed)
