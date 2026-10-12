# FastAPI generator: CRUD slices

Story #84 added the CRUD slices to the FastAPI generator (phase 1). Each CRUD operation of an exposed entity is one vertical slice with an endpoint, the Pydantic schemas and a handler. Story #88 added the custom operations (see `docs/notes/fastapi-custom-operations.md`).

- Slices: `src/dsml/generate/fastapi_slices.py`. The methods and the paths come from `src/dsml/ir/operations.py`, the module that the rule STR-009 also uses (PRD-APP-110).
- Test values: `src/dsml/generate/fastapi_examples.py`.
- Templates: `src/dsml/templates/fastapi/slices/`, `src/dsml/templates/fastapi/db/commit_gen.py.j2` and `src/dsml/templates/fastapi/tests/`.
- Tests: `tests/test_fastapi_slices.py`.
- Golden files: `tests/golden/fastapi/order-service/` (the example model) and `tests/golden/fastapi/shop/` (the test model `tests/models/fastapi/shop.sysml`). Write them again with `uv run python scripts/write_golden_fastapi.py`.
- CI: the job "FastAPI golden project" runs the HTTP tests of each golden project against PostgreSQL 18.

## Output

For each CRUD operation of each `#Exposed` entity, the generator writes the folder `app/features/<entity>/<operation>_<entity>/`, for example `app/features/order/create_order/` (PRD-APP-102, Q37, AD3).

| File | Content | Requirements |
| --- | --- | --- |
| `endpoint_gen.py` | The router with one endpoint. The endpoint checks the token and the roles, validates the input and calls the handler. | PRD-APP-008, PRD-APP-102, PRD-APP-110 |
| `schemas_gen.py` | The Pydantic v2 models of the operation. | PRD-APP-102, PRD-APP-111, PRD-APP-112, PRD-APP-115 |
| `handler_gen.py` | The handler that reads or writes the database. | PRD-APP-103, PRD-APP-113, PRD-APP-114 |
| `__init__.py` | The header only. | PRD-APP-134 |

The generator also writes these files if the application has one or more CRUD operations or custom operations:

| File | Content | Requirements |
| --- | --- | --- |
| `app/shared/db/commit_gen.py` | The function `commit`. It changes the database errors into problem details. | PRD-APP-104, PRD-APP-113 |
| `tests/http_support_gen.py` | The database, the tokens and the client of the HTTP tests. | PRD-APP-135 |
| `tests/test_<exposed>_http_gen.py` | The HTTP tests of the CRUD operations of one exposed entity, for example `tests/test_orders_http_gen.py`. | PRD-APP-008, PRD-APP-110 to PRD-APP-115 |

`app/main_gen.py` registers the router of each slice after `GET /healthz`, in the sorted order of the slice packages (PRD-APP-105).

The header of a slice file and of a test file gives the `#Exposed` element and the entity. The endpoint file gives one `route` symbol for its endpoint, for example `POST /orders` (PRD-TRACE-006).

## Imports

A file of a slice imports only from its own slice and from `app/shared/` (PRD-APP-106). Thus each slice has its own schemas. The schema class names start with the slice name, for example `CreateOrderInput` and `ReadOrderOutput`. Thus the OpenAPI document has no two schemas with the same name. The test `test_a_slice_file_imports_only_from_its_slice_and_from_app_shared` examines the imports of each golden slice file.

## Operations

| Operation | Method and default path | Success | Errors |
| --- | --- | --- | --- |
| `create` | `POST /<entities>` | 201 with the new entity | 401, 403, 409, 422 |
| `read` | `GET /<entities>/{id}` | 200 with the entity | 401, 403, 404, 422 |
| `update` | `PATCH /<entities>/{id}` | 200 with the changed entity | 401, 403, 404, 409, 422 |
| `delete` | `DELETE /<entities>/{id}` | 204 with no body | 401, 403, 404, 409 |
| `list` | `GET /<entities>?limit=&offset=` | 200 with `items` and `total` | 401, 403, 422 |

- `<entities>` is the name of the `#Exposed` element, for example `orders`. If the model gives a different method or path, the IR has it, and the slice uses it (PRD-APP-110).
- The path of `read`, `update` and `delete` must have one path parameter for the key. The parameter name must be a Python name. If not, `dsml generate` stops with an error.
- An operation with `public = true` has no token check. Each other operation uses `require_roles(*ALLOWED_ROLES)`. `ALLOWED_ROLES` holds the values of `allowedRoles`, sorted (PRD-APP-008).
- `list` accepts `limit` (1 to 200, default 50) and `offset` (0 or more, default 0). It sorts the entities by key and gives the number of all entities in `total` (PRD-APP-114).
- `delete` gives HTTP 409 if other entities refer to the entity.

## Schemas

The fields of the schemas are the columns of the table of the entity, in the order of the column names. Thus a `[0..1]` or `[1]` relation is its foreign key column, for example `supplier_id` (PRD-APP-115).

- The create input has no key field (PRD-APP-111). It has `extra="forbid"`, thus a request with the key gets HTTP 422.
- The handler of `create` makes a random UUID for a `Uuid` key. The database makes an `Integer` key. A `create` operation of an entity with a key of a different type stops `dsml generate` with an error.
- Each field of the update input is optional. A field that is not in the body does not change. The value null for a field that the entity must have gets HTTP 422.
- The output schema has all fields. A nullable column gives `<type> | None`.
- An enumeration field has a type alias, for example `StatusValue = Literal["open", "shipped", "cancelled"]`.
- A field with the name of a Python keyword has an alias, for example `class_` with the JSON name `class`.

The field rules become `Field` constraints (PRD-APP-112):

| Field rule | Constraint |
| --- | --- |
| `minLength`, `maxLength` | `min_length`, `max_length` |
| `minValue`, `maxValue` | `ge`, `le` |
| `pattern` | `pattern` |
| `precision`, `scale` of `Decimal` | `max_digits`, `decimal_places` |

Pydantic examines `pattern` with a search, not a full match. Thus a pattern must have `^` and `$` to examine the full text.

## Database errors

The handlers call `commit` from `app/shared/db/commit_gen.py` (PRD-APP-113):

- A value that breaks a `unique` rule gives HTTP 409. The model of the entity has `unique=True` on the column of a field with `unique = true`.
- A foreign key to an entity that does not exist gives HTTP 422. The delete of an entity that other entities refer to gives HTTP 409.
- A value that the database cannot keep gives HTTP 422.

The schema snapshot and the migrations do not have the `UNIQUE` constraints yet. The tables of the HTTP tests come from `Base.metadata.create_all`, thus they have the constraints.

## HTTP tests

The generator writes HTTP tests for each exposed entity with CRUD operations. They show the success responses of the CRUD table and the status codes 401, 403, 404, 409 and 422.

- The tests use a PostgreSQL database. They read the database variables of the configuration, for example `DATABASE_HOST`. If `DATABASE_HOST` is not set, the tests do not run. Thus `pytest` operates in a project with no database (PRD-APP-135).
- The first test makes the tables with `Base.metadata.create_all`. Each test deletes all rows, then adds its rows with SQL.
- The tests sign the tokens with a local key pair and give a local JWKS. They do not use the network.
- The generator makes the test values from the type and the field rules of each field, with no random value. It makes three rows with different values, a row for each entity that a required relation refers to, and one value that breaks each field rule.
- For a `pattern` rule, the generator makes a text from the regular expression. It knows literal characters, character classes, `.`, `\d`, `\w`, `\s`, groups, alternatives, anchors and the quantifiers `?`, `*`, `+` and `{m,n}`. If it cannot make a value, the test file tells why and does not run.

The CI job "FastAPI golden project" starts a PostgreSQL 18 service container and runs the HTTP tests of each golden project. The job fails if a test does not run.
