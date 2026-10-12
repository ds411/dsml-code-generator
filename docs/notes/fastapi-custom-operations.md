# FastAPI generator: custom operations

Story #88 added the custom operations to the FastAPI generator (phase 1). Each custom operation is one vertical slice. The generated endpoint calls a typed `handle` function in a hand-written `handler.py`. The generator writes `handler.py` one time as a stub (Q15, Q55).

- Slices: `src/dsml/generate/fastapi_operations.py`. The methods and the paths come from `src/dsml/ir/operations.py` (PRD-APP-110).
- Templates: `src/dsml/templates/fastapi/operations/` and `src/dsml/templates/fastapi/tests/test_operation_http_gen.py.j2`.
- Tests: `tests/test_fastapi_operations.py`.
- Golden files: the slice `cancel_order` of the example model in `tests/golden/fastapi/order-service/`, and four slices of the test model `tests/models/fastapi/shop.sysml` in `tests/golden/fastapi/shop/`. Write them again with `uv run python scripts/write_golden_fastapi.py`.
- CI: the job "FastAPI golden project" runs ruff, pyright and the HTTP tests of each golden project. Its last step shows the type check error of PRD-CORE-045.

## Output

For each custom operation of an application, the generator writes the folder `app/features/<entity>/<operation>/`, for example `app/features/order/cancel_order/` (PRD-APP-102). The name of the slice is the name of the `#Exposed` element in snake case.

| File | Kind | Content | Requirements |
| --- | --- | --- | --- |
| `endpoint_gen.py` | Generated | The router with one endpoint. The endpoint validates the input, checks the roles, opens a database session and calls `handle(data, session, user)`. It returns the output of `handle` as the output schema. | PRD-APP-102, PRD-APP-110, PRD-APP-116 |
| `schemas_gen.py` | Generated | The input schema, the schema of the request body or of the query parameters, and the output schema. | PRD-APP-102, PRD-APP-116, PRD-CORE-045 |
| `handler.py` | Create-once | The typed `handle` function. The body of the stub raises `NotImplementedError`. | PRD-APP-103, PRD-APP-117, PRD-CORE-044 |
| `__init__.py` | Generated | The header only. | PRD-APP-134 |

The generator also writes `tests/test_<operation>_http_gen.py` for each custom operation. The tests send a request with no token (HTTP 401) and a request with no permitted role (HTTP 403). While `handle` is the stub, a third test expects HTTP 501. When a developer writes the logic, pytest skips that test.

`app/shared/errors_gen.py` changes `NotImplementedError` into HTTP 501 with problem details (PRD-APP-117).

## Map from the model to the schemas

- Each `in` parameter is a field of the input schema `<Operation>Input`. The JSON name is the parameter name in snake case.
- A parameter in the path of the operation is a path parameter. Its name must be a correct Python name, and its multiplicity must be `[1]`.
- For POST, PUT and PATCH, the other `in` parameters are the request body `<Operation>Body`. For GET and DELETE, they are the query parameters `<Operation>Query`. The endpoint makes the input schema from the path parameters and the body or the query parameters.
- A parameter that an entity types gives the key of the entity, not a nested object.
- A `[0..1]` parameter is optional. A parameter with an upper multiplicity of more than 1 is a list.
- If the operation has one `out` parameter and an entity types it, the output schema `<Operation>Output` has the fields of the entity. A `[*]` parameter of this kind gives a list of entities.
- If not, the output schema has one field for each `out` parameter.
- An operation with no `out` parameter returns HTTP 204 with no body.
- A public operation (`public = true`) needs no token. Then `handle` gets `None` as the user.

The entity folder is the table of the first entity of the `out` parameters, then of the `in` parameters. An operation with no entity gets a folder with the name of the operation, for example `app/features/count_customers/count_customers/`.

## Hand-written handler

The generator writes `handler.py` only if no file exists at its path (PRD-CORE-044). The manifest `.dsml/generated.json` lists it in `createOnce`. The trace manifest has no symbols of the file. The stub has the trace comment `# trace: <operation>` with the qualified name of the operation (PRD-TRACE-009).

The endpoint and the handler use the typed schemas (PRD-CORE-045). If the operation changes in the model, the generator writes the schemas again, but not the handler. Then a type check shows each place where the handler does not agree with the schemas. The CI step "Check the typed interface of a custom operation" shows this:

1. The step puts the hand-written handler `tests/golden/fastapi/handler-check/handler.py` into the golden project `order-api`. pyright must find no error.
2. The step puts the generated files of a changed model from `tests/golden/fastapi/handler-check/` into the project. In this model, the `in` parameter `orderId` has the new name `orderKey`.
3. pyright must find an error in `handler.py`.

The test `test_changed_model_gives_the_files_of_the_type_check` makes sure that the files of step 2 are the output of the generator for the changed model.

## Errors

These conditions stop `dsml generate` with an error:

- A path parameter that is not an `in` parameter, that is not a correct Python name, or that is not `[1]`.
- A parameter type that is not a scalar type, an enumeration or an entity with one key field.
- An `inout` parameter.
- A custom operation in an application with no entity. The endpoint opens a database session, thus the application needs a database.
- A custom operation with the slice folder of an other operation.
- Two enumerations with one type alias name in the schemas of one operation.
