"""The common form of the operations of both sides, and the comparison.

A shape is a dictionary that tells the JSON values of one field:

- `type`: `string`, `integer`, `number`, `boolean`, `decimal`, `array` or
  `object`. A decimal value in a request is a number or a text.
- `format`: `uuid`, `date`, `date-time` or `uri`, for a text.
- `enum`: the sorted values of an enumeration.
- The field rules: `minLength`, `maxLength`, `pattern`, `minimum`,
  `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `minItems` and
  `maxItems`.
- `nullable`: `True` if the value can be `null`.
- `items`: the shape of the items of an array.
- `properties`, `required` and `strict`: the fields of an object, the
  sorted names of the fields that must be in the object, and `True` if the
  object refuses other fields.

The React client gives some values with a TypeScript type and no Zod
schema, for example the parameters of a query. The shape of such a value
is `{"typescript": <type>}`. The client does not apply field rules to it,
thus the comparison examines only the type. The API applies the rules.
"""

from dataclasses import dataclass
from typing import Any, Final

type Shape = dict[str, Any]
"""The JSON values of one field."""

type Parameter = dict[str, Any]
"""One path or query parameter: `required`, `default` (if any) and `schema`."""

_TYPESCRIPT_TYPES: Final = {
    "boolean": ("boolean",),
    "number": ("integer", "number"),
    "string": ("string",),
}
"""The OpenAPI types that agree with each TypeScript type."""


class ContractError(Exception):
    """The contract test cannot read a file. The file has an unknown form."""


# trace: PRD-APP-005
@dataclass(frozen=True, slots=True)
class Operation:
    """One operation of an API, as one side of the contract gives it.

    `path` has `{}` in place of each path parameter. The path parameters
    are in the order of the path. `body` and `response` are `None` if the
    operation has no request body or no response body. `unsent` gives the
    fields of the input that the client does not send.
    """

    method: str
    path: str
    source: str
    path_parameters: tuple[Parameter, ...] = ()
    query_parameters: tuple[tuple[str, Parameter], ...] = ()
    body: Shape | None = None
    response: Shape | None = None
    unsent: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, str]:
        return (self.method, self.path)

    def label(self) -> str:
        return f"{self.method} {self.path}"


# trace: PRD-APP-005, PRD-APP-211
def compare(client: list[Operation], api: list[Operation]) -> list[str]:
    """Give each difference between the operations of the client and of the API.

    Each operation of the client must be an operation of the API. The API
    can have more operations, for example `GET /healthz`. An empty list
    tells that the two sides agree.
    """
    found = {operation.key: operation for operation in api}
    messages: list[str] = []
    for operation in sorted(client, key=lambda item: item.key):
        other = found.get(operation.key)
        if other is None:
            messages.append(
                f"{operation.label()}: the OpenAPI document has no such operation. "
                f"The React client sends it in {operation.source}."
            )
            continue
        messages.extend(_operation_differences(operation, other))
    return messages


def _operation_differences(client: Operation, api: Operation) -> list[str]:
    where = client.label()
    messages = [
        f"{where}: the React client does not send the input field {name!r}."
        for name in client.unsent
    ]
    for number, (ours, theirs) in enumerate(
        zip(client.path_parameters, api.path_parameters, strict=True), start=1
    ):
        messages.extend(differences(ours, theirs, f"{where} path parameter {number}"))
    messages.extend(
        differences(dict(client.query_parameters), dict(api.query_parameters), f"{where} query")
    )
    messages.extend(differences(client.body, api.body, f"{where} request body"))
    messages.extend(differences(client.response, api.response, f"{where} response"))
    return messages


# trace: PRD-APP-005, PRD-APP-211
def differences(client: object, api: object, where: str) -> list[str]:
    """Give each difference between a value of the client and a value of the API."""
    if isinstance(client, dict) and "typescript" in client:
        return _typescript_differences(str(client["typescript"]), api, where)  # pyright: ignore[reportUnknownArgumentType]
    if isinstance(client, dict) and isinstance(api, dict):
        ours: dict[str, object] = client  # pyright: ignore[reportUnknownVariableType]
        theirs: dict[str, object] = api  # pyright: ignore[reportUnknownVariableType]
        messages: list[str] = []
        for key in sorted(ours.keys() | theirs.keys()):
            if key not in theirs:
                messages.append(
                    f"{where}: the React client has {key} = {ours[key]!r}. "
                    "The OpenAPI document does not have it."
                )
            elif key not in ours:
                messages.append(
                    f"{where}: the OpenAPI document has {key} = {theirs[key]!r}. "
                    "The React client does not have it."
                )
            else:
                messages.extend(differences(ours[key], theirs[key], f"{where} {key}"))
        return messages
    if client != api or isinstance(client, bool) != isinstance(api, bool):
        return [f"{where}: the React client has {client!r}. The OpenAPI document has {api!r}."]
    return []


def _typescript_differences(name: str, api: object, where: str) -> list[str]:
    allowed = _TYPESCRIPT_TYPES.get(name)
    if allowed is None:
        raise ContractError(f"The contract test does not know the TypeScript type {name!r}.")
    if isinstance(api, dict) and api.get("type") in allowed:  # pyright: ignore[reportUnknownMemberType]
        return []
    return [
        f"{where}: the React client has the TypeScript type {name!r}. "
        f"The OpenAPI document has {api!r}."
    ]
