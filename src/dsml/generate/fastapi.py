# trace: PRD-APP-001, PRD-APP-002, PRD-APP-008, PRD-APP-101, PRD-APP-104, PRD-APP-120,
# PRD-APP-123, PRD-APP-130, PRD-APP-134
"""The FastAPI generator (phase 1).

The generator reads only the IR and the configuration (PRD-APP-001,
PRD-CORE-026). For each application with the target `fastapi`, it writes
the project files and the shared code into the output folder of the
application (PRD-APP-002):

- `pyproject.toml`, `Dockerfile` and `.dockerignore`.
- `app/main_gen.py`: the application factory and `GET /healthz`.
- `app/shared/config_gen.py`, `app/shared/errors_gen.py` and
  `app/shared/logs_gen.py`: the configuration, the problem details and the
  JSON logs.
- `app/shared/auth/cognito_gen.py`: the Cognito token check and the role
  check (PRD-APP-008, PRD-APP-130, PRD-APP-131).
- `tests/test_app_gen.py` and `tests/test_auth_gen.py`: the tests of the
  shared code, so that `pytest` finds tests in a new project (PRD-APP-135).
- Each `__init__.py` of a generated folder.

If the application has entities, the generator also writes the database
code (`dsml.generate.fastapi_database`): the SQLAlchemy models, the
asynchronous session and their tests (PRD-APP-120 to PRD-APP-123). It
also writes the migration files (`dsml.generate.fastapi_migrations`):
`alembic.ini`, `migrations/env.py`, the migrations, the schema snapshot,
`app/migrate_gen.py` and the tests of the migrations (PRD-APP-124 to
PRD-APP-128).

The versions come from the version baseline `versions.toml` (PRD-APP-101).
The generator gives the symbols of each Python file for the trace manifest.
Other M6 stories add the slices.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

from dsml.config import Configuration
from dsml.database.schema import application_schema
from dsml.database.snapshot import SNAPSHOT_PATH
from dsml.errors import ToolchainError
from dsml.generate.fastapi_database import MODELS_FOLDER, Model, import_lines, models
from dsml.generate.fastapi_migrations import Call, code_lines, migration_files
from dsml.generate.fastapi_slices import (
    FEATURES_FOLDER,
    LIMIT_DEFAULT,
    LIMIT_MAX,
    EntityTests,
    Slice,
    bracket_lines,
    entity_tests,
    slices,
)
from dsml.generate.header import FileType, file_type_of
from dsml.generate.names import kebab_case
from dsml.generate.python_symbols import python_symbols
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import Kind, OutputFile, application_part
from dsml.ir.model import Element, EnumValue, Ir
from dsml.versions import Pin, load_baseline, pinned_version

TARGET: Final = "fastapi"
"""The literal of `DSML::Target` that selects this generator."""

FIXED_NAMES: Final = (
    ".dockerignore",
    "Dockerfile",
    "__init__.py",
    "alembic.ini",
    "migrations/env.py",
    "pyproject.toml",
)
"""The fixed-name generated files of the FastAPI target (PRD-APP-134)."""

STATE_FILES: Final = (SNAPSHOT_PATH,)
"""The generated files of the toolchain state that have a fixed path (PRD-APP-124).

The name of the schema snapshot does not end with `.gen.json`, because
PRD-APP-124 gives its path. The generator owns the file.
"""

PROJECT_VERSION: Final = "0.1.0"
"""The version of the generated project and of its OpenAPI document."""

RUNTIME_PACKAGES: Final = ("cryptography", "fastapi", "pydantic", "pyjwt", "uvicorn")
"""The baseline items of the run-time dependencies (PRD-APP-101)."""

DATABASE_PACKAGES: Final[dict[str, str | None]] = {
    "alembic": None,
    "psycopg": "binary",
    "sqlalchemy": "asyncio",
}
"""The baseline items and the extras of the database dependencies (PRD-APP-101,
PRD-APP-123, Q51).

The extra "binary" of psycopg holds libpq. The extra "asyncio" of
SQLAlchemy holds greenlet, which the asynchronous mode needs. Alembic
applies the migrations.
"""

DEV_PACKAGES: Final = ("httpx2", "pyright", "pytest", "ruff")
"""The baseline items of the dev dependencies."""

# The template of each output file, by the path in the output folder.
_TEMPLATES: Final = {
    ".dockerignore": "fastapi/dockerignore.j2",
    "Dockerfile": "fastapi/Dockerfile.j2",
    "app/__init__.py": "fastapi/init.py.j2",
    "app/main_gen.py": "fastapi/main_gen.py.j2",
    "app/shared/__init__.py": "fastapi/init.py.j2",
    "app/shared/auth/__init__.py": "fastapi/init.py.j2",
    "app/shared/auth/cognito_gen.py": "fastapi/cognito_gen.py.j2",
    "app/shared/config_gen.py": "fastapi/config_gen.py.j2",
    "app/shared/errors_gen.py": "fastapi/errors_gen.py.j2",
    "app/shared/logs_gen.py": "fastapi/logs_gen.py.j2",
    "pyproject.toml": "fastapi/pyproject.toml.j2",
    "tests/test_app_gen.py": "fastapi/test_app_gen.py.j2",
    "tests/test_auth_gen.py": "fastapi/test_auth_gen.py.j2",
}

# The templates of the database code, by the path in the output folder.
_DATABASE_TEMPLATES: Final = {
    "app/shared/db/__init__.py": "fastapi/init.py.j2",
    "app/shared/db/base_gen.py": "fastapi/db/base_gen.py.j2",
    "app/shared/db/session_gen.py": "fastapi/db/session_gen.py.j2",
    f"{MODELS_FOLDER}/__init__.py": "fastapi/init.py.j2",
    "tests/test_db_gen.py": "fastapi/db/test_db_gen.py.j2",
    "alembic.ini": "fastapi/migrations/alembic.ini.j2",
    "app/migrate_gen.py": "fastapi/migrate_gen.py.j2",
    "migrations/env.py": "fastapi/migrations/env.py.j2",
    "tests/test_migrations_gen.py": "fastapi/migrations/test_migrations_gen.py.j2",
}

# The templates of the shared code of the CRUD slices, by the path in the output folder.
_SLICE_TEMPLATES: Final = {
    f"{FEATURES_FOLDER}/__init__.py": "fastapi/init.py.j2",
    "app/shared/db/commit_gen.py": "fastapi/db/commit_gen.py.j2",
    "tests/http_support_gen.py": "fastapi/tests/http_support_gen.py.j2",
}

# The templates of the files of one slice, by the name of the file in the slice folder.
_SLICE_FILES: Final = {
    "__init__.py": "fastapi/init.py.j2",
    "endpoint_gen.py": "fastapi/slices/endpoint_gen.py.j2",
    "handler_gen.py": "fastapi/slices/handler_gen.py.j2",
    "schemas_gen.py": "fastapi/slices/schemas_gen.py.j2",
}


# trace: PRD-APP-007, PRD-APP-010, PRD-APP-132
@dataclass(frozen=True, slots=True)
class Variable:
    """One environment variable of the configuration of the application."""

    name: str
    """The name of the environment variable, for example `APP_ENVIRONMENT`."""
    field: str
    """The name of the field of the class `Settings`."""
    doc: str
    """The description of the field."""
    default: str = ""
    """The default value. An empty text makes the variable mandatory."""
    secret: bool = False
    """Tell if the value is secret. The text of the settings does not show a secret value."""

    @property
    def mandatory(self) -> bool:
        """Tell if the application stops when the variable is missing."""
        return not self.default


VARIABLES: Final = (
    Variable(
        "APP_ENVIRONMENT",
        "environment",
        "The name of the environment, for example `dev`.",
    ),
    Variable(
        "LOG_LEVEL",
        "log_level",
        "The lowest level of the logs: DEBUG, INFO, WARNING or ERROR.",
        "INFO",
    ),
    Variable(
        "AWS_REGION",
        "aws_region",
        "The AWS Region of the user pool, for example `eu-west-1`.",
    ),
    Variable(
        "COGNITO_USER_POOL_ID",
        "cognito_user_pool_id",
        "The ID of the Cognito user pool of the environment.",
    ),
    Variable(
        "COGNITO_APP_CLIENT_ID",
        "cognito_app_client_id",
        "The ID of the app client of the application.",
    ),
)
"""The environment variables of the shared configuration, in the order of the fields."""

# trace: PRD-APP-010, PRD-APP-011, PRD-APP-123
DATABASE_VARIABLES: Final = (
    Variable("DATABASE_HOST", "database_host", "The host name of the PostgreSQL database."),
    Variable("DATABASE_PORT", "database_port", "The port of the PostgreSQL database.", "5432"),
    Variable("DATABASE_NAME", "database_name", "The name of the PostgreSQL database."),
    Variable("DATABASE_USER", "database_user", "The user name for the PostgreSQL database."),
    Variable(
        "DATABASE_PASSWORD",
        "database_password",
        "The password of the user. ECS sets it from Secrets Manager.",
        secret=True,
    ),
    Variable(
        "DATABASE_SSL_MODE",
        "database_ssl_mode",
        "The TLS mode of the connection (the libpq value `sslmode`).",
        "require",
    ),
)
"""The environment variables of the database, if the application has entities."""


# trace: PRD-APP-001, PRD-APP-002, PRD-APP-017, PRD-CORE-039, PRD-TRACE-006
class FastApiGenerator:
    """The generator of the target `fastapi`."""

    name = "fastapi"
    fixed_names: Collection[str] = (*FIXED_NAMES, *STATE_FILES)

    def generate(
        self, ir: Ir, configuration: Configuration, parts: Collection[str] | None
    ) -> Sequence[OutputFile]:
        files: list[OutputFile] = []
        engine: TemplateEngine | None = None
        for application in applications(ir):
            part = application_part(application.name)
            if parts is not None and part not in parts:
                continue
            folder = output_folder(application, configuration)
            if engine is None:
                engine = TemplateEngine()
            files.extend(application_files(engine, ir, application, configuration, folder, part))
        return files


# trace: PRD-APP-001
def applications(ir: Ir) -> list[Element]:
    """Give the applications of the IR with the target `fastapi`, sorted by identity."""
    return sorted(
        (
            element
            for element in ir.elements
            if element.kind == "Application" and _target(element) == TARGET
        ),
        key=lambda element: element.identity,
    )


def _target(application: Element) -> str | None:
    for attribute in application.attributes:
        if attribute.name == "target" and isinstance(attribute.value, EnumValue):
            return attribute.value.literal
    return None


# trace: PRD-APP-002, PRD-CORE-013
def output_folder(application: Element, configuration: Configuration) -> str:
    """Give the output folder of an application, relative to the configuration file.

    The result is an empty text for the folder of the configuration file,
    or a path that ends with "/".
    """
    settings = configuration.application(application.name)
    if settings is None or settings.output is None:
        raise ToolchainError(
            f'The configuration file gives no output folder for the application "'
            f'{application.name}". Add the key applications.{application.name}.output.'
        )
    folder = PurePosixPath(settings.output).as_posix()
    return "" if folder == "." else f"{folder}/"


# trace: PRD-APP-101, PRD-CORE-031, PRD-CORE-046
def dependencies(
    application: Element,
    configuration: Configuration,
    baseline: dict[str, Pin],
    database: bool = False,
) -> tuple[list[str], list[str]]:
    """Give the run-time and the dev dependencies of an application, each sorted.

    The run-time list has the pinned packages of the target and the extra
    dependencies of the key `applications.<name>.dependencies` (PRD-CORE-046).
    If `database` is true, the list also has the database packages.
    """
    settings = configuration.application(application.name)
    extra = settings.dependencies if settings is not None else ()
    runtime = [f"{name}=={pinned_version(name, baseline)}" for name in RUNTIME_PACKAGES]
    if database:
        runtime.extend(
            f"{name}{'' if extra_name is None else f'[{extra_name}]'}"
            f"=={pinned_version(name, baseline)}"
            for name, extra_name in DATABASE_PACKAGES.items()
        )
    dev = [f"{name}=={pinned_version(name, baseline)}" for name in DEV_PACKAGES]
    return sorted(set(runtime) | set(extra)), sorted(dev)


def _value(baseline: dict[str, Pin], name: str) -> str:
    value = baseline[name].value
    if value is None:
        raise ToolchainError(f'The version baseline has no value for the item "{name}".')
    return value


# trace: PRD-APP-002, PRD-APP-008, PRD-APP-013, PRD-APP-017, PRD-APP-104, PRD-APP-105,
# PRD-APP-120, PRD-APP-124, PRD-APP-128, PRD-APP-130, PRD-APP-131, PRD-APP-133,
# PRD-APP-134, PRD-TRACE-005, PRD-TRACE-006
def application_files(
    engine: TemplateEngine,
    ir: Ir,
    application: Element,
    configuration: Configuration,
    folder: str,
    part: str,
) -> list[OutputFile]:
    """Give the project files, the shared code, the database code and the migrations."""
    baseline = load_baseline()
    entity_models = models(ir, application)
    database = bool(entity_models)
    crud = slices(ir, application, entity_models)
    runtime, dev = dependencies(application, configuration, baseline, database)
    elements = (application.identity,)
    variables = VARIABLES + DATABASE_VARIABLES if database else VARIABLES
    templates = {**_TEMPLATES, **_DATABASE_TEMPLATES} if database else dict(_TEMPLATES)
    if crud:
        templates.update(_SLICE_TEMPLATES)
    data: dict[str, object] = {
        "elements": list(elements),
        "application": application.name,
        "project": kebab_case(application.name),
        "version": PROJECT_VERSION,
        "dependencies": runtime,
        "dev_dependencies": dev,
        "python_line": baseline["python"].line,
        "python_image": _value(baseline, "python-image"),
        "uv_image": _value(baseline, "uv-image"),
        "variables": variables,
        "database": database,
        "models": entity_models,
        "join_tables": [table for model in entity_models for table in model.join_tables],
        "checks": any(model.checks for model in entity_models),
        "model_modules_import_lines": import_lines(
            "app.shared.db.models", [model.module for model in entity_models]
        ),
        "model_modules": code_lines(
            Call(
                "MODEL_MODULES = ",
                tuple(model.module for model in entity_models),
                is_tuple=True,
            ),
            0,
        ),
        "slices": crud,
        "router_import_lines": [
            line
            for item in crud
            for line in import_lines(f"{item.package}.endpoint_gen", [f"router as {item.router}"])
        ],
        "models_lines": models_tuple_lines([model.class_name for model in entity_models]),
        "model_import_lines": [
            line
            for model in entity_models
            for line in import_lines(f"app.shared.db.models.{model.module}", [model.class_name])
        ],
        "tables": sorted(
            [
                *(_TableColumns(model.table, model.columns) for model in entity_models),
                *(
                    _TableColumns(table.name, table.columns)
                    for model in entity_models
                    for table in model.join_tables
                ),
            ],
            key=lambda table: table.name,
        ),
    }
    files: list[OutputFile] = []
    for path, template in sorted(templates.items()):
        file_type = file_type_of(path)
        content = engine.render_bytes(template, {**data, "file_type": file_type.value})
        symbols = python_symbols(content, elements) if file_type is FileType.PYTHON else ()
        files.append(OutputFile(f"{folder}{path}", content, Kind.GENERATED, part, symbols))
    files.extend(model_file(engine, model, folder, part) for model in entity_models)
    files.extend(slice_files(engine, crud, folder, part))
    files.extend(
        test_file(engine, tests, folder, part) for tests in entity_tests(ir, crud, entity_models)
    )
    if database:
        schema = application_schema(ir, application.identity)
        files.extend(migration_files(engine, ir, application, configuration, schema, folder, part))
    return sorted(files, key=lambda file: file.path)


@dataclass(frozen=True, slots=True)
class _TableColumns:
    """The name and the columns of one table, for the tests of the database code."""

    name: str
    columns: tuple[object, ...]


# trace: PRD-APP-017, PRD-APP-120, PRD-APP-121, PRD-APP-122, PRD-TRACE-005, PRD-TRACE-006
def model_file(engine: TemplateEngine, model: Model, folder: str, part: str) -> OutputFile:
    """Give the file of the SQLAlchemy model of one entity.

    The header gives the entity and the relations of the join tables. The
    symbol of the class gives the entity.
    """
    elements = model.elements
    content = engine.render_bytes(
        "fastapi/db/model_gen.py.j2",
        {"file_type": FileType.PYTHON.value, "elements": elements, "model": model},
    )
    symbols = python_symbols(content, tuple(elements), {model.class_name: (model.entity,)})
    return OutputFile(f"{folder}{model.path}", content, Kind.GENERATED, part, symbols)


# trace: PRD-APP-017, PRD-APP-102, PRD-APP-103, PRD-TRACE-005, PRD-TRACE-006
def slice_files(
    engine: TemplateEngine, items: Sequence[Slice], folder: str, part: str
) -> list[OutputFile]:
    """Give the files of the CRUD slices and the `__init__.py` of each entity folder.

    The header of a slice file gives the exposed element and the entity. The
    endpoint file gives one route symbol for its endpoint.
    """
    files: list[OutputFile] = []
    entity_folders: dict[str, list[str]] = {}
    for item in items:
        entity_folders.setdefault(item.folder.rpartition("/")[0], []).extend(item.elements)
        data: dict[str, object] = {
            "file_type": FileType.PYTHON.value,
            "elements": item.elements,
            "operation": item,
            "limit_default": LIMIT_DEFAULT,
            "limit_max": LIMIT_MAX,
        }
        for name, template in sorted(_SLICE_FILES.items()):
            content = engine.render_bytes(template, data)
            symbols = python_symbols(content, tuple(item.elements))
            files.append(
                OutputFile(f"{folder}{item.folder}/{name}", content, Kind.GENERATED, part, symbols)
            )
    for path, elements in sorted(entity_folders.items()):
        identities = sorted(set(elements))
        content = engine.render_bytes(
            "fastapi/init.py.j2", {"file_type": FileType.PYTHON.value, "elements": identities}
        )
        files.append(OutputFile(f"{folder}{path}/__init__.py", content, Kind.GENERATED, part, ()))
    return files


# trace: PRD-APP-017, PRD-APP-113, PRD-APP-114, PRD-APP-135, PRD-TRACE-005, PRD-TRACE-006
def test_file(engine: TemplateEngine, tests: EntityTests, folder: str, part: str) -> OutputFile:
    """Give the file of the HTTP tests of the CRUD operations of one exposed entity."""
    content = engine.render_bytes(
        "fastapi/tests/test_http_gen.py.j2",
        {"file_type": FileType.PYTHON.value, "elements": tests.elements, "tests": tests},
    )
    symbols = python_symbols(content, tuple(tests.elements))
    return OutputFile(f"{folder}{tests.path}", content, Kind.GENERATED, part, symbols)


def models_tuple_lines(names: list[str]) -> list[str]:
    """Give the lines of the tuple `MODELS` of the HTTP test support code."""
    head = "MODELS: tuple[type[Base], ...] = "
    if len(names) == 1:
        return [f"{head}({names[0]},)"]
    return bracket_lines(head, names, "(", ")")
