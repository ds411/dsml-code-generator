# FastAPI generator: project files and shared code

Story #75 added the first part of the FastAPI generator (phase 1). The generator writes a project that starts and answers `GET /healthz`. Story #77 added the SQLAlchemy models and the database session. Other M6 stories add the slices, the migrations, the token check and `openapi.gen.json`.

- Generator: `src/dsml/generate/fastapi.py`. It is in the list `GENERATORS` of `src/dsml/generate/generators.py`.
- Database code: `src/dsml/generate/fastapi_database.py`. The tables and the column types come from `src/dsml/database/schema.py` (see `docs/notes/schema-snapshot.md`).
- Templates: `src/dsml/templates/fastapi/`.
- Symbols of Python files: `src/dsml/generate/python_symbols.py`.
- Tests: `tests/test_fastapi_generator.py` and `tests/test_fastapi_database.py`.
- Golden files: `tests/golden/fastapi/order-service/`. Write them again with `uv run python scripts/write_golden_fastapi.py`.
- CI: the job "FastAPI golden project" in `.github/workflows/ci.yml`.

## Inputs

The generator reads only the IR and the configuration (PRD-APP-001, PRD-CORE-026). It writes files for each application with `target = Target::fastapi`.

- The key `applications.<name>.output` gives the output folder of the application (PRD-APP-002). If the key is missing, `dsml generate` stops with an error. A run that does not select the application does not need the key.
- The key `applications.<name>.dependencies` gives extra dependencies. The generator adds them to the run-time dependencies in `pyproject.toml`, in sorted order (PRD-CORE-046).
- The versions and the base images come from `src/dsml/versions.toml` (PRD-APP-101).

## Output

All files are generated files. The generator writes them again at each run.

| File | Content | Requirements |
| --- | --- | --- |
| `pyproject.toml` | The pinned dependencies, the dev dependencies and the settings of ruff, pyright and pytest. `[tool.uv] package = false`. No lockfile. | PRD-APP-101, PRD-CORE-036, PRD-CORE-046 |
| `Dockerfile` | A multi-stage build. The base images are pinned by digest. `uv sync --frozen --no-dev`. Uvicorn on port 8000. The user ID 10001, not root. | PRD-APP-013, PRD-APP-133 |
| `.dockerignore` | Only `app/`, `pyproject.toml` and `uv.lock` go into the build context. | PRD-APP-013 |
| `app/main_gen.py` | The factory `create_app` and the route `GET /healthz` with no authentication. | PRD-APP-012, PRD-APP-105 |
| `app/shared/config_gen.py` | The class `Settings` and the function `load_settings`. | PRD-APP-010, PRD-APP-132 |
| `app/shared/errors_gen.py` | `ProblemError` and the handlers that give problem details (RFC 9457). | PRD-APP-014 |
| `app/shared/logs_gen.py` | JSON line logs on standard output, and the middleware of the request ID. | PRD-APP-015 |
| `tests/test_app_gen.py` | The tests of the shared code. Thus `pytest` finds tests in a new project. | PRD-APP-135 |
| `app/__init__.py`, `app/shared/__init__.py` | The header only. | PRD-APP-134 |

If the application has one or more entities, the generator also writes the database code:

| File | Content | Requirements |
| --- | --- | --- |
| `app/shared/db/base_gen.py` | The declarative base `Base`. Its metadata gives a fixed name to each constraint. | PRD-APP-104 |
| `app/shared/db/models/<entity>_gen.py` | One typed SQLAlchemy 2 model for each entity, and the join tables of its `[*]` relations. | PRD-APP-120, PRD-APP-121, PRD-APP-122 |
| `app/shared/db/session_gen.py` | The asynchronous engine, the session factory and the FastAPI dependency `get_session`. | PRD-APP-123 |
| `tests/test_db_gen.py` | Tests that compare the PostgreSQL DDL of each table with the model. They need no database. | PRD-APP-121, PRD-APP-135 |
| `app/shared/db/__init__.py`, `app/shared/db/models/__init__.py` | The header only. | PRD-APP-134 |

The run-time dependencies then also have `sqlalchemy[asyncio]` and `psycopg[binary]`.

Each file starts with the trace header (PRD-APP-017, PRD-TRACE-005). The elements of the header are the application. In a model file, the elements are the entity and the relations of its join tables.

## Database code

The database code uses SQLAlchemy 2 in the asynchronous mode with the psycopg 3 driver (PRD-APP-123, Q51).

- The table name is the entity name in snake case (PRD-APP-120). The class name is the entity name in Pascal case.
- The type map of PRD-APP-121 gives the SQLAlchemy type and the Python type of each column. For example, `Uuid` gives `Mapped[UUID] = mapped_column(Uuid)`.
- A field with the lower multiplicity 0 gives `Mapped[<type> | None]`, thus a nullable column.
- An enumeration column has a `CHECK` constraint with the name `ck_<table>_<column>_values`. The constant `<COLUMN>_VALUES` holds the permitted values.
- A `[0..1]` or `[1]` relation gives a foreign key column. A `[*]` relation gives a join table `<table>_<relation>` in the file of the entity (PRD-APP-122).
- A column with the name of a Python keyword, `metadata` or `registry` gets a class attribute with `_` at the end, for example `class_`.
- The models do not have ORM relationships. The slices use the foreign key columns.

The engine connects to the database only when a request uses a session. Thus `GET /healthz` operates with no database. The function `create_app` makes the engine, and the application closes the engine when it stops.

The fixed-name list of the target is `pyproject.toml`, `Dockerfile`, `.dockerignore`, `alembic.ini`, `migrations/env.py` and `__init__.py` (PRD-APP-134).

## Environment variables

The application reads its configuration one time at start, not at build time (PRD-APP-010).

| Variable | Mandatory | Default | Use |
| --- | --- | --- | --- |
| `APP_ENVIRONMENT` | Yes | None | The name of the environment, for example `dev`. |
| `LOG_LEVEL` | No | `INFO` | The lowest level of the logs: `DEBUG`, `INFO`, `WARNING` or `ERROR`. |

If a mandatory variable is missing, the process stops with exit code 1 and this message (PRD-APP-132):

```text
The application cannot start. The environment variable APP_ENVIRONMENT is missing. Set it before the application starts.
```

If the application has entities, it also reads these variables:

| Variable | Mandatory | Default | Use |
| --- | --- | --- | --- |
| `DATABASE_HOST` | Yes | None | The host name of the PostgreSQL database. |
| `DATABASE_PORT` | No | `5432` | The port of the database. It must be a number. |
| `DATABASE_NAME` | Yes | None | The name of the database. |
| `DATABASE_USER` | Yes | None | The user name. |
| `DATABASE_PASSWORD` | Yes | None | The password. ECS sets it from Secrets Manager (PRD-APP-011). The text of the settings does not show it. |
| `DATABASE_SSL_MODE` | No | `require` | The TLS mode of the connection, the libpq value `sslmode`. |

The infrastructure generator must set these variables in the task definition. A later story adds the variables of the user pool.

## Errors and logs

- Each error response has the media type `application/problem+json` and the keys `type`, `title` and `status`. An error can also have `detail`. A validation error (HTTP 422) has `errors`, with the location, the message and the type of each error, but not the input value.
- An error that no handler catches gives HTTP 500 with problem details. The log line of the error has the exception.
- Each log line is one JSON object with the keys `time`, `level`, `logger`, `message` and `requestId`. The line of a request also has `method`, `path`, `status` and `durationMs`.
- The request ID comes from the header `X-Request-ID` if it has 1 to 128 characters from `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`. Otherwise the application makes a new request ID. The response has the header `X-Request-ID`.
- The logs do not contain headers, query parameters or bodies. Thus they do not contain tokens or secret values (PRD-APP-015).
- The access log of Uvicorn is off, because the middleware writes one line for each request.

## Trace manifest

The generator gives the symbols of each Python file (PRD-TRACE-006). `python_symbols` reads the file with the Python parser:

- Each top-level class gives a `class` symbol. Each top-level function gives a `function` symbol.
- A function with a route decorator, for example `@health_router.get("/healthz")`, also gives a `route` symbol, for example `GET /healthz`.
- The line range starts at the first decorator and stops at the last line of the class or function.

## Versions

Story #75 added the exact versions of the FastAPI stack to `src/dsml/versions.toml`. The newest release of each line on 11 October 2026 is the exact version.

| Item | Version | Use |
| --- | --- | --- |
| `python` | 3.14.8 | The Python version of the base image. |
| `fastapi` | 0.143.0 | Run-time dependency. |
| `pydantic` | 2.14.1 | Run-time dependency. |
| `uvicorn` | 0.54.0 | Run-time dependency, the ASGI server. |
| `sqlalchemy` | 2.1.4 | Run-time dependency with the extra `asyncio`, if the application has entities. |
| `psycopg` | 3.3.6 | Run-time dependency with the extra `binary`, if the application has entities (story #77). |
| `alembic` | 1.20.0 | For the migration story. |
| `pytest` | 9.1.1 | Dev dependency. |
| `httpx2` | 2.13.1 | Dev dependency, the HTTP client of the test client of Starlette 1.x. |
| `ruff` | 0.17.0 | Dev dependency. |
| `pyright` | 1.1.414 | Dev dependency, the type checker. |
| `uv` | 0.13.0 | The uv image of the build stage. |
| `python-image` | `python:3.14.8-slim-trixie` | The base image, pinned by the digest of its multi-platform image index. |
| `uv-image` | `ghcr.io/astral-sh/uv:0.13.0` | The image that supplies `uv`, pinned by digest. |

Starlette 1.x gives a deprecation warning for `httpx` in its test client. Thus the dev dependency is `httpx2`, not `httpx`.
