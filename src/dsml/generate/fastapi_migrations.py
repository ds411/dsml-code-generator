# trace: PRD-APP-124, PRD-APP-125, PRD-APP-126, PRD-APP-127, PRD-CORE-033
"""The schema snapshot and the Alembic migrations of the FastAPI generator.

The generator reads the schema snapshot `.dsml/schema-snapshot.json` and the
old migrations in the output folder of the application. It compares the
snapshot with the schema of the IR (`dsml.database.migration`):

- If the schemas are different, the generator writes one new migration
  `migrations/versions/<NNNN>_<slug>_gen.py` and the new snapshot
  (PRD-APP-124, PRD-APP-125).
- The generator gives each old migration file to the file writer again,
  byte for byte (PRD-APP-126).
- The revision ID of a migration is the start of the SHA-256 hash of its
  number and its content. It does not come from a random value or the
  clock (PRD-APP-125, PRD-CORE-033).
- A migration drops or renames a table or a column only if the IR has the
  `#Destructive` metadata for that change (PRD-APP-127). Rule STR-013 stops
  the run first. This module also stops with an error.

The migrations go forward only. Their `downgrade` function stops with an
error.
"""

import hashlib
import json
import re
import textwrap
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dsml.config import Configuration
from dsml.database.migration import AlteredColumn, Changes, Constraint, compare, constraints
from dsml.database.schema import Column, Schema, Table, is_destructive
from dsml.database.snapshot import SNAPSHOT_PATH, read_snapshot, snapshot_bytes
from dsml.errors import ToolchainError
from dsml.generate.fastapi_database import LINE_LENGTH, compiled_type, sql_type
from dsml.generate.header import FileType
from dsml.generate.python_symbols import python_symbols
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import Kind, OutputFile
from dsml.ir.model import Element, Ir

VERSIONS_FOLDER: Final = "migrations/versions"
"""The folder of the migration files, relative to the output folder of the application."""

REVISION_LENGTH: Final = 12
"""The number of hexadecimal characters of a revision ID."""

_MIGRATION_NAME: Final = re.compile(r"(?P<number>[0-9]{4})_(?P<slug>[a-z0-9_]+)_gen\.py")
_REVISION: Final = re.compile(r'^revision = "(?P<revision>[0-9a-f]+)"$', re.MULTILINE)
_ELEMENTS: Final = re.compile(r"^# Elements: (?P<elements>.*)$", re.MULTILINE)
_PLACEHOLDER: Final = "0" * REVISION_LENGTH


# trace: PRD-APP-126
@dataclass(frozen=True, slots=True)
class OldMigration:
    """A migration file that the generator wrote before."""

    number: int
    path: str
    """The path in the output folder of the application."""
    content: bytes
    revision: str


# trace: PRD-APP-124, PRD-APP-125, PRD-APP-126, PRD-APP-127
def migration_files(
    engine: TemplateEngine,
    ir: Ir,
    application: Element,
    configuration: Configuration,
    schema: Schema,
    folder: str,
    part: str,
) -> list[OutputFile]:
    """Give the old migrations, the new migration if the schema changed, and the snapshot.

    `folder` is the output folder of the application, relative to the
    configuration file.
    """
    root = configuration.root / folder
    snapshot = read_snapshot(root)
    old = read_migrations(root)
    if old and snapshot is None:
        raise ToolchainError(
            f"The folder {folder}{VERSIONS_FOLDER} has migrations, but there is no schema "
            f"snapshot {folder}{SNAPSHOT_PATH}. Restore the snapshot from Git."
        )
    if snapshot is not None and snapshot.tables and not old:
        raise ToolchainError(
            f"The schema snapshot {folder}{SNAPSHOT_PATH} has tables, but the folder "
            f"{folder}{VERSIONS_FOLDER} has no migration. Restore the migrations from Git."
        )
    changes = compare(snapshot or Schema(), schema)
    check_destructive(ir, application, schema, changes)
    files: list[OutputFile] = []
    for migration in old:
        elements = _header_elements(migration.content) or (application.identity,)
        symbols = python_symbols(migration.content, elements)
        files.append(
            OutputFile(
                f"{folder}{migration.path}", migration.content, Kind.GENERATED, part, symbols
            )
        )
    if not changes.empty:
        number = old[-1].number + 1 if old else 1
        down_revision = old[-1].revision if old else None
        path, content = render_migration(engine, application, changes, number, down_revision)
        elements = (application.identity,)
        files.append(
            OutputFile(
                f"{folder}{path}",
                content,
                Kind.GENERATED,
                part,
                python_symbols(content, elements),
            )
        )
    files.append(
        OutputFile(f"{folder}{SNAPSHOT_PATH}", snapshot_bytes(schema), Kind.GENERATED, part)
    )
    return files


# trace: PRD-APP-126
def read_migrations(root: Path) -> list[OldMigration]:
    """Read the migration files in the folder `migrations/versions` of `root`, by number.

    Two files with the same number, or a file with no revision ID, give an
    error.
    """
    folder = root / VERSIONS_FOLDER
    if not folder.is_dir():
        return []
    found: dict[int, OldMigration] = {}
    for path in sorted(folder.iterdir()):
        match = _MIGRATION_NAME.fullmatch(path.name)
        if match is None or not path.is_file():
            continue
        number = int(match.group("number"))
        relative = f"{VERSIONS_FOLDER}/{path.name}"
        if number in found:
            raise ToolchainError(
                f"The migrations {found[number].path} and {relative} have the same number."
            )
        try:
            content = path.read_bytes()
        except OSError as error:
            raise ToolchainError(
                f"Cannot read the migration {relative}: {error.strerror}."
            ) from None
        revision = _REVISION.search(content.decode("utf-8", errors="replace"))
        if revision is None:
            raise ToolchainError(f"The migration {relative} has no line 'revision = \"<ID>\"'.")
        found[number] = OldMigration(number, relative, content, revision.group("revision"))
    return [found[number] for number in sorted(found)]


def _header_elements(content: bytes) -> tuple[str, ...]:
    """Give the element identities of the header of a file, or an empty tuple."""
    match = _ELEMENTS.search(content.decode("utf-8", errors="replace"))
    if match is None:
        return ()
    return tuple(item for item in match.group("elements").split(", ") if item)


# trace: PRD-APP-127, PRD-DSML-034
def check_destructive(ir: Ir, application: Element, schema: Schema, changes: Changes) -> None:
    """Stop with an error if the changes drop a table or a column with no `#Destructive`.

    A rename always has `@Destructive { renamedFrom }`. A dropped table needs
    `#Destructive` on the application. A dropped column needs it on the
    entity, or on the relation of a join table. These are the rules of
    STR-013.
    """
    elements: Mapping[str, Element] = {item.identity: item for item in ir.elements}
    errors: list[str] = []
    if changes.dropped_tables and not is_destructive(application):
        errors.extend(
            f'The migration must drop the table "{table.name}", but the application '
            f"{application.name} has no #Destructive metadata."
            for table in changes.dropped_tables
        )
    for table, column in changes.dropped_columns:
        found = schema.table(table)
        source = elements.get(found.element or "") if found is not None else None
        if source is None or not is_destructive(source):
            errors.append(
                f'The migration must drop the column "{table}.{column}", but the model has no '
                "#Destructive metadata for it."
            )
    if errors:
        raise ToolchainError("\n".join([*errors, "Rule STR-013 finds these changes."]))


# trace: PRD-APP-125, PRD-CORE-033
def render_migration(
    engine: TemplateEngine,
    application: Element,
    changes: Changes,
    number: int,
    down_revision: str | None,
) -> tuple[str, bytes]:
    """Give the path and the bytes of one new migration.

    The revision ID is the start of the SHA-256 hash of the number and of the
    content with a placeholder in place of the ID.
    """
    statements = upgrade_statements(changes)
    data: dict[str, object] = {
        "file_type": FileType.PYTHON.value,
        "elements": [application.identity],
        "application": application.name,
        "number": f"{number:04d}",
        "down_revision": "None" if down_revision is None else python_string(down_revision),
        "summary": summary_lines(changes),
        "statements": statements,
        "uses_sqlalchemy": any("sa." in line for line in statements),
        "rename_helper": bool(changes.renamed_constraints),
    }
    draft = engine.render_bytes(
        "fastapi/migrations/migration_gen.py.j2", {**data, "revision": _PLACEHOLDER}
    )
    revision = revision_id(number, draft)
    content = engine.render_bytes(
        "fastapi/migrations/migration_gen.py.j2", {**data, "revision": revision}
    )
    return f"{VERSIONS_FOLDER}/{number:04d}_{changes.slug}_gen.py", content


# trace: PRD-APP-125
def revision_id(number: int, draft: bytes) -> str:
    """Give the revision ID of a migration from its number and its draft content."""
    digest = hashlib.sha256(f"{number:04d}\n".encode() + draft).hexdigest()
    return digest[:REVISION_LENGTH]


# trace: PRD-APP-124
def summary_lines(changes: Changes) -> list[str]:
    """Give the lines of the list of changes in the docstring of a migration."""
    items: list[str] = []
    items.extend(
        f"Rename the table `{item.old}` to `{item.new}`." for item in changes.renamed_tables
    )
    items.extend(
        f"Rename the column `{item.table}.{item.old}` to `{item.new}`."
        for item in changes.renamed_columns
    )
    items.extend(
        f"Rename the constraint `{item.old}` of the table `{item.table}` to `{item.new}`."
        for item in changes.renamed_constraints
    )
    items.extend(
        f"Drop the constraint `{item.name}` of the table `{item.table}`."
        for item in changes.dropped_constraints
    )
    items.extend(
        f"Drop the column `{table}.{column}`." for table, column in changes.dropped_columns
    )
    items.extend(f"Drop the table `{table.name}`." for table in changes.dropped_tables)
    items.extend(f"Create the table `{table.name}`." for table in changes.created_tables)
    items.extend(
        f"Add the column `{table}.{column.name}`." for table, column in changes.added_columns
    )
    for item in changes.altered_columns:
        name = f"`{item.table}.{item.column.name}`"
        if item.type_changed and item.column.type is not None:
            items.append(
                f"Change the type of the column {name} to `{compiled_type(item.column.type)}`."
            )
        if item.nullable_changed:
            state = "nullable" if item.column.nullable else "not nullable"
            items.append(f"Make the column {name} {state}.")
    items.extend(
        f"Add the constraint `{item.name}` to the table `{item.table}`."
        for item in changes.created_constraints
    )
    lines: list[str] = []
    for item in items:
        lines.extend(
            textwrap.wrap(
                f"- {item}",
                width=LINE_LENGTH,
                subsequent_indent="  ",
                break_long_words=False,
                break_on_hyphens=False,
            )
        )
    return lines


# trace: PRD-CORE-035
@dataclass(frozen=True, slots=True)
class Call:
    """A call in the generated code, for example `op.drop_table("order")`.

    An argument is a text or a call. A tuple is a call with `is_tuple`. Its
    head is "", or an assignment such as `NAMES = `.
    """

    head: str
    arguments: tuple[Call | str, ...]
    is_tuple: bool = False

    def flat(self) -> str:
        """Give the call on one line."""
        texts = [item if isinstance(item, str) else item.flat() for item in self.arguments]
        inner = ", ".join(texts)
        if self.is_tuple and len(texts) == 1:
            inner += ","
        return f"{self.head}({inner})"


# trace: PRD-CORE-035
def code_lines(item: Call | str, level: int, end: str = "") -> list[str]:
    """Give the lines of a call in the form that `ruff format` gives.

    The call is on one line if the line has 100 characters or fewer. If not,
    the arguments of a call go on one line of their own. If that line is too
    long also, each argument goes on its own line, and the same rules apply
    to each argument. A comma follows each argument, but not the only
    argument of a call. A tuple that is too long for one line always has
    each item on its own line with a comma.
    """
    indent = "    " * level
    text = item if isinstance(item, str) else item.flat()
    line = f"{indent}{text}{end}"
    if isinstance(item, str) or len(line) <= LINE_LENGTH:
        return [line]
    texts = [part if isinstance(part, str) else part.flat() for part in item.arguments]
    inner = f"{indent}    {', '.join(texts)}"
    if not item.is_tuple and len(inner) <= LINE_LENGTH:
        return [f"{indent}{item.head}(", inner, f"{indent}){end}"]
    comma = "," if item.is_tuple or len(item.arguments) > 1 else ""
    lines = [f"{indent}{item.head}("]
    for part in item.arguments:
        lines.extend(code_lines(part, level + 1, comma))
    lines.append(f"{indent}){end}")
    return lines


# trace: PRD-CORE-035
def python_string(text: str) -> str:
    """Give a Python string literal with the quotes that `ruff format` prefers."""
    if '"' in text and "'" not in text:
        return "'" + text.replace("\\", "\\\\") + "'"
    return json.dumps(text, ensure_ascii=False)


def _name(name: str) -> str:
    return f"op.f({python_string(name)})"


def _type(column: Column) -> str:
    if column.type is None:
        raise ToolchainError(
            f'The column "{column.name}" has a type that is not supported. '
            "Use a field type that STR-007 permits."
        )
    expression = sql_type(column.type).expression
    if "(" not in expression:
        expression += "()"
    return f"sa.{expression}"


def _column(column: Column) -> Call:
    return Call(
        "sa.Column",
        (python_string(column.name), _type(column), f"nullable={column.nullable}"),
    )


def _values(constraint: Constraint) -> Call:
    """Give the condition of a check constraint: the column must have one of the values."""
    return Call(
        f"sa.column({python_string(constraint.columns[0])}).in_",
        (Call("", tuple(python_string(value) for value in constraint.values), is_tuple=True),),
    )


def _strings(items: Sequence[str]) -> str:
    return f"[{', '.join(python_string(item) for item in items)}]"


def _inline(constraint: Constraint) -> Call:
    """Give a constraint in a `create_table` call."""
    name = f"name={_name(constraint.name)}"
    match constraint.kind:
        case "pk":
            return Call(
                "sa.PrimaryKeyConstraint",
                (*(python_string(item) for item in constraint.columns), name),
            )
        case "uq":
            return Call("sa.UniqueConstraint", (python_string(constraint.columns[0]), name))
        case "fk":
            assert constraint.references is not None
            target = f"{constraint.references.table}.{constraint.references.column}"
            return Call(
                "sa.ForeignKeyConstraint",
                (_strings(constraint.columns), _strings([target]), name),
            )
        case "ck":
            return Call("sa.CheckConstraint", (_values(constraint), name))


def _create(constraint: Constraint) -> Call:
    """Give a statement that adds a constraint to a table that exists."""
    name = _name(constraint.name)
    table = python_string(constraint.table)
    match constraint.kind:
        case "pk":
            return Call("op.create_primary_key", (name, table, _strings(constraint.columns)))
        case "uq":
            return Call("op.create_unique_constraint", (name, table, _strings(constraint.columns)))
        case "fk":
            assert constraint.references is not None
            return Call(
                "op.create_foreign_key",
                (
                    name,
                    table,
                    python_string(constraint.references.table),
                    _strings(constraint.columns),
                    _strings([constraint.references.column]),
                ),
            )
        case "ck":
            return Call("op.create_check_constraint", (name, table, _values(constraint)))


_DROP_TYPES: Final = {"pk": "primary", "uq": "unique", "fk": "foreignkey", "ck": "check"}


def _create_table(table: Table, pending: set[str]) -> Call:
    """Give the `create_table` statement of a new table.

    A foreign key to a table in `pending`, which the migration creates
    later, is not in the statement. The migration adds it after the tables.
    """
    items: list[Call | str] = [python_string(table.name)]
    items.extend(_column(column) for column in table.columns)
    items.extend(
        _inline(item)
        for item in constraints(table)
        if item.references is None or item.references.table not in pending
    )
    return Call("op.create_table", tuple(items))


def _alter(item: AlteredColumn) -> Call:
    arguments: list[Call | str] = [python_string(item.table), python_string(item.column.name)]
    if item.type_changed and item.column.type is not None:
        arguments.append(f"type_={_type(item.column)}")
        using = f'"{item.column.name}"::{item.column.type.postgresql}'
        arguments.append(f"postgresql_using={python_string(using)}")
    if item.nullable_changed:
        arguments.append(f"nullable={item.column.nullable}")
    return Call("op.alter_column", tuple(arguments))


# trace: PRD-APP-124, PRD-APP-127
def upgrade_statements(changes: Changes) -> list[str]:
    """Give the lines of the body of the function `upgrade`, in the order of `Changes`."""
    calls: list[Call] = []
    calls.extend(
        Call("op.rename_table", (python_string(item.old), python_string(item.new)))
        for item in changes.renamed_tables
    )
    calls.extend(
        Call(
            "op.alter_column",
            (
                python_string(item.table),
                python_string(item.old),
                f"new_column_name={python_string(item.new)}",
            ),
        )
        for item in changes.renamed_columns
    )
    calls.extend(
        Call(
            "rename_constraint",
            (python_string(item.table), python_string(item.old), python_string(item.new)),
        )
        for item in changes.renamed_constraints
    )
    calls.extend(
        Call(
            "op.drop_constraint",
            (
                _name(item.name),
                python_string(item.table),
                f"type_={python_string(_DROP_TYPES[item.kind])}",
            ),
        )
        for item in changes.dropped_constraints
    )
    calls.extend(
        Call("op.drop_column", (python_string(table), python_string(column)))
        for table, column in changes.dropped_columns
    )
    calls.extend(
        Call("op.drop_table", (python_string(table.name),)) for table in changes.dropped_tables
    )
    pending = {table.name for table in changes.created_tables}
    for table in changes.created_tables:
        pending.discard(table.name)
        calls.append(_create_table(table, pending))
    calls.extend(
        Call("op.add_column", (python_string(table), _column(column)))
        for table, column in changes.added_columns
    )
    calls.extend(_alter(item) for item in changes.altered_columns)
    calls.extend(_create(item) for item in changes.created_constraints)
    lines: list[str] = []
    for call in calls:
        lines.extend(code_lines(call, 1))
    return lines
