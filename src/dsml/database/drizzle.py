# trace: PRD-APP-121, PRD-APP-122, PRD-APP-124, PRD-APP-127, PRD-APP-331, PRD-CORE-031
"""Write the SQL of a Drizzle migration from the changes of a schema.

The Next.js generator writes each migration as one SQL file that the Drizzle
migrator reads (PRD-APP-331, Q67). The function `sql_statements` gives the
PostgreSQL statements of the changes of `dsml.database.migration.Changes`,
in the order of `Changes`. The Drizzle migrator runs the statements of one
file in a transaction. The text `--> statement-breakpoint` divides the
statements of a file.

The SQL has the type map of PRD-APP-121 and the constraint names of
`dsml.database.migration`. Thus the two targets give the same database
schema for the same model.

All statements are in a fixed order, so the same changes give the same
SQL (PRD-CORE-031).
"""

import textwrap
from typing import Final

from dsml.database.migration import AlteredColumn, Changes, Constraint, constraints
from dsml.database.schema import Column, Table
from dsml.errors import ToolchainError

BREAKPOINT: Final = "--> statement-breakpoint"
"""The text that divides the statements of a migration file for the Drizzle migrator."""

LINE_LENGTH: Final = 100
"""The maximum length of a comment line of a migration file."""

INDENT: Final = "  "
"""The indent of the items of a `CREATE TABLE` statement."""


# trace: PRD-APP-120
def identifier(name: str) -> str:
    """Give a PostgreSQL identifier in double quotes, for example `"order"`."""
    return '"' + name.replace('"', '""') + '"'


# trace: PRD-APP-121
def literal(text: str) -> str:
    """Give a PostgreSQL string literal, for example `'open'`."""
    return "'" + text.replace("'", "''") + "'"


# trace: PRD-APP-121
def column_type(column: Column) -> str:
    """Give the PostgreSQL type of a column (PRD-APP-121)."""
    if column.type is None:
        raise ToolchainError(
            f'The column "{column.name}" has a type that is not supported. '
            "Use a field type that STR-007 permits."
        )
    return column.type.postgresql


def _column(column: Column) -> str:
    text = f"{identifier(column.name)} {column_type(column)}"
    return text if column.nullable else f"{text} NOT NULL"


def _names(columns: tuple[str, ...]) -> str:
    return ", ".join(identifier(name) for name in columns)


# trace: PRD-APP-120, PRD-APP-121, PRD-APP-122
def constraint_definition(constraint: Constraint) -> str:
    """Give the definition of a constraint, for example `CONSTRAINT "pk_x" PRIMARY KEY ("id")`."""
    head = f"CONSTRAINT {identifier(constraint.name)}"
    match constraint.kind:
        case "pk":
            return f"{head} PRIMARY KEY ({_names(constraint.columns)})"
        case "uq":
            return f"{head} UNIQUE ({_names(constraint.columns)})"
        case "fk":
            assert constraint.references is not None
            target = identifier(constraint.references.table)
            column = identifier(constraint.references.column)
            return (
                f"{head} FOREIGN KEY ({_names(constraint.columns)}) REFERENCES {target} ({column})"
            )
        case "ck":
            values = ", ".join(literal(value) for value in constraint.values)
            return f"{head} CHECK ({identifier(constraint.columns[0])} IN ({values}))"


def _create_table(table: Table, pending: set[str]) -> str:
    """Give the `CREATE TABLE` statement of a new table.

    A foreign key to a table in `pending`, which the migration creates
    later, is not in the statement. The migration adds it after the tables.
    """
    items = [_column(column) for column in table.columns]
    items.extend(
        constraint_definition(item)
        for item in constraints(table)
        if item.references is None or item.references.table not in pending
    )
    body = ",\n".join(f"{INDENT}{item}" for item in items)
    return f"CREATE TABLE {identifier(table.name)} (\n{body}\n);"


def _alter(item: AlteredColumn) -> list[str]:
    table = identifier(item.table)
    name = identifier(item.column.name)
    statements: list[str] = []
    if item.type_changed:
        text = column_type(item.column)
        statements.append(
            f"ALTER TABLE {table} ALTER COLUMN {name} SET DATA TYPE {text} USING {name}::{text};"
        )
    if item.nullable_changed:
        action = "DROP NOT NULL" if item.column.nullable else "SET NOT NULL"
        statements.append(f"ALTER TABLE {table} ALTER COLUMN {name} {action};")
    return statements


# trace: PRD-APP-124, PRD-APP-127
def sql_statements(changes: Changes) -> list[str]:
    """Give the SQL statements of the changes, in the order of `Changes`."""
    statements: list[str] = []
    statements.extend(
        f"ALTER TABLE {identifier(item.old)} RENAME TO {identifier(item.new)};"
        for item in changes.renamed_tables
    )
    statements.extend(
        f"ALTER TABLE {identifier(item.table)} RENAME COLUMN {identifier(item.old)} "
        f"TO {identifier(item.new)};"
        for item in changes.renamed_columns
    )
    statements.extend(
        f"ALTER TABLE {identifier(item.table)} RENAME CONSTRAINT {identifier(item.old)} "
        f"TO {identifier(item.new)};"
        for item in changes.renamed_constraints
    )
    statements.extend(
        f"ALTER TABLE {identifier(item.table)} DROP CONSTRAINT {identifier(item.name)};"
        for item in changes.dropped_constraints
    )
    statements.extend(
        f"ALTER TABLE {identifier(table)} DROP COLUMN {identifier(column)};"
        for table, column in changes.dropped_columns
    )
    statements.extend(f"DROP TABLE {identifier(table.name)};" for table in changes.dropped_tables)
    pending = {table.name for table in changes.created_tables}
    for table in changes.created_tables:
        pending.discard(table.name)
        statements.append(_create_table(table, pending))
    statements.extend(
        f"ALTER TABLE {identifier(table)} ADD COLUMN {_column(column)};"
        for table, column in changes.added_columns
    )
    for item in changes.altered_columns:
        statements.extend(_alter(item))
    statements.extend(
        f"ALTER TABLE {identifier(item.table)} ADD {constraint_definition(item)};"
        for item in changes.created_constraints
    )
    return statements


# trace: PRD-APP-124
def summary_lines(changes: Changes) -> list[str]:
    """Give the list of changes for the comment at the top of a migration file.

    Each line starts with `-- `. A long item continues on the next line.
    """
    items: list[str] = []
    items.extend(f"Rename the table {item.old} to {item.new}." for item in changes.renamed_tables)
    items.extend(
        f"Rename the column {item.table}.{item.old} to {item.new}."
        for item in changes.renamed_columns
    )
    items.extend(
        f"Rename the constraint {item.old} of the table {item.table} to {item.new}."
        for item in changes.renamed_constraints
    )
    items.extend(
        f"Drop the constraint {item.name} of the table {item.table}."
        for item in changes.dropped_constraints
    )
    items.extend(f"Drop the column {table}.{column}." for table, column in changes.dropped_columns)
    items.extend(f"Drop the table {table.name}." for table in changes.dropped_tables)
    items.extend(f"Create the table {table.name}." for table in changes.created_tables)
    items.extend(
        f"Add the column {table}.{column.name}." for table, column in changes.added_columns
    )
    for item in changes.altered_columns:
        name = f"{item.table}.{item.column.name}"
        if item.type_changed:
            items.append(f"Change the type of the column {name} to {column_type(item.column)}.")
        if item.nullable_changed:
            state = "nullable" if item.column.nullable else "not nullable"
            items.append(f"Make the column {name} {state}.")
    items.extend(
        f"Add the constraint {item.name} to the table {item.table}."
        for item in changes.created_constraints
    )
    lines: list[str] = []
    for item in items:
        lines.extend(
            textwrap.wrap(
                f"-- - {item}",
                width=LINE_LENGTH,
                subsequent_indent="--   ",
                break_long_words=False,
                break_on_hyphens=False,
            )
        )
    return lines
