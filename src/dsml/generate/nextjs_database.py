# trace: PRD-APP-121, PRD-APP-122, PRD-APP-124, PRD-APP-125, PRD-APP-126, PRD-APP-127
# trace: PRD-APP-128, PRD-APP-301, PRD-APP-330, PRD-APP-331, PRD-APP-332, PRD-APP-334
"""The Drizzle schema and migrations of the Next.js generator (story #182).

The Next.js generator (`dsml.generate.nextjs`) calls the function
`database_files` for each `nextjs` application. The function gives these
files:

- `src/shared/db/schema.gen.ts`: one Drizzle table for each table of the
  schema of the application (`dsml.database.schema`), with the type map of
  PRD-APP-121 and the constraint names of `dsml.database.migration`
  (PRD-APP-330).
- `src/shared/db/client.server.gen.ts`: the Drizzle database with the
  driver `pg` (PRD-APP-301, Q64). It reads the connection values from the
  environment variables at run time.
- The public API files of the segment `src/shared/db`.
- The migrations `migrations/<NNNN>_<slug>.gen.sql` and the journal
  `migrations/meta/_journal.json` that the Drizzle migrator reads
  (PRD-APP-331, PRD-APP-332, Q67).
- The schema snapshot `.dsml/schema-snapshot.json` (PRD-APP-124).
- `migrate.gen.mjs`: the migration command (PRD-APP-128, PRD-APP-332).
- `standalone-migrate.gen.mjs`: the Dockerfile runs it after `next build`.
  It copies `migrate.gen.mjs` and the files that it needs into the
  `standalone` output.

The generator compares the snapshot with the schema of the IR, as the
FastAPI generator does (`dsml.generate.fastapi_migrations`):

- If the schemas are different, the generator writes one new migration and
  the new snapshot (PRD-APP-124).
- The generator gives each old migration file to the file writer again,
  byte for byte (PRD-APP-126).
- The Drizzle migrator identifies a migration by the SHA-256 hash of its
  file. The file has the number of the migration, thus the ID comes from
  the content and the number (PRD-APP-125). The journal gives the number
  as the value `when`, not the clock (PRD-CORE-033).
- A migration drops or renames a table or a column only if the IR has the
  `#Destructive` metadata for that change (PRD-APP-127).
"""

import json
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dsml.database.drizzle import BREAKPOINT, sql_statements, summary_lines
from dsml.database.migration import Changes, Constraint, compare, constraints
from dsml.database.schema import Column, Schema, Table, application_schema
from dsml.database.snapshot import SNAPSHOT_PATH, read_snapshot, snapshot_bytes
from dsml.errors import ToolchainError
from dsml.generate.fastapi_migrations import check_destructive
from dsml.generate.header import FileType, header
from dsml.generate.names import camel_case, pascal_case
from dsml.generate.react_common import ReactContext, public_api_files
from dsml.generate.react_entities import INDENT, PRINT_WIDTH, string_literal
from dsml.generate.typescript_symbols import typescript_symbols
from dsml.generate.writer import Kind, OutputFile

SEGMENT: Final = "src/shared/db"
"""The segment of the Drizzle schema and the database client."""

MIGRATIONS_FOLDER: Final = "migrations"
"""The folder of the migration files, relative to the output folder of the application."""

JOURNAL_PATH: Final = "migrations/meta/_journal.json"
"""The journal of the Drizzle migrator. It is on the fixed-name list (PRD-APP-334, Q67)."""

JOURNAL_VERSION: Final = "7"
"""The version of the journal format that the Drizzle migrator of the baseline reads."""

MIGRATE_COMMAND: Final = "migrate.gen.mjs"
"""The migration command. The deployment runs `node migrate.gen.mjs` (PRD-APP-332, Q53)."""

EXTRA_CONFIG_TYPE: Final = "PgTableExtraConfigValue"
"""The type of a constraint of a Drizzle table."""

STANDALONE_SCRIPT: Final = "standalone-migrate.gen.mjs"
"""The script that copies the migration command into the `standalone` output."""

# The templates of the files with no data from the schema, by the path in
# the output folder.
_TEMPLATES: Final = {
    f"{SEGMENT}/client.server.gen.ts": "nextjs/db/client.server.gen.ts.j2",
    MIGRATE_COMMAND: "nextjs/db/migrate.gen.mjs.j2",
    STANDALONE_SCRIPT: "nextjs/db/standalone-migrate.gen.mjs.j2",
}

_MIGRATION_NAME: Final = re.compile(r"(?P<number>[0-9]{4})_(?P<slug>[a-z0-9_]+)\.gen\.sql")

# trace: PRD-APP-121
_BUILDERS: Final = {
    "Boolean": ("boolean", ()),
    "Date": ("date", ()),
    "DateTime": ("timestamp", (("withTimezone", "true"),)),
    "Integer": ("bigint", (("mode", '"number"'),)),
    "Real": ("doublePrecision", ()),
    "Uuid": ("uuid", ()),
}
"""The Drizzle column builder and its options for the types with no parameter.

A `BIGINT` column gives a JavaScript number. A `DATE` column gives a text
`YYYY-MM-DD`, and a `TIMESTAMPTZ` column gives a `Date`.
"""


# trace: PRD-APP-126
@dataclass(frozen=True, slots=True)
class OldMigration:
    """A migration file that the generator wrote before."""

    number: int
    path: str
    """The path in the output folder of the application."""
    content: bytes

    @property
    def tag(self) -> str:
        """Give the tag of the migration in the journal: the file name with no `.sql`."""
        return Path(self.path).name.removesuffix(".sql")


# trace: PRD-APP-124, PRD-APP-125, PRD-APP-126, PRD-APP-127, PRD-APP-128, PRD-APP-330
# trace: PRD-APP-331, PRD-APP-332
def database_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the Drizzle schema and migrations of one application."""
    schema = application_schema(context.ir, context.application.identity)
    files = [schema_file(context, schema)]
    files.extend(
        context.generated_file(
            path, template, {"application": context.application.name}, context.elements
        )
        for path, template in sorted(_TEMPLATES.items())
    )
    files.extend(
        public_api_files(context, SEGMENT, ["schema.gen"], context.elements, ["client.server.gen"])
    )
    files.extend(migration_files(context, schema))
    return files


# trace: PRD-APP-124, PRD-APP-125, PRD-APP-126, PRD-APP-127, PRD-APP-331, PRD-APP-332
def migration_files(context: ReactContext, schema: Schema) -> list[OutputFile]:
    """Give the old migrations, the new migration if the schema changed, the journal and
    the snapshot."""
    folder = context.folder
    root = context.configuration.root / folder
    snapshot = read_snapshot(root)
    old = read_migrations(root)
    if old and snapshot is None:
        raise ToolchainError(
            f"The folder {folder}{MIGRATIONS_FOLDER} has migrations, but there is no schema "
            f"snapshot {folder}{SNAPSHOT_PATH}. Restore the snapshot from Git."
        )
    if snapshot is not None and snapshot.tables and not old:
        raise ToolchainError(
            f"The schema snapshot {folder}{SNAPSHOT_PATH} has tables, but the folder "
            f"{folder}{MIGRATIONS_FOLDER} has no migration. Restore the migrations from Git."
        )
    changes = compare(snapshot or Schema(), schema)
    check_destructive(context.ir, context.application, schema, changes)
    migrations = list(old)
    if not changes.empty:
        number = old[-1].number + 1 if old else 1
        path, content = render_migration(context, changes, number)
        migrations.append(OldMigration(number, path, content))
    files = [
        OutputFile(f"{folder}{item.path}", item.content, Kind.GENERATED, context.part)
        for item in migrations
    ]
    files.append(
        OutputFile(
            f"{folder}{JOURNAL_PATH}", journal_bytes(migrations), Kind.GENERATED, context.part
        )
    )
    files.append(
        OutputFile(f"{folder}{SNAPSHOT_PATH}", snapshot_bytes(schema), Kind.GENERATED, context.part)
    )
    return files


# trace: PRD-APP-126
def read_migrations(root: Path) -> list[OldMigration]:
    """Read the migration files in the folder `migrations` of `root`, by number.

    Two files with the same number give an error.
    """
    folder = root / MIGRATIONS_FOLDER
    if not folder.is_dir():
        return []
    found: dict[int, OldMigration] = {}
    for path in sorted(folder.iterdir()):
        match = _MIGRATION_NAME.fullmatch(path.name)
        if match is None or not path.is_file():
            continue
        number = int(match.group("number"))
        relative = f"{MIGRATIONS_FOLDER}/{path.name}"
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
        found[number] = OldMigration(number, relative, content)
    return [found[number] for number in sorted(found)]


# trace: PRD-APP-125, PRD-APP-331, PRD-APP-332, PRD-CORE-033
def render_migration(context: ReactContext, changes: Changes, number: int) -> tuple[str, bytes]:
    """Give the path and the bytes of one new migration (PRD-APP-332, Q67).

    The Drizzle migrator runs the statements in one transaction. The
    comment at the top has the number of the migration.
    """
    statements = sql_statements(changes)
    content = context.engine.render_bytes(
        "nextjs/db/migration.gen.sql.j2",
        {
            "file_type": FileType.SQL.value,
            "elements": [context.application.identity],
            "application": context.application.name,
            "number": f"{number:04d}",
            "summary": summary_lines(changes),
            "statements": statements,
            "breakpoint": BREAKPOINT,
        },
    )
    return f"{MIGRATIONS_FOLDER}/{number:04d}_{changes.slug}.gen.sql", content


# trace: PRD-APP-331, PRD-APP-332, PRD-CORE-033, PRD-CORE-034
def journal_bytes(migrations: Sequence[OldMigration]) -> bytes:
    """Give the journal of the Drizzle migrator, in the Prettier format of JSON.

    The value `when` of a migration is its number. The Drizzle migrator
    applies each migration with a value `when` that is more than the value of
    the last migration in the database.
    """
    lines = ["{", f'  "version": "{JOURNAL_VERSION}",', '  "dialect": "postgresql",']
    if not migrations:
        lines.append('  "entries": []')
    else:
        lines.append('  "entries": [')
        for index, item in enumerate(migrations):
            lines.extend(
                [
                    "    {",
                    f'      "idx": {index},',
                    f'      "version": "{JOURNAL_VERSION}",',
                    f'      "when": {item.number},',
                    f'      "tag": {json.dumps(item.tag)},',
                    '      "breakpoints": true',
                    "    }" + ("," if index < len(migrations) - 1 else ""),
                ]
            )
        lines.append("  ]")
    lines.append("}")
    return ("\n".join(lines) + "\n").encode("utf-8")


# trace: PRD-APP-120, PRD-APP-121, PRD-APP-122, PRD-APP-330, PRD-TRACE-006
def schema_file(context: ReactContext, schema: Schema) -> OutputFile:
    """Give `src/shared/db/schema.gen.ts`: one Drizzle table for each table of the schema."""
    tables = ordered_tables(schema)
    variables = {table.name: table_variable(table.name) for table in tables}
    body: list[str] = []
    builders: set[str] = set()
    uses_sql = False
    symbol_elements: dict[str, tuple[str, ...]] = {}
    for index, table in enumerate(tables):
        later = {item.name for item in tables[index + 1 :]}
        lines, used = table_lines(table, variables, later)
        builders.update(used)
        uses_sql = uses_sql or "check" in used
        body.extend(["", *lines])
        if table.element is not None:
            pascal = pascal_case(table.name)
            for name in (variables[table.name], f"{pascal}Row", f"New{pascal}Row"):
                symbol_elements[name] = (table.element,)
    elements = sorted({context.application.identity, *(t.element for t in tables if t.element)})
    lines = [*_import_lines(builders, uses_sql), *body] if body else ["export {};"]
    content = (header(FileType.TYPESCRIPT, elements) + "\n".join(lines) + "\n").encode("utf-8")
    symbols = typescript_symbols(content, (context.application.identity,), symbol_elements)
    return OutputFile(
        f"{context.folder}{SEGMENT}/schema.gen.ts", content, Kind.GENERATED, context.part, symbols
    )


# trace: PRD-APP-122
def ordered_tables(schema: Schema) -> list[Table]:
    """Give the tables in an order where a table comes after the tables it refers to.

    The tables of a cycle stay in the order of their names.
    """
    remaining = {table.name: table for table in schema.tables}
    order: list[Table] = []
    while remaining:
        ready = [
            name
            for name in sorted(remaining)
            if not any(
                column.references is not None
                and column.references.table in remaining
                and column.references.table != name
                for column in remaining[name].columns
            )
        ]
        order.append(remaining.pop(ready[0] if ready else sorted(remaining)[0]))
    return order


# trace: PRD-APP-330
def table_variable(table: str) -> str:
    """Give the name of the constant of a Drizzle table, for example `orderTable`."""
    return f"{camel_case(table)}Table"


# trace: PRD-APP-121, PRD-APP-330
def column_builder(column: Column) -> tuple[str, list[tuple[str, str]]]:
    """Give the Drizzle column builder and its options for a column (PRD-APP-121)."""
    column_type = column.type
    if column_type is None:
        raise ToolchainError(
            f'The column "{column.name}" has a type that is not supported. '
            "Use a field type that STR-007 permits."
        )
    match column_type.name:
        case "String":
            if column_type.length is None:
                return "text", []
            return "varchar", [("length", str(column_type.length))]
        case "Decimal":
            return "numeric", [
                ("precision", str(column_type.precision)),
                ("scale", str(column_type.scale)),
            ]
        case "Enumeration":
            values = ", ".join(string_literal(value) for value in column_type.values)
            return "varchar", [("length", "64"), ("enum", f"[{values}]")]
        case _:
            builder, options = _BUILDERS[column_type.name]
            return builder, list(options)


# trace: PRD-APP-120, PRD-APP-121, PRD-APP-122, PRD-APP-330, PRD-CORE-035
def table_lines(
    table: Table, variables: Mapping[str, str], later: Collection[str] = ()
) -> tuple[list[str], set[str]]:
    """Give the lines of one Drizzle table and its row types, in the Prettier format.

    `later` holds the names of the tables that come after this table in the
    file. A foreign key to this table or to a later table can be a part of a
    cycle. TypeScript cannot infer the types of the tables of a cycle. Thus
    the function of the constraints then has the return type
    `PgTableExtraConfigValue[]`.

    The function also gives the names that the lines import from
    `drizzle-orm/pg-core`, and `check` for a check constraint.
    """
    variable = variables[table.name]
    used = {"pgTable"}
    extra = [_constraint_item(item, variables, used) for item in constraints(table)]
    head = "(table) =>"
    if any(
        item.references is not None
        and (item.references.table == table.name or item.references.table in later)
        for item in constraints(table)
    ):
        head = f"(table): {EXTRA_CONFIG_TYPE}[] =>"
        used.add(f"type {EXTRA_CONFIG_TYPE}")
    level = 2 if extra else 1
    columns: list[str] = []
    for column in table.columns:
        builder, options = column_builder(column)
        used.add(builder)
        chain = "" if column.nullable and not column.primary_key else ".notNull()"
        columns.extend(
            _column_lines(camel_case(column.name), builder, column.name, options, chain, level)
        )
    name = string_literal(table.name)
    if extra:
        lines = [f"export const {variable} = pgTable(", f"{INDENT}{name},", f"{INDENT}{{"]
        lines.extend(columns)
        lines.append(f"{INDENT}}},")
        lines.extend(_extra_lines(head, extra))
        lines.append(");")
    else:
        lines = [f"export const {variable} = pgTable({name}, {{", *columns, "});"]
    pascal = pascal_case(table.name)
    lines.extend(["", f"/** A row of the table {table.name}. */"])
    lines.extend(_type_lines(f"{pascal}Row", f"typeof {variable}.$inferSelect"))
    lines.extend(["", f"/** The values of a new row of the table {table.name}. */"])
    lines.extend(_type_lines(f"New{pascal}Row", f"typeof {variable}.$inferInsert"))
    return lines, used


def _type_lines(name: str, value: str) -> list[str]:
    """Give an exported type alias, with the line break of Prettier after `=` if it is long."""
    line = f"export type {name} = {value};"
    return [line] if _fits(line) else [f"export type {name} =", f"{INDENT}{value};"]


def _fits(line: str) -> bool:
    return len(line) <= PRINT_WIDTH


def _array_lines(indent: str, head: str, items: Sequence[str], end: str) -> list[str]:
    """Give an array on one line, or with one item on each line as Prettier writes it."""
    line = f"{indent}{head}[{', '.join(items)}]{end}"
    if _fits(line) or not items:
        return [line]
    return [f"{indent}{head}[", *(f"{indent}{INDENT}{item}," for item in items), f"{indent}]{end}"]


def _entry_lines(indent: str, options: Sequence[tuple[str, str]]) -> list[str]:
    """Give the entries of an object with one entry on each line."""
    lines: list[str] = []
    for key, value in options:
        if value.startswith("[") and value.endswith("]"):
            items = [item for item in value[1:-1].split(", ") if item]
            lines.extend(_array_lines(indent, f"{key}: ", items, ","))
        else:
            lines.append(f"{indent}{key}: {value},")
    return lines


def _inline_object(options: Sequence[tuple[str, str]]) -> str:
    return "{ " + ", ".join(f"{key}: {value}" for key, value in options) + " }"


def _column_lines(
    key: str,
    builder: str,
    name: str,
    options: Sequence[tuple[str, str]],
    chain: str,
    level: int,
) -> list[str]:
    """Give the lines of one column property, as Prettier writes them."""
    indent = INDENT * level
    deeper = indent + INDENT
    literal = string_literal(name)
    arguments = literal + (f", {_inline_object(options)}" if options else "")
    line = f"{indent}{key}: {builder}({arguments}){chain},"
    if _fits(line):
        return [line]
    hug = f"{indent}{key}: {builder}({literal}, {{"
    if options and _fits(hug):
        return [hug, *_entry_lines(deeper, options), f"{indent}}}){chain},"]
    lines = [f"{indent}{key}: {builder}(", f"{deeper}{literal},"]
    if options:
        inline = f"{deeper}{_inline_object(options)},"
        if _fits(inline):
            lines.append(inline)
        else:
            lines.extend([f"{deeper}{{", *_entry_lines(deeper + INDENT, options), f"{deeper}}},"])
    lines.append(f"{indent}){chain},")
    return lines


@dataclass(frozen=True, slots=True)
class _Item:
    """One item of the extra configuration of a table: one line, and the lines if it is too
    long."""

    line: str
    long: tuple[str, ...]


def _columns(names: Sequence[str]) -> list[str]:
    return [f"table.{camel_case(name)}" for name in names]


def _object_item(function: str, options: list[tuple[str, str]]) -> _Item:
    indent = INDENT * 2
    line = f"{function}({_inline_object(options)})"
    long = [f"{indent}{function}({{", *_entry_lines(indent + INDENT, options), f"{indent}}}),"]
    return _Item(line, tuple(long))


# trace: PRD-APP-120, PRD-APP-121, PRD-APP-122
def _constraint_item(constraint: Constraint, variables: Mapping[str, str], used: set[str]) -> _Item:
    """Give one constraint of the extra configuration of a Drizzle table."""
    indent = INDENT * 2
    deeper = indent + INDENT
    name = string_literal(constraint.name)
    match constraint.kind:
        case "pk":
            used.add("primaryKey")
            columns = f"[{', '.join(_columns(constraint.columns))}]"
            return _object_item("primaryKey", [("name", name), ("columns", columns)])
        case "fk":
            used.add("foreignKey")
            assert constraint.references is not None
            target = variables.get(constraint.references.table)
            if target is None:
                raise ToolchainError(
                    f'The foreign key {constraint.name} refers to the table "'
                    f'{constraint.references.table}", but the schema has no such table.'
                )
            columns = f"[{', '.join(_columns(constraint.columns))}]"
            foreign = f"[{target}.{camel_case(constraint.references.column)}]"
            return _object_item(
                "foreignKey", [("name", name), ("columns", columns), ("foreignColumns", foreign)]
            )
        case "uq":
            used.add("unique")
            column = _columns(constraint.columns)[0]
            line = f"unique({name}).on({column})"
            return _Item(line, (f"{indent}unique({name}).on(", f"{deeper}{column},", f"{indent}),"))
        case "ck":
            used.add("check")
            values = ", ".join("'" + value.replace("'", "''") + "'" for value in constraint.values)
            condition = f"sql`${{{_columns(constraint.columns)[0]}}} IN ({values})`"
            line = f"check({name}, {condition})"
            return _Item(
                line,
                (f"{indent}check(", f"{deeper}{name},", f"{deeper}{condition},", f"{indent}),"),
            )


def _extra_lines(head: str, items: Sequence[_Item]) -> list[str]:
    """Give the last argument of `pgTable`: the arrow function that gives the constraints."""
    line = f"{INDENT}{head} [{', '.join(item.line for item in items)}],"
    if _fits(line):
        return [line]
    lines = [f"{INDENT}{head} ["]
    for item in items:
        single = f"{INDENT * 2}{item.line},"
        lines.extend([single] if _fits(single) else item.long)
    lines.append(f"{INDENT}],")
    return lines


def _import_lines(builders: set[str], uses_sql: bool) -> list[str]:
    """Give the import lines of the schema file, as Prettier writes them."""
    lines: list[str] = []
    if uses_sql:
        lines.append('import { sql } from "drizzle-orm";')
    names = sorted(builders, key=lambda name: name.removeprefix("type "))
    if names:
        line = f'import {{ {", ".join(names)} }} from "drizzle-orm/pg-core";'
        if _fits(line):
            lines.append(line)
        else:
            lines.extend(
                [
                    "import {",
                    *(f"{INDENT}{name}," for name in names),
                    '} from "drizzle-orm/pg-core";',
                ]
            )
    return lines
