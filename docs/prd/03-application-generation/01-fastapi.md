# FastAPI target (phase 1)

## Stack and vertical slice layout

Each operation is one vertical slice. Code that all slices use is in `app/shared/`.

```text
app/
├── main_gen.py                       # creates the app, registers slice routers
├── migrate_gen.py                    # applies the migrations
├── features/order/
│   ├── create_order/                 # CRUD operation
│   │   ├── endpoint_gen.py
│   │   ├── schemas_gen.py
│   │   └── handler_gen.py
│   └── cancel_order/                 # custom operation
│       ├── endpoint_gen.py
│       ├── schemas_gen.py
│       └── handler.py                # hand-written, create once
└── shared/
    ├── auth/cognito_gen.py
    ├── config_gen.py
    ├── errors_gen.py
    └── db/
        ├── session_gen.py
        └── models/order_gen.py
migrations/versions/0001_create_order_gen.py
.dsml/schema-snapshot.json
openapi.gen.json
pyproject.toml
Dockerfile
```

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-101 | The FastAPI target must use Python, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic and pytest, and uv must manage the project. The versions must come from the version baseline. | Inspection | Q17, Q49 |
| PRD-APP-102 | The generator must write one slice folder for each operation: `app/features/<entity>/<operation>/`. A slice must contain `endpoint_gen.py` (the router) and `schemas_gen.py` (the Pydantic models). | Test | Q37, AD3 |
| PRD-APP-103 | For a CRUD operation, the generator must write the handler as `handler_gen.py`. For a custom operation, it must write `handler.py` as a create-once stub. | Test | Q14, Q55 |
| PRD-APP-104 | Code that all slices use must be in `app/shared/`: the database session, the SQLAlchemy models, the Cognito token check, the configuration and the error types. | Test | Q37 |
| PRD-APP-105 | `app/main_gen.py` must create the FastAPI application and register the router of each slice in sorted order. | Test | Q37 |
| PRD-APP-106 | A generated file in a slice must import only from its own slice and from `app/shared/`. | Test | AD3 |

## API operations and schemas

Each operation in the IR becomes one endpoint. The generator writes the endpoint, the schemas and the role check. A custom operation calls the hand-written handler.

| CRUD operation | HTTP method and default path | Success response |
| --- | --- | --- |
| `create` | `POST /<entities>` | 201 with the created entity |
| `read` | `GET /<entities>/{id}` | 200 with the entity |
| `update` | `PATCH /<entities>/{id}` | 200 with the changed entity |
| `delete` | `DELETE /<entities>/{id}` | 204 with no body |
| `list` | `GET /<entities>?limit=&offset=` | 200 with `items` and `total` |

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-110 | Each operation in the IR must have one endpoint with the HTTP method and the path of the operation. CRUD operations must use the default methods and paths in the table of the section "API operations and schemas" unless the model gives a different method or path. | Test | Q14, PRD-DSML-029, Q61 |
| PRD-APP-111 | For each exposed entity, the generator must write Pydantic v2 models for create input, update input and output. The key field must not be in the create input. Each field of the update input must be optional. | Test | Q14 |
| PRD-APP-112 | Field rules must become Pydantic field constraints: `minLength` and `maxLength` to `min_length` and `max_length`, `minValue` and `maxValue` to `ge` and `le`, and `pattern` to `pattern`. | Test | Q14 |
| PRD-APP-113 | A request that breaks a field rule must get HTTP 422. A request that breaks a `unique` rule must get HTTP 409. A request for an entity that does not exist must get HTTP 404. | Test | Q14 |
| PRD-APP-114 | A `list` operation must accept `limit` (default 50, maximum 200) and `offset` (default 0). It must return the found entities in `items`, sorted by key, and their count in `total`. | Test | Q14 |
| PRD-APP-115 | An output schema must give a related entity as its key, not as a nested object. | Test | Q14 |
| PRD-APP-116 | For a custom operation, the generated endpoint must validate the input, check the roles, open a database session and then call `handle(input, session, user)` in `handler.py`. It must return the output that `handle` gives as the output schema. | Test | Q15 |
| PRD-APP-117 | The create-once `handler.py` stub must contain the typed `handle` function. Its body must raise `NotImplementedError`, so the endpoint returns HTTP 501 until a developer writes the logic. | Test | Q15 |

## Data access and migrations

Each entity becomes one SQLAlchemy model and one PostgreSQL table. The generator writes each migration from the difference between the schema snapshot and the IR, so no live database is necessary. The Next.js target uses the same type map.

| DSML field type | PostgreSQL type |
| --- | --- |
| `String` with `maxLength` | `VARCHAR(<maxLength>)` |
| `String` with no `maxLength` | `TEXT` |
| `Integer` | `BIGINT` |
| `Real` | `DOUBLE PRECISION` |
| `Decimal` | `NUMERIC(<precision>, <scale>)`, default `NUMERIC(18, 4)` |
| `Boolean` | `BOOLEAN` |
| `Date` | `DATE` |
| `DateTime` | `TIMESTAMPTZ` |
| `Uuid` | `UUID` |
| Enumeration | `VARCHAR(64)` with a `CHECK` constraint on the values |

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-120 | For each entity, the generator must write one typed SQLAlchemy 2 model in `app/shared/db/models/<entity>_gen.py`. The table name must be the entity name in snake case. | Test | Q19, Q37 |
| PRD-APP-121 | Field types must map to PostgreSQL types as the table of the section "Data access and migrations" gives. | Test | Q19, Q61 |
| PRD-APP-122 | A `[*]` to `[*]` relation must have a generated join table. A `[0..1]` or `[1]` relation must have a foreign key. | Test | Q14 |
| PRD-APP-123 | Database access must use the SQLAlchemy mode and the database driver that decision record 03 gives. | Test | Q51 |
| PRD-APP-124 | The generator must keep the schema snapshot in `.dsml/schema-snapshot.json`. If the IR schema is different from the snapshot, the generator must write one new Alembic migration and then update the snapshot. | Test | Q19 |
| PRD-APP-125 | A migration file must have the name `migrations/versions/<NNNN>_<slug>_gen.py`. Its revision ID must come from its content and its number, not from a random value or the clock. | Test | Q16, Q19 |
| PRD-APP-126 | The generator must keep each migration file that it wrote before, byte for byte. | Test | Q19 |
| PRD-APP-127 | The generator must not write a migration that drops or renames a table or a column, unless the IR has the `#Destructive` metadata for that change. | Test | Q19 |
| PRD-APP-128 | `app/migrate_gen.py` must apply all migrations that the database does not have, and then stop. The deployment runs it as decision record 03 gives. | Test | Q53 |

## Authentication, container and fixed-name files

One shared dependency checks the Cognito access token for all slices. The container runs Uvicorn as a user that is not root.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-130 | `app/shared/auth/cognito_gen.py` must supply a FastAPI dependency. It must check the signature of the access token against the JWKS of the user pool, and the claims `iss`, `token_use` (`access`), `client_id` and `exp`. | Test | Q42 |
| PRD-APP-131 | The dependency must keep the JWKS in memory and get it again only when a token has an unknown key ID. | Test | Q42 |
| PRD-APP-132 | `app/shared/config_gen.py` must read the configuration from environment variables at start. If a mandatory variable is missing, the application must stop with a message that names the variable. | Test | PRD-APP-010 |
| PRD-APP-133 | The Dockerfile must install the locked dependencies with `uv sync --frozen --no-dev` and run Uvicorn on port 8000. | Test | Q25 |
| PRD-APP-134 | The fixed-name generated files of the FastAPI target must be: `pyproject.toml`, `Dockerfile`, `.dockerignore`, `alembic.ini`, `migrations/env.py` and each `__init__.py` in a generated folder. | Inspection | Q34, PRD-CORE-039 |
| PRD-APP-135 | `pytest` must run on the generated project with no error when the project has no tests. | Test | Q13 |
