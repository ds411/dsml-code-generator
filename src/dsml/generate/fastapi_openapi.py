# trace: PRD-APP-004, PRD-CORE-028, PRD-CORE-031, PRD-CORE-034
"""The OpenAPI document of the FastAPI generator: `openapi.gen.json`.

The generator writes the OpenAPI 3.1 document of an application from the
IR (PRD-APP-004, Q18). The document has the paths and the methods of the
operations, the schemas of the slices, the security scheme of the Cognito
access token and the problem details responses.

The generated application makes its own OpenAPI document from its routes
and its Pydantic models. The test `tests/test_app_gen.py` of the generated
project compares the parsed JSON of the two documents. Thus this module
writes each value as FastAPI and Pydantic write it:

- The title of a field is its name in title case, for example `Vip Total`.
- The title of a parameter is its name in title case, for example `Orderid`.
- The description of a schema is the docstring of its class. The
  description of an operation is the docstring of its endpoint function.
- The ID of an operation comes from the name of the endpoint function, the
  path and the method.
- A schema has no default value `null`, because FastAPI removes it.

The order of a list follows the order of the fields and of the parameters
in the generated code, because the two documents must agree. The JSON
objects have sorted keys (PRD-CORE-028, PRD-CORE-031).
"""

import re
from collections.abc import Sequence
from typing import Final, cast

from dsml.generate.fastapi_operations import CustomSlice, ParameterField
from dsml.generate.fastapi_slices import LIMIT_DEFAULT, LIMIT_MAX, SchemaField, Slice
from dsml.ir.writer import JsonValue, canonical_json

OPENAPI_PATH: Final = "openapi.gen.json"
"""The path of the OpenAPI document in the output folder of the application."""

OPENAPI_VERSION: Final = "3.1.0"
"""The version of the OpenAPI specification of the document."""

SECURITY_SCHEME: Final = "HTTPBearer"
"""The name of the security scheme of the Cognito access token."""

PROBLEM_MEDIA_TYPE: Final = "application/problem+json"
"""The media type of problem details (RFC 9457)."""

PROBLEM_REFERENCE: Final = "#/components/schemas/Problem"

PROBLEM_SCHEMA: Final[dict[str, object]] = {
    "description": "An API error as problem details (RFC 9457).",
    "properties": {
        "detail": {"type": "string"},
        "errors": {
            "items": {
                "properties": {
                    "location": {"items": {"type": "string"}, "type": "array"},
                    "message": {"type": "string"},
                    "type": {"type": "string"},
                },
                "required": ["location", "message", "type"],
                "type": "object",
            },
            "type": "array",
        },
        "status": {"type": "integer"},
        "title": {"type": "string"},
        "type": {"type": "string"},
    },
    "required": ["status", "title", "type"],
    "title": "Problem",
    "type": "object",
}
"""The schema `Problem`. The template `errors_gen.py.j2` has the same schema."""

STATUS_PHRASES: Final = {
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Unprocessable Content",
}
"""The phrase of each error status of an endpoint (`http.HTTPStatus` of Python 3.14)."""

SUCCESS: Final = "Successful Response"
"""The description of the success response of an endpoint."""

_HEALTH_SCHEMA: Final[dict[str, object]] = {
    "description": "The response of `GET /healthz`.",
    "properties": {"status": {"title": "Status", "type": "string"}},
    "required": ["status"],
    "title": "Health",
    "type": "object",
}

_HEALTH_PATH: Final[dict[str, object]] = {
    "get": {
        "description": "Tell that the process operates. The route needs no token.",
        "operationId": "healthz_healthz_get",
        "responses": {
            "200": {
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/Health"}}
                },
                "description": SUCCESS,
            }
        },
        "summary": "Healthz",
        "tags": ["health"],
    }
}

_SCALARS: Final[dict[str, dict[str, object]]] = {
    "Boolean": {"type": "boolean"},
    "Date": {"format": "date", "type": "string"},
    "DateTime": {"format": "date-time", "type": "string"},
    "Integer": {"type": "integer"},
    "Real": {"type": "number"},
    "String": {"type": "string"},
    "Uuid": {"format": "uuid", "type": "string"},
}
"""The JSON schema of each DSML scalar type, except `Decimal`."""

_NOT_WORD: Final = re.compile(r"\W")

type Json = dict[str, object]


# trace: PRD-APP-004, PRD-CORE-028, PRD-CORE-034
def openapi_file(application: str, version: str, routers: Sequence[Slice | CustomSlice]) -> bytes:
    """Give the bytes of `openapi.gen.json`: canonical JSON with sorted keys."""
    return canonical_json(cast(JsonValue, openapi_document(application, version, routers)))


# trace: PRD-APP-004, PRD-APP-008, PRD-APP-014, PRD-APP-110
def openapi_document(
    application: str, version: str, routers: Sequence[Slice | CustomSlice]
) -> Json:
    """Give the OpenAPI document of an application with its slices."""
    paths: dict[str, Json] = {"/healthz": dict(_HEALTH_PATH)}
    schemas: dict[str, object] = {"Health": _HEALTH_SCHEMA, "Problem": PROBLEM_SCHEMA}
    secured = False
    for item in routers:
        if isinstance(item, Slice):
            operation = _crud_operation(item, schemas)
        else:
            operation = _custom_operation(item, schemas)
        if not item.public:
            operation["security"] = [{SECURITY_SCHEME: []}]
            secured = True
        paths.setdefault(item.path, {})[item.method] = operation
    components: Json = {"schemas": schemas}
    if secured:
        components["securitySchemes"] = {
            SECURITY_SCHEME: {
                "description": "The Cognito access token.",
                "scheme": "bearer",
                "type": "http",
            }
        }
    return {
        "components": components,
        "info": {"title": application, "version": version},
        "openapi": OPENAPI_VERSION,
        "paths": paths,
    }


def _crud_operation(item: Slice, schemas: dict[str, object]) -> Json:
    parameters: list[Json] = []
    if item.parameter is not None:
        parameters.append(_path_parameter(item.parameter, item.key.rules.kind, ()))
    if item.operation == "list":
        parameters.append(_limit_parameter("limit", LIMIT_DEFAULT, 1, LIMIT_MAX))
        parameters.append(_limit_parameter("offset", 0, 0, None))
    body: str | None = None
    if item.input_class is not None:
        optional = item.operation == "update"
        schemas[item.input_class] = _object_schema(
            item.input_class,
            item.input_doc,
            [_input_field(field, optional) for field in item.input_fields],
            forbid=True,
        )
        body = item.input_class
    result: Json | None = None
    status = "200"
    if item.output_class is not None:
        schemas[item.output_class] = _object_schema(
            item.output_class,
            item.output_doc,
            [_output_field(field) for field in item.fields],
        )
        result = _reference(item.output_class)
    if item.page_class is not None and item.output_class is not None:
        schemas[item.page_class] = _object_schema(
            item.page_class,
            item.page_doc,
            [
                ("items", _titled("items", _array(_reference(item.output_class))), True),
                ("total", _titled("total", {"type": "integer"}), True),
            ],
        )
        result = _reference(item.page_class)
    if item.operation == "create":
        status = "201"
    if item.operation == "delete":
        status = "204"
    return _operation(item, item.endpoint_doc, parameters, body, status, result)


def _custom_operation(item: CustomSlice, schemas: dict[str, object]) -> Json:
    parameters = [
        _path_parameter(field.name, field.rules.kind, field.rules.values)
        for field in item.path_fields
    ]
    body: str | None = None
    if item.request_class is not None:
        fields = [_parameter_field(field, "validation") for field in item.request_fields]
        if item.has_body:
            schemas[item.request_class] = _object_schema(
                item.request_class, item.request_doc, fields, forbid=True
            )
            body = item.request_class
        else:
            parameters.extend(
                {"in": "query", "name": name, "required": required, "schema": schema}
                for name, schema, required in fields
            )
    result: Json | None = None
    status = "204"
    if item.output_class is not None:
        status = "200"
        if item.entity_output is not None:
            fields = [_output_field(field) for field in item.entity_output]
        else:
            fields = [_parameter_field(field, "serialization") for field in item.outputs]
        schemas[item.output_class] = _object_schema(item.output_class, item.output_doc, fields)
        result = _reference(item.output_class)
        title = _title(f"Response_{_operation_id(item)}")
        if item.entity_many:
            result = {**_array(result), "title": title}
        elif item.entity_optional:
            result = {"anyOf": [result, {"type": "null"}], "title": title}
    return _operation(item, item.endpoint_doc, parameters, body, status, result)


def _operation(
    item: Slice | CustomSlice,
    description: str,
    parameters: list[Json],
    body: str | None,
    status: str,
    result: Json | None,
) -> Json:
    success: Json = {"description": SUCCESS}
    if result is not None:
        success["content"] = {"application/json": {"schema": result}}
    responses: Json = {status: success}
    for problem in item.problem_statuses:
        responses[str(problem)] = {
            "content": {PROBLEM_MEDIA_TYPE: {"schema": {"$ref": PROBLEM_REFERENCE}}},
            "description": STATUS_PHRASES[problem],
        }
    operation: Json = {
        "description": description,
        "operationId": _operation_id(item),
        "responses": responses,
        "summary": _summary(item.name),
        "tags": [item.collection],
    }
    if parameters:
        operation["parameters"] = parameters
    if body is not None:
        operation["requestBody"] = {
            "content": {"application/json": {"schema": _reference(body)}},
            "required": True,
        }
    return operation


def _operation_id(item: Slice | CustomSlice) -> str:
    """Give the operation ID that FastAPI gives: the function name, the path and the method."""
    return f"{_NOT_WORD.sub('_', f'{item.name}{item.path}')}_{item.method}"


def _summary(name: str) -> str:
    """Give the summary that FastAPI gives: the function name in title case."""
    return name.replace("_", " ").title()


def _title(name: str) -> str:
    """Give the title of a field or of a parameter as Pydantic gives it."""
    return name.title().replace("_", " ").strip()


def _titled(name: str, schema: Json) -> Json:
    return {**schema, "title": _title(name)}


def _reference(name: str) -> Json:
    return {"$ref": f"#/components/schemas/{name}"}


def _array(items: Json) -> Json:
    return {"items": items, "type": "array"}


def _object_schema(
    name: str,
    description: str,
    fields: Sequence[tuple[str, Json, bool]],
    forbid: bool = False,
) -> Json:
    """Give the schema of a Pydantic model: its fields are (name, schema, required)."""
    schema: Json = {
        "description": description,
        "properties": {field: value for field, value, _ in fields},
        "title": name,
        "type": "object",
    }
    required = [field for field, _, mandatory in fields if mandatory]
    if required:
        schema["required"] = required
    if forbid:
        schema["additionalProperties"] = False
    return schema


def _value_schema(kind: str, values: Sequence[str], mode: str) -> Json:
    """Give the schema of one value of a DSML type in the validation or serialization mode."""
    if kind == "Decimal":
        if mode == "serialization":
            return {"type": "string"}
        return {"anyOf": [{"type": "number"}, {"type": "string"}]}
    if kind == "Enumeration":
        if len(values) == 1:
            return {"const": values[0], "type": "string"}
        return {"enum": list(values), "type": "string"}
    return dict(_SCALARS[kind])


def _nullable(schema: Json) -> Json:
    alternatives = schema.get("anyOf")
    if isinstance(alternatives, list):
        return {"anyOf": [*alternatives, {"type": "null"}]}
    return {"anyOf": [schema, {"type": "null"}]}


def _input_field(field: SchemaField, optional: bool) -> tuple[str, Json, bool]:
    """Give the schema of a field of an input schema, with the field rules (PRD-APP-112)."""
    rules = field.rules
    limits: Json = {}
    if rules.min_length is not None:
        limits["minLength"] = rules.min_length
    if rules.max_length is not None:
        limits["maxLength"] = rules.max_length
    if rules.min_value is not None:
        limits["minimum"] = rules.min_value
    if rules.max_value is not None:
        limits["maximum"] = rules.max_value
    if rules.pattern is not None:
        limits["pattern"] = rules.pattern
    if rules.kind == "Decimal":
        # Pydantic puts the limits of a decimal on the number, not on the text.
        schema: Json = {"anyOf": [{"type": "number", **limits}, {"type": "string"}]}
    else:
        schema = {**_value_schema(rules.kind, rules.values, "validation"), **limits}
    nullable = optional or field.nullable
    if nullable:
        schema = _nullable(schema)
    return field.name, _titled(field.name, schema), not nullable


def _output_field(field: SchemaField) -> tuple[str, Json, bool]:
    """Give the schema of a field of an output schema."""
    schema = _value_schema(field.rules.kind, field.rules.values, "serialization")
    if field.nullable:
        schema = _nullable(schema)
    return field.name, _titled(field.name, schema), True


def _parameter_field(field: ParameterField, mode: str) -> tuple[str, Json, bool]:
    """Give the schema of a field of a custom operation schema."""
    schema = _value_schema(field.rules.kind, field.rules.values, mode)
    required = True
    if field.many:
        schema = _array(schema)
        if field.lower > 0:
            schema["minItems"] = field.lower
        if field.upper is not None:
            schema["maxItems"] = field.upper
        if field.lower == 0:
            schema["default"] = []
            required = False
    elif field.optional:
        schema = _nullable(schema)
        required = False
    return field.json_name, _titled(field.json_name, schema), required


def _path_parameter(name: str, kind: str, values: Sequence[str]) -> Json:
    return {
        "in": "path",
        "name": name,
        "required": True,
        "schema": _titled(name, _value_schema(kind, values, "validation")),
    }


def _limit_parameter(name: str, default: int, minimum: int, maximum: int | None) -> Json:
    schema: Json = {"default": default, "minimum": minimum, "type": "integer"}
    if maximum is not None:
        schema["maximum"] = maximum
    return {"in": "query", "name": name, "required": False, "schema": _titled(name, schema)}
