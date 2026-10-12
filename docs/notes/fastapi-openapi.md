# FastAPI generator: the OpenAPI document

Story #90 added the OpenAPI document `openapi.gen.json` to the FastAPI generator (PRD-APP-004, Q18). The module `src/dsml/generate/fastapi_openapi.py` writes it from the IR. The document is in the output folder of the application.

## Content

- `openapi` is `3.1.0`. `info` has the name of the application and the version of the project.
- `paths` has `GET /healthz` and one operation for each CRUD slice and each custom slice: the method, the path, the parameters, the request body and the responses.
- `components.schemas` has the Pydantic schemas of the slices, `Health` and `Problem`.
- `components.securitySchemes` has `HTTPBearer`, the Cognito access token. An operation that is not public has `security`. A public operation has no `security`.
- Each error response has the media type `application/problem+json` and the schema `Problem`.

## Error responses

The endpoint declares its error responses with `responses=problem_responses(...)` of `app/shared/errors_gen.py`. The model gives these statuses:

| Status | Operations |
| --- | --- |
| 401, 403 | An operation that is not public (PRD-APP-008). |
| 404 | A CRUD operation with the key in the path: `read`, `update` and `delete` (PRD-APP-113). |
| 409 | A CRUD operation that writes: `create`, `update` and `delete`. A `unique` rule or a relation can stop the change (PRD-APP-113). |
| 422 | A CRUD operation, and a custom operation with an `in` parameter (PRD-APP-113). |

A hand-written handler of a custom operation can return other statuses. The model does not give them, thus the document does not show them.

FastAPI adds the response 422 with its own schema `HTTPValidationError` if the route does not declare 422. The application returns problem details, thus each endpoint with an input declares 422.

## Agreement with the running application

FastAPI makes the OpenAPI document of the application from the routes and the Pydantic models. `register_error_handlers` adds the schema `Problem` to that document. The test `test_openapi_document_agrees_with_openapi_gen_json` in `tests/test_app_gen.py` of the generated project gets `GET /openapi.json` and compares the parsed JSON with `openapi.gen.json`. The CI job "FastAPI golden project" runs this test for each golden project.

Thus the generator writes each value as FastAPI and Pydantic write it:

- The title of a field or of a parameter is its name in title case: `vip_total` gives `Vip Total`, and `orderId` gives `Orderid`.
- The description of a schema is the docstring of its class. The description of an operation is the docstring of the endpoint function. The slice classes give these texts to the templates and to the OpenAPI writer.
- The summary is the name of the endpoint function in title case. The operation ID is the name of the function, the path and the method.
- A decimal in an input is a number or a text. The field rules apply to the number. A decimal in an output is a text.
- A schema has no default value `null`, because FastAPI removes it.

The comparison of parsed JSON ignores the order of the keys. FastAPI writes a minimum or a maximum as a real number, for example `0.0`. The generator writes the value of the model, for example `0`. The parsed values are equal.

## Determinism

The file is canonical JSON: sorted keys, two spaces of indent, UTF-8, LF line ends and one LF at the end (PRD-CORE-028, PRD-CORE-034). The order of a list is the order of the fields or of the parameters in the generated code, because the two documents must agree (PRD-CORE-031).

## Tests

- `tests/test_fastapi_openapi.py` validates the golden documents against the OpenAPI 3.1 schema in `tests/schemas/`. It also examines the paths, the schemas, the security scheme and the error responses.
- The golden files `tests/golden/fastapi/*/services/*/openapi.gen.json` are the output for the example model and for the shop model.
