# trace: PRD-APP-104, PRD-APP-120, PRD-APP-121, PRD-APP-122, PRD-APP-123
"""The database code of the FastAPI generator.

The functions of this module get the data of the templates of the database
code from the schema of the application (`dsml.database.schema`):

- `app/shared/db/base_gen.py`: the declarative base and the names of the
  constraints.
- `app/shared/db/session_gen.py`: the asynchronous engine and session, with
  the psycopg 3 driver (PRD-APP-123, Q51).
- `app/shared/db/models/<entity>_gen.py`: one typed SQLAlchemy 2 model for
  each entity (PRD-APP-120). The file of an entity also holds the join
  tables of its `[*]` relations (PRD-APP-122).
- `tests/test_db_gen.py`: the tests of the tables of the models.

The type map of PRD-APP-121 gives the SQLAlchemy type and the Python type
of each column.
"""

import keyword
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from dsml.database.schema import (
    ENUMERATION,
    ENUMERATION_LENGTH,
    FIELD_RULES,
    Column,
    ColumnType,
    SchemaError,
    Table,
    application_schema,
)
from dsml.generate.names import pascal_case, snake_case
from dsml.ir.model import BooleanValue, Element, Ir

MODELS_FOLDER: Final = "app/shared/db/models"
"""The folder of the model files, relative to the output folder of the application."""

LINE_LENGTH: Final = 100
"""The line length of the generated project (`tool.ruff.line-length`)."""

RESERVED_ATTRIBUTES: Final = frozenset({"metadata", "registry"})
"""The class attributes of the declarative base. A column must not use these names."""

# trace: PRD-APP-121
_SQLALCHEMY_TYPES: Final = {
    "Boolean": ("Boolean", "bool"),
    "Date": ("Date", "date"),
    "DateTime": ("DateTime(timezone=True)", "datetime"),
    "Integer": ("BigInteger", "int"),
    "Real": ("Double", "float"),
    "Uuid": ("Uuid", "UUID"),
}
"""The SQLAlchemy type and the Python type of the DSML field types with no parameter."""

_PYTHON_IMPORTS: Final = {
    "Decimal": "decimal",
    "UUID": "uuid",
    "date": "datetime",
    "datetime": "datetime",
}
"""The module of each Python type that needs an import."""

_COMPILED_ALIASES: Final = {"TIMESTAMPTZ": "TIMESTAMP WITH TIME ZONE"}
"""The text that SQLAlchemy writes for a PostgreSQL type alias of the type map."""


# trace: PRD-APP-121
@dataclass(frozen=True, slots=True)
class SqlType:
    """The SQLAlchemy type and the Python type of a column."""

    expression: str
    """The SQLAlchemy type expression, for example `String(500)`."""
    python: str
    """The Python type of the values, for example `str`."""

    @property
    def name(self) -> str:
        """Give the name of the SQLAlchemy type to import, for example `String`."""
        return self.expression.partition("(")[0]


# trace: PRD-APP-121
def sql_type(column_type: ColumnType) -> SqlType:
    """Give the SQLAlchemy type and the Python type of a column type (PRD-APP-121)."""
    match column_type.name:
        case "String":
            if column_type.length is None:
                return SqlType("Text", "str")
            return SqlType(f"String({column_type.length})", "str")
        case "Decimal":
            return SqlType(f"Numeric({column_type.precision}, {column_type.scale})", "Decimal")
        case "Enumeration":
            return SqlType(f"String({ENUMERATION_LENGTH})", "str")
        case _:
            expression, python = _SQLALCHEMY_TYPES[column_type.name]
            return SqlType(expression, python)


def compiled_type(column_type: ColumnType) -> str:
    """Give the text that SQLAlchemy writes for the PostgreSQL type of a column type."""
    text = column_type.postgresql
    return _COMPILED_ALIASES.get(text, text)


# trace: PRD-APP-120, PRD-APP-121, PRD-APP-122
@dataclass(frozen=True, slots=True)
class ModelColumn:
    """One column of a model or of a join table, as the templates write it."""

    name: str
    attribute: str
    """The name of the class attribute. It is the column name, or the column name and `_`."""
    type: SqlType
    postgresql: str
    """The text that SQLAlchemy writes for the PostgreSQL type of the column."""
    nullable: bool
    primary_key: bool
    foreign_key: str | None
    """The column that the column refers to, for example `customer.id`."""
    values: tuple[str, ...] = ()
    """The values of an enumeration column. A `CHECK` constraint permits only these values."""
    unique: bool = False
    """Tell if the field has the rule `unique`. A `UNIQUE` constraint keeps the values unique."""

    @property
    def values_constant(self) -> str:
        """Give the name of the constant that holds the values of an enumeration column."""
        return f"{self.name.upper()}_VALUES"

    @property
    def mapped_lines(self) -> list[str]:
        """Give the lines of the class attribute of the column in a model."""
        arguments: list[str] = []
        if self.attribute != self.name:
            arguments.append(f'"{self.name}"')
        arguments.append(self.type.expression)
        if self.foreign_key is not None:
            arguments.append(f'ForeignKey("{self.foreign_key}")')
        if self.primary_key:
            arguments.append("primary_key=True")
        if self.unique:
            arguments.append("unique=True")
        python = f"{self.type.python} | None" if self.nullable else self.type.python
        return python_call(f"{self.attribute}: Mapped[{python}] = mapped_column", arguments, 1)

    @property
    def expected_lines(self) -> list[str]:
        """Give the lines of the column in the dictionary `COLUMNS` of the tests."""
        foreign_key = "None" if self.foreign_key is None else f'"{self.foreign_key}"'
        items = [f'"{self.postgresql}"', str(self.nullable), foreign_key]
        line = f'        "{self.name}": ({", ".join(items)}),'
        if len(line) <= LINE_LENGTH:
            return [line]
        return [
            f'        "{self.name}": (',
            *(f"            {item}," for item in items),
            "        ),",
        ]

    @property
    def table_lines(self) -> list[str]:
        """Give the lines of the column in a join table."""
        arguments = [f'"{self.name}"', self.type.expression]
        if self.foreign_key is not None:
            arguments.append(f'ForeignKey("{self.foreign_key}")')
        arguments.append("primary_key=True")
        return python_call(f"Column[{self.type.python}]", arguments, 1, ",")


# trace: PRD-APP-122
@dataclass(frozen=True, slots=True)
class JoinTable:
    """One join table of a `[*]` relation."""

    name: str
    element: str
    """The identity of the relation."""
    columns: tuple[ModelColumn, ...]

    @property
    def variable(self) -> str:
        """Give the name of the module variable of the table."""
        return f"{self.name}_table"


# trace: PRD-APP-120, PRD-APP-121, PRD-APP-122
@dataclass(frozen=True, slots=True)
class Model:
    """The model of one entity and the join tables of its `[*]` relations."""

    entity: str
    """The identity of the entity."""
    entity_name: str
    class_name: str
    table: str
    columns: tuple[ModelColumn, ...]
    join_tables: tuple[JoinTable, ...]

    @property
    def module(self) -> str:
        """Give the name of the module of the model, for example `order_gen`."""
        return f"{self.table}_gen"

    @property
    def path(self) -> str:
        """Give the path of the model file in the output folder of the application."""
        return f"{MODELS_FOLDER}/{self.module}.py"

    @property
    def elements(self) -> list[str]:
        """Give the identities of the elements of the model file, sorted."""
        return sorted({self.entity, *(table.element for table in self.join_tables)})

    @property
    def checks(self) -> tuple[ModelColumn, ...]:
        """Give the enumeration columns. Each has a `CHECK` constraint."""
        return tuple(column for column in self.columns if column.values)

    @property
    def sqlalchemy_imports(self) -> list[str]:
        """Give the names to import from `sqlalchemy`, sorted as ruff sorts them."""
        names = {column.type.name for column in self.columns}
        if self.checks:
            names |= {"CheckConstraint", "column"}
        if any(column.foreign_key for column in self.columns):
            names.add("ForeignKey")
        for table in self.join_tables:
            names |= {"Column", "ForeignKey", "Table"}
            names |= {column.type.name for column in table.columns}
        return _ruff_order(names)

    @property
    def sqlalchemy_import_lines(self) -> list[str]:
        """Give the lines of the import from `sqlalchemy`."""
        return import_lines("sqlalchemy", self.sqlalchemy_imports)

    @property
    def test_import_lines(self) -> list[str]:
        """Give the lines of the import of the model and its join tables in the tests."""
        names = [self.class_name, *(table.variable for table in self.join_tables)]
        return import_lines(f"app.shared.db.models.{self.module}", names)

    @property
    def python_imports(self) -> list[str]:
        """Give the import lines of the Python types, sorted as ruff sorts them."""
        modules: dict[str, set[str]] = {}
        for column in self.columns + tuple(
            column for table in self.join_tables for column in table.columns
        ):
            module = _PYTHON_IMPORTS.get(column.type.python)
            if module is not None:
                modules.setdefault(module, set()).add(column.type.python)
        return [
            f"from {module} import {', '.join(_ruff_order(names))}"
            for module, names in sorted(modules.items())
        ]


# trace: PRD-APP-120, PRD-APP-121, PRD-APP-122
def models(ir: Ir, application: Element) -> list[Model]:
    """Give the models of the entities of an application, sorted by table name.

    A column with a type that is not supported gives a `SchemaError`. The
    validator finds this error first (STR-007).
    """
    schema = application_schema(ir, application.identity)
    elements: Mapping[str, Element] = {item.identity: item for item in ir.elements}
    join_tables: dict[str, list[JoinTable]] = {}
    for table in schema.tables:
        relation = elements.get(table.element or "")
        if relation is not None and relation.kind == "Relation" and relation.owner is not None:
            join_tables.setdefault(relation.owner, []).append(
                JoinTable(table.name, relation.identity, _columns(table, elements))
            )
    result: list[Model] = []
    for table in schema.tables:
        entity = elements.get(table.element or "")
        if entity is None or entity.kind != "Entity":
            continue
        result.append(
            Model(
                entity=entity.identity,
                entity_name=entity.name,
                class_name=pascal_case(entity.name),
                table=table.name,
                columns=_columns(table, elements),
                join_tables=tuple(join_tables.get(entity.identity, ())),
            )
        )
    return result


def _columns(table: Table, elements: Mapping[str, Element]) -> tuple[ModelColumn, ...]:
    return tuple(
        _column(table, column, _is_unique(elements.get(column.element or "")))
        for column in table.columns
    )


# trace: PRD-DSML-025, PRD-APP-113
def _is_unique(field: Element | None) -> bool:
    """Tell if a field has the rule `unique = true` in its `@FieldRules`."""
    if field is None or field.kind != "Field":
        return False
    return any(
        attribute.name == "unique"
        and isinstance(attribute.value, BooleanValue)
        and attribute.value.value
        for annotation in field.annotations
        if annotation.name == FIELD_RULES
        for attribute in annotation.attributes
    )


def _column(table: Table, column: Column, unique: bool = False) -> ModelColumn:
    if column.type is None:
        raise SchemaError(
            f'The column "{column.name}" of the table "{table.name}" has a type that is '
            "not supported. Use a field type that STR-007 permits."
        )
    foreign_key = None
    if column.references is not None:
        foreign_key = f"{column.references.table}.{column.references.column}"
    return ModelColumn(
        name=column.name,
        attribute=_attribute(column.name),
        type=sql_type(column.type),
        postgresql=compiled_type(column.type),
        nullable=column.nullable,
        primary_key=column.primary_key,
        foreign_key=foreign_key,
        values=column.type.values if column.type.name == ENUMERATION else (),
        unique=unique,
    )


def _attribute(name: str) -> str:
    """Give the class attribute of a column. Add `_` to a keyword or a reserved name."""
    if keyword.iskeyword(name) or keyword.issoftkeyword(name) or name in RESERVED_ATTRIBUTES:
        return f"{name}_"
    return snake_case(name)


def import_lines(module: str, names: list[str]) -> list[str]:
    """Give the lines of an import in the form that ruff gives."""
    line = f"from {module} import {', '.join(names)}"
    if len(line) <= LINE_LENGTH:
        return [line]
    return [f"from {module} import (", *(f"    {name}," for name in names), ")"]


# trace: PRD-CORE-035
def python_call(head: str, arguments: list[str], level: int, end: str = "") -> list[str]:
    """Give the lines of a call in the form that `ruff format` gives.

    `head` is the text before the opening parenthesis, and `level` is the
    indent level. The call is on one line if the line has 100 characters or
    fewer. If not, the arguments are on one line of their own. If that line
    is too long also, each argument is on its own line with a comma.
    """
    indent = "    " * level
    line = f"{indent}{head}({', '.join(arguments)}){end}"
    if len(line) <= LINE_LENGTH:
        return [line]
    inner = f"{indent}    {', '.join(arguments)}"
    if len(inner) <= LINE_LENGTH:
        return [f"{indent}{head}(", inner, f"{indent}){end}"]
    return [
        f"{indent}{head}(",
        *(f"{indent}    {argument}," for argument in arguments),
        f"{indent}){end}",
    ]


def _ruff_order(names: set[str]) -> list[str]:
    """Sort imported names as ruff sorts them: constants, classes, then other names."""

    def key(name: str) -> tuple[int, str]:
        if name.isupper() and len(name) > 1:
            return (0, name)
        if name[0].isupper():
            return (1, name)
        return (2, name)

    return sorted(names, key=key)
