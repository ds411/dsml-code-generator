"""Give the operations of an OpenAPI 3.1 document in the form of `shapes.py`.

The document is the `openapi.gen.json` of the FastAPI generator. The
function knows the JSON Schema keywords that Pydantic writes for the
field types and the field rules of the DSML. An unknown keyword gives a
`ContractError`, thus a new form of the document cannot pass without a
comparison.
"""

import re
from typing import Any, Final

from contract.shapes import ContractError, Operation, Parameter, Shape

_METHODS: Final = ("get", "put", "post", "patch", "delete")

_IGNORED: Final = frozenset({"title", "description", "default"})
"""The keywords that do not change the JSON values of a field."""

_RULES: Final = {
    "string": ("minLength", "maxLength", "pattern"),
    "integer": ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"),
    "number": ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"),
    "boolean": (),
    "array": ("minItems", "maxItems"),
}
"""The field rules of each JSON type."""

_FORMATS: Final = frozenset({"uuid", "date", "date-time", "uri"})

_PARAMETER: Final = re.compile(r"\{[^}]+\}")


# trace: PRD-APP-004, PRD-APP-005
def openapi_operations(document: dict[str, Any]) -> list[Operation]:
    """Give each operation of the OpenAPI document."""
    schemas: dict[str, Any] = document.get("components", {}).get("schemas", {})
    operations: list[Operation] = []
    for path, item in sorted(document["paths"].items()):
        for method in _METHODS:
            if method in item:
                operations.append(_operation(path, method, item[method], schemas))
    return operations


def _operation(path: str, method: str, data: dict[str, Any], schemas: dict[str, Any]) -> Operation:
    parameters: dict[tuple[str, str], dict[str, Any]] = {
        (item["in"], item["name"]): item for item in data.get("parameters", [])
    }
    path_parameters = tuple(
        _parameter(parameters.pop(("path", name[1:-1])), schemas)
        for name in _PARAMETER.findall(path)
    )
    query = tuple(
        (name, _parameter(parameters.pop(("query", name)), schemas))
        for kind, name in sorted(parameters)
        if kind == "query"
    )
    if parameters:
        raise ContractError(f"The contract test does not know the parameters {sorted(parameters)}.")
    body = None
    if "requestBody" in data:
        body = schema_shape(_json_schema(data["requestBody"]["content"]), schemas)
    return Operation(
        method=method.upper(),
        path=_PARAMETER.sub("{}", path),
        source=f"{method.upper()} {path}",
        path_parameters=path_parameters,
        query_parameters=query,
        body=body,
        response=_response(data["responses"], schemas),
    )


def _parameter(data: dict[str, Any], schemas: dict[str, Any]) -> Parameter:
    result: Parameter = {
        "required": bool(data.get("required", False)),
        "schema": schema_shape(data["schema"], schemas),
    }
    if "default" in data["schema"]:
        result["default"] = data["schema"]["default"]
    return result


def _response(responses: dict[str, Any], schemas: dict[str, Any]) -> Shape | None:
    """Give the shape of the body of the one success response."""
    success = [status for status in responses if status.startswith("2")]
    if len(success) != 1:
        raise ContractError(f"The contract test expects one success response, not {success}.")
    content = responses[success[0]].get("content")
    return None if content is None else schema_shape(_json_schema(content), schemas)


def _json_schema(content: dict[str, Any]) -> dict[str, Any]:
    if set(content) != {"application/json"}:
        raise ContractError(f"The contract test expects JSON content, not {sorted(content)}.")
    return content["application/json"]["schema"]


# trace: PRD-APP-005, PRD-APP-211
def schema_shape(schema: dict[str, Any], schemas: dict[str, Any]) -> Shape:
    """Give the shape of a JSON Schema of the OpenAPI document."""
    if "$ref" in schema:
        name = schema["$ref"].removeprefix("#/components/schemas/")
        return schema_shape(schemas[name], schemas)
    if "anyOf" in schema:
        return _any_of(schema, schemas)
    kind = schema.get("type")
    if kind == "object":
        return _object(schema, schemas)
    if kind not in _RULES:
        raise ContractError(f"The contract test does not know the JSON Schema {schema!r}.")
    shape: Shape = {"type": kind}
    known = set(_RULES[kind]) | _IGNORED | {"type"}
    for key, value in schema.items():
        if key in _RULES[kind]:
            shape[key] = value
        elif kind == "string" and key == "format" and value in _FORMATS:
            shape["format"] = value
        elif kind == "string" and key == "enum":
            shape["enum"] = sorted(value)
        elif kind == "array" and key == "items":
            shape["items"] = schema_shape(value, schemas)
        elif key not in known:
            raise ContractError(
                f"The contract test does not know the keyword {key!r} in {schema!r}."
            )
    return shape


def _any_of(schema: dict[str, Any], schemas: dict[str, Any]) -> Shape:
    """Give the shape of `anyOf`: a nullable value, or a decimal value in a request.

    Pydantic gives a decimal value in a request as a number or a text. The
    field rules of the value are on the number.
    """
    unknown = set(schema) - _IGNORED - {"anyOf"}
    if unknown:
        raise ContractError(f"The contract test does not know the keywords {sorted(unknown)}.")
    branches: list[dict[str, Any]] = [item for item in schema["anyOf"] if item != {"type": "null"}]
    nullable = len(branches) < len(schema["anyOf"])
    kinds = sorted(str(item.get("type")) for item in branches)
    if len(branches) == 1:
        shape = schema_shape(branches[0], schemas)
    elif kinds == ["number", "string"]:
        number, text = sorted(branches, key=lambda item: str(item.get("type")))
        if set(text) - _IGNORED != {"type"}:
            raise ContractError(f"The contract test does not know the decimal text {text!r}.")
        shape = schema_shape(number, schemas) | {"type": "decimal"}
    else:
        raise ContractError(f"The contract test does not know the JSON Schema {schema!r}.")
    if nullable:
        shape["nullable"] = True
    return shape


def _object(schema: dict[str, Any], schemas: dict[str, Any]) -> Shape:
    unknown = set(schema) - _IGNORED - {"type", "properties", "required", "additionalProperties"}
    if unknown:
        raise ContractError(f"The contract test does not know the keywords {sorted(unknown)}.")
    extra = schema.get("additionalProperties", True)
    if extra not in (True, False):
        raise ContractError(f"The contract test does not know additionalProperties {extra!r}.")
    properties: dict[str, Any] = schema.get("properties", {})
    return {
        "type": "object",
        "properties": {name: schema_shape(value, schemas) for name, value in properties.items()},
        "required": sorted(schema.get("required", [])),
        "strict": extra is False,
    }
