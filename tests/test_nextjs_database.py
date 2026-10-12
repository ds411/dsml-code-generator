"""Tests of the Drizzle schema and migrations of the Next.js generator (story #182).

The golden files in `tests/golden/nextjs/order-web/` hold the database files
of the order web: `src/shared/db/`, `migrations/`, `migrate.gen.mjs`,
`standalone-migrate.gen.mjs` and `.dsml/schema-snapshot.json`. Write them
again with `uv run python scripts/write_golden_nextjs.py`.

The other tests generate the project of a test model into a temporary
folder, change the model and generate again. The CI job "Next.js golden
project" applies the golden migrations to PostgreSQL 18 two times, with the
container image of the golden project.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.config import Configuration, parse_configuration
from dsml.database.drizzle import BREAKPOINT, identifier, literal, sql_statements
from dsml.database.migration import compare
from dsml.database.schema import Column, ColumnType, ForeignKey, Schema, Table
from dsml.database.snapshot import SNAPSHOT_PATH, read_snapshot, snapshot_bytes
from dsml.errors import ToolchainError
from dsml.generate.generators import collect
from dsml.generate.header import FileType, header
from dsml.generate.nextjs import FIXED_NAMES, NextjsGenerator
from dsml.generate.nextjs_database import JOURNAL_PATH, table_lines, table_variable
from dsml.generate.writer import OutputFile, apply_plan, is_generated_name, make_plan
from dsml.ir.model import Ir
from dsml.library import library_document

ROOT = Path(__file__).resolve().parent.parent
WEB_MODEL = ROOT / "docs" / "model" / "examples" / "order-web" / "order-web.sysml"
GOLDEN = ROOT / "tests" / "golden" / "nextjs" / "order-web"
APP = "OrderWeb::orderWeb"
PRETTIER = ROOT / "node_modules" / "prettier" / "bin" / "prettier.cjs"

DATABASE_PATHS = (
    ".dsml/",
    "migrate.gen.mjs",
    "migrations/",
    "src/shared/db/",
    "standalone-migrate.gen.mjs",
)
"""The paths of the files of the database part in the output folder."""

MIGRATIONS = "web/migrations"
HEAD = """package Shop {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 1; }
"""
FIRST = (
    HEAD
    + """
    enum def OrderStatus { open; shipped; }
    #Entity part def Customer {
        #Key attribute id : Uuid [1];
        attribute name : String [1] { @FieldRules { maxLength = 80; unique = true; } }
        attribute born : Date [0..1];
        ref favourite : Order [0..1];
    }
    #Entity part def Tag { #Key attribute code : String [1] { @FieldRules { maxLength = 20; } } }
    #Entity part def Order {
        #Key attribute number : Integer [1];
        attribute status : OrderStatus [1];
        attribute note : String [0..1];
        attribute placedAt : DateTime [1];
        attribute paid : Boolean [1];
        attribute weight : Real [0..1];
        ref customer : Customer [1];
        ref tags : Tag [*];
    }
    #Application part shopWeb {
        :>> target = Target::nextjs;
        #Exposed part orders : Order [*];
    }
}
"""
)
"""The first model. Customer and Order refer to each other in a cycle."""

SECOND = (
    HEAD
    + """
    enum def OrderStatus { open; shipped; cancelled; }
    #Entity part def Client {
        @Destructive { renamedFrom = "Customer"; }
        #Key attribute id : Uuid [1];
        attribute name : String [0..1] { @FieldRules { maxLength = 120; unique = true; } }
        attribute born : Date [0..1];
        ref favourite : Order [0..1];
    }
    #Entity part def Tag { #Key attribute code : String [1] { @FieldRules { maxLength = 20; } } }
    #Entity part def Order {
        #Key attribute number : Integer [1];
        attribute status : OrderStatus [1];
        attribute remark : String [0..1] { @Destructive { renamedFrom = "note"; } }
        attribute placedAt : DateTime [1];
        attribute paid : Boolean [1];
        attribute weight : Real [0..1];
        attribute total : Decimal [0..1];
        ref customer : Client [1];
        ref tags : Tag [*];
    }
    #Entity part def Invoice {
        #Key attribute id : Uuid [1];
        ref order : Order [1];
    }
    #Application part shopWeb {
        :>> target = Target::nextjs;
        #Exposed part orders : Order [*];
        #Exposed part invoices : Invoice [*];
    }
}
"""
)
"""The second model: renames, a new value, a new type, a new column and a new table."""

DROPS = """
    enum def OrderStatus { open; shipped; }
    #Entity part def Customer {
        #Key attribute id : Uuid [1];
        attribute name : String [1] { @FieldRules { maxLength = 80; unique = true; } }
        attribute born : Date [0..1];
        ref favourite : Order [0..1];
    }
    #Entity DESTRUCTIVE_ORDER part def Order {
        #Key attribute number : Integer [1];
        attribute status : OrderStatus [1];
        attribute placedAt : DateTime [1];
        attribute paid : Boolean [1];
        attribute weight : Real [0..1];
        ref customer : Customer [1];
    }
    #Application DESTRUCTIVE_APP part shopWeb {
        :>> target = Target::nextjs;
        #Exposed part orders : Order [*];
    }
}
"""
"""A model that drops the column `order.note` and the tables `order_tags` and `tag`."""


def _ir(engine: Engine, text: str) -> Ir:
    parsed = engine.parse_texts([library_document(), ("shop.sysml", text)])
    assert [str(item) for item in parsed.diagnostics] == []
    return build_ir(parsed, ["shop.sysml"])


def _drops(order: bool, application: bool) -> str:
    text = DROPS.replace("DESTRUCTIVE_ORDER", "#Destructive" if order else "")
    return HEAD + text.replace("DESTRUCTIVE_APP", "#Destructive" if application else "")


def _configuration(root: Path) -> Configuration:
    return parse_configuration(
        'schema = 1\n\n[applications.shopWeb]\noutput = "web"\n', root / "dsml.toml"
    )


def _generate(engine: Engine, text: str, root: Path) -> list[OutputFile]:
    """Generate the project of the model into `root`. Give the output files."""
    files = collect([NextjsGenerator()], _ir(engine, text), _configuration(root), None)
    apply_plan(root, make_plan(root, files, None))
    return files


def _migrations(root: Path) -> dict[str, bytes]:
    folder = root / MIGRATIONS
    return {path.name: path.read_bytes() for path in sorted(folder.glob("*.gen.sql"))}


def _journal(root: Path) -> dict[str, object]:
    return json.loads((root / "web" / JOURNAL_PATH).read_text(encoding="utf-8"))


def _database_files(files: dict[str, bytes]) -> dict[str, bytes]:
    return {path: content for path, content in files.items() if path.startswith(DATABASE_PATHS)}


@pytest.fixture(scope="module")
def web_ir() -> Ir:
    """Make the IR of the order web model one time for the tests of this module."""
    from dsml.adapter.convert import make_ir

    return make_ir([WEB_MODEL], ROOT)


# trace: PRD-CORE-030, PRD-APP-330, PRD-APP-331, PRD-APP-332
def test_database_files_of_the_order_web_agree_with_the_golden_files(
    web_ir: Ir, tmp_path: Path
) -> None:
    configuration = parse_configuration(
        'schema = 1\n\n[applications.orderWeb]\noutput = "order-web"\n', tmp_path / "dsml.toml"
    )
    files = collect([NextjsGenerator()], web_ir, configuration, None)
    output = _database_files({file.path.removeprefix("order-web/"): file.content for file in files})
    golden = _database_files(
        {
            path.relative_to(GOLDEN).as_posix(): path.read_bytes()
            for path in sorted(GOLDEN.rglob("*"))
            if path.is_file()
        }
    )
    assert output == golden, (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_nextjs.py and examine the differences."
    )
    assert sorted(output) == [
        ".dsml/schema-snapshot.json",
        "migrate.gen.mjs",
        "migrations/0001_create_order.gen.sql",
        "migrations/meta/_journal.json",
        "src/shared/db/client.server.gen.ts",
        "src/shared/db/index.gen.ts",
        "src/shared/db/index.server.gen.ts",
        "src/shared/db/index.server.ts",
        "src/shared/db/index.ts",
        "src/shared/db/schema.gen.ts",
        "standalone-migrate.gen.mjs",
    ]


# trace: PRD-APP-121, PRD-APP-330
def test_schema_of_the_order_web_has_the_type_map_and_the_constraint_names() -> None:
    schema = (GOLDEN / "src/shared/db/schema.gen.ts").read_text(encoding="utf-8")
    assert schema.startswith(header(FileType.TYPESCRIPT, ["OrderWeb::Order", APP]))
    for line in (
        'export const orderTable = pgTable(\n  "order",',
        '    id: uuid("id").notNull(),',
        '    note: varchar("note", { length: 500 }),',
        '      enum: ["open", "shipped", "cancelled"],',
        '    total: numeric("total", { precision: 18, scale: 4 }).notNull(),',
        '    primaryKey({ name: "pk_order", columns: [table.id] }),',
        '      "ck_order_status_values",',
        "      sql`${table.status} IN ('open', 'shipped', 'cancelled')`,",
        "export type OrderRow = typeof orderTable.$inferSelect;",
        "export type NewOrderRow = typeof orderTable.$inferInsert;",
    ):
        assert line in schema, line
    migration = (GOLDEN / "migrations/0001_create_order.gen.sql").read_text(encoding="utf-8")
    for line in (
        '  "status" VARCHAR(64) NOT NULL,',
        '  "total" NUMERIC(18, 4) NOT NULL,',
        '  CONSTRAINT "pk_order" PRIMARY KEY ("id"),',
        "  CONSTRAINT \"ck_order_status_values\" CHECK (\"status\" IN ('open', 'shipped', "
        "'cancelled'))",
    ):
        assert line in migration, line


# trace: PRD-APP-128, PRD-APP-301, PRD-APP-332
def test_migration_command_uses_the_drizzle_migrator_and_the_driver_pg() -> None:
    command = (GOLDEN / "migrate.gen.mjs").read_text(encoding="utf-8")
    assert command.startswith(header(FileType.JAVASCRIPT, [APP]))
    assert 'import { migrate } from "drizzle-orm/node-postgres/migrator";' in command
    assert 'import pg from "pg";' in command
    assert "No migration was applied." in command
    client = (GOLDEN / "src/shared/db/client.server.gen.ts").read_text(encoding="utf-8")
    assert 'import "server-only";' in client
    assert 'import { Pool, type PoolConfig } from "pg";' in client
    for variable in ("HOST", "PORT", "NAME", "USER", "PASSWORD", "SSL_MODE"):
        assert f"DATABASE_{variable}" in command, variable
        assert f"DATABASE_{variable}" in client, variable
    assert (
        (GOLDEN / "src/shared/db/index.server.gen.ts")
        .read_text(encoding="utf-8")
        .endswith('export * from "./client.server.gen";\n')
    )
    dockerfile = (GOLDEN / "Dockerfile").read_text(encoding="utf-8")
    assert "pnpm build && node standalone-migrate.gen.mjs\n" in dockerfile
    assert "COPY --from=build /srv/migrations ./migrations\n" in dockerfile


# trace: PRD-APP-332, PRD-APP-334, PRD-CORE-039
def test_migration_files_have_generated_names() -> None:
    for path in ("migrations/0001_create_order.gen.sql", JOURNAL_PATH, "migrate.gen.mjs"):
        assert is_generated_name(f"apps/web/{path}", FIXED_NAMES), path
    assert not is_generated_name("apps/web/migrations/meta/0000_snapshot.json", FIXED_NAMES)


# trace: PRD-APP-124, PRD-APP-125, PRD-APP-331, PRD-APP-332
def test_first_migration_creates_the_tables_the_journal_and_the_snapshot(
    rule_engine: Engine, tmp_path: Path
) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    migrations = _migrations(tmp_path)
    assert list(migrations) == ["0001_create_tables.gen.sql"]
    text = migrations["0001_create_tables.gen.sql"].decode()
    assert text.startswith(header(FileType.SQL, ["Shop::shopWeb"]) + "-- Migration 0001 ")
    # Each table comes after the tables that it refers to. The cycle between
    # customer and order gets its foreign key after the tables.
    created = re.findall(r'^CREATE TABLE "(\w+)"', text, re.MULTILINE)
    assert created == ["tag", "customer", "order", "order_tags"]
    assert text.index('CREATE TABLE "order_tags"') < text.index(
        'ALTER TABLE "customer" ADD CONSTRAINT "fk_customer_favourite_number_order"'
    )
    assert text.count(f"\n{BREAKPOINT}\n") == 4
    assert '  CONSTRAINT "uq_customer_name" UNIQUE ("name")\n);\n' in text
    assert _journal(tmp_path) == {
        "version": "7",
        "dialect": "postgresql",
        "entries": [
            {
                "idx": 0,
                "version": "7",
                "when": 1,
                "tag": "0001_create_tables.gen",
                "breakpoints": True,
            }
        ],
    }
    snapshot = read_snapshot(tmp_path / "web")
    assert snapshot is not None
    assert [table.name for table in snapshot.tables] == ["customer", "order", "order_tags", "tag"]
    assert (tmp_path / "web" / SNAPSHOT_PATH).read_bytes() == snapshot_bytes(snapshot)


# trace: PRD-APP-124, PRD-APP-126, PRD-APP-127, PRD-APP-332
def test_model_change_gives_a_second_migration_and_keeps_the_first(
    rule_engine: Engine, tmp_path: Path
) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    first = _migrations(tmp_path)
    files = collect([NextjsGenerator()], _ir(rule_engine, SECOND), _configuration(tmp_path), None)
    plan = make_plan(tmp_path, files, None)
    changes = {str(change) for change in plan.changes}
    assert f"add {MIGRATIONS}/0002_change_schema.gen.sql" in changes
    assert f"change web/{JOURNAL_PATH}" in changes
    assert f"change web/{SNAPSHOT_PATH}" in changes
    assert not [change for change in changes if "0001" in change]
    apply_plan(tmp_path, plan)
    second = _migrations(tmp_path)
    assert list(second) == ["0001_create_tables.gen.sql", "0002_change_schema.gen.sql"]
    assert second["0001_create_tables.gen.sql"] == first["0001_create_tables.gen.sql"]
    entries = cast(list[dict[str, object]], _journal(tmp_path)["entries"])
    assert [(item["idx"], item["when"], item["tag"]) for item in entries] == [
        (0, 1, "0001_create_tables.gen"),
        (1, 2, "0002_change_schema.gen"),
    ]
    text = second["0002_change_schema.gen.sql"].decode()
    assert "-- Migration 0002 of the application shopWeb.\n" in text
    for statement in (
        'ALTER TABLE "customer" RENAME TO "client";',
        'ALTER TABLE "order" RENAME COLUMN "note" TO "remark";',
        'ALTER TABLE "client" RENAME CONSTRAINT "pk_customer" TO "pk_client";',
        'ALTER TABLE "order" RENAME CONSTRAINT "fk_order_customer_id_customer" '
        'TO "fk_order_customer_id_client";',
        'ALTER TABLE "order" DROP CONSTRAINT "ck_order_status_values";',
        'ALTER TABLE "order" ADD COLUMN "total" NUMERIC(18, 4);',
        'ALTER TABLE "client" ALTER COLUMN "name" SET DATA TYPE VARCHAR(120) '
        'USING "name"::VARCHAR(120);',
        'ALTER TABLE "client" ALTER COLUMN "name" DROP NOT NULL;',
        'ALTER TABLE "order" ADD CONSTRAINT "ck_order_status_values" '
        "CHECK (\"status\" IN ('open', 'shipped', 'cancelled'));",
        '  CONSTRAINT "fk_invoice_order_number_order" FOREIGN KEY ("order_number") '
        'REFERENCES "order" ("number")',
    ):
        assert statement in text, statement


# trace: PRD-APP-124
def test_no_change_gives_no_migration(rule_engine: Engine, tmp_path: Path) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    files = collect([NextjsGenerator()], _ir(rule_engine, FIRST), _configuration(tmp_path), None)
    assert make_plan(tmp_path, files, None).changes == ()
    assert list(_migrations(tmp_path)) == ["0001_create_tables.gen.sql"]


# trace: PRD-APP-125, PRD-CORE-028, PRD-CORE-033
def test_two_runs_give_the_same_migration(rule_engine: Engine, tmp_path: Path) -> None:
    _generate(rule_engine, FIRST, tmp_path / "a")
    _generate(rule_engine, FIRST, tmp_path / "b")
    assert _migrations(tmp_path / "a") == _migrations(tmp_path / "b")
    assert _journal(tmp_path / "a") == _journal(tmp_path / "b")


# trace: PRD-APP-127
@pytest.mark.parametrize(
    ("order", "application", "message"),
    [
        (False, True, r'drop the column "order\.note"'),
        (True, False, 'drop the table "order_tags"'),
    ],
)
def test_drop_with_no_destructive_metadata_is_an_error(
    rule_engine: Engine, tmp_path: Path, order: bool, application: bool, message: str
) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    ir = _ir(rule_engine, _drops(order, application))
    with pytest.raises(ToolchainError, match=message):
        collect([NextjsGenerator()], ir, _configuration(tmp_path), None)


# trace: PRD-APP-127
def test_drop_with_destructive_metadata_drops_the_tables_and_the_column(
    rule_engine: Engine, tmp_path: Path
) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    _generate(rule_engine, _drops(order=True, application=True), tmp_path)
    text = _migrations(tmp_path)["0002_change_schema.gen.sql"].decode()
    assert (
        'ALTER TABLE "order_tags" DROP CONSTRAINT "fk_order_tags_tags_code_tag";\n'
        f"{BREAKPOINT}\n"
        'ALTER TABLE "order" DROP COLUMN "note";\n'
        f"{BREAKPOINT}\n"
        'DROP TABLE "order_tags";\n'
        f"{BREAKPOINT}\n"
        'DROP TABLE "tag";\n'
    ) in text


def test_migrations_with_no_snapshot_are_an_error(rule_engine: Engine, tmp_path: Path) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    (tmp_path / "web" / SNAPSHOT_PATH).unlink()
    with pytest.raises(ToolchainError, match="there is no schema snapshot"):
        collect([NextjsGenerator()], _ir(rule_engine, FIRST), _configuration(tmp_path), None)


def test_snapshot_with_no_migration_is_an_error(rule_engine: Engine, tmp_path: Path) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    for path in (tmp_path / MIGRATIONS).glob("*.gen.sql"):
        path.unlink()
    with pytest.raises(ToolchainError, match="has no migration"):
        collect([NextjsGenerator()], _ir(rule_engine, FIRST), _configuration(tmp_path), None)


def test_two_migrations_with_one_number_are_an_error(rule_engine: Engine, tmp_path: Path) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    folder = tmp_path / MIGRATIONS
    (folder / "0001_other.gen.sql").write_bytes(
        (folder / "0001_create_tables.gen.sql").read_bytes()
    )
    with pytest.raises(ToolchainError, match="have the same number"):
        collect([NextjsGenerator()], _ir(rule_engine, FIRST), _configuration(tmp_path), None)


# trace: PRD-APP-122, PRD-APP-330
def test_schema_has_the_join_tables_and_the_foreign_keys(
    rule_engine: Engine, tmp_path: Path
) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    schema = (tmp_path / "web/src/shared/db/schema.gen.ts").read_text(encoding="utf-8")
    # A table comes after the tables that it refers to. The tables of the
    # cycle between customer and order are in the order of their names.
    tables = re.findall(r"^export const (\w+) = pgTable", schema, re.MULTILINE)
    assert tables == ["tagTable", "customerTable", "orderTable", "orderTagsTable"]
    for line in (
        '    born: date("born"),',
        '    placedAt: timestamp("placed_at", { withTimezone: true }).notNull(),',
        '    number: bigint("number", { mode: "number" }).notNull(),',
        '    paid: boolean("paid").notNull(),',
        '    weight: doublePrecision("weight"),',
        '    note: text("note"),',
        '    unique("uq_customer_name").on(table.name),',
        '      name: "fk_customer_favourite_number_order",',
        "      columns: [table.favouriteNumber],",
        "      foreignColumns: [orderTable.number],",
        "      columns: [table.orderNumber, table.tagsCode],",
        "export type NewOrderTagsRow = typeof orderTagsTable.$inferInsert;",
    ):
        assert line in schema, line
    # TypeScript cannot infer the types of a cycle. The table that refers to
    # a later table gives the return type of its constraint function.
    assert schema.count("(table): PgTableExtraConfigValue[] => [") == 1
    assert "  type PgTableExtraConfigValue,\n" in schema


def _prettier(text: str, path: Path) -> str:
    node = shutil.which("node")
    if node is None or not PRETTIER.is_file():
        pytest.skip("The test needs Node.js and the Prettier of the dev tools (pnpm install).")
    path.write_text(text, encoding="utf-8")
    result = subprocess.run(
        [node, str(PRETTIER), str(path)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _uuid(name: str, primary_key: bool = False) -> Column:
    return Column(name, primary_key=primary_key, type=ColumnType("Uuid"))


# trace: PRD-CORE-035
def test_long_names_get_the_prettier_line_breaks(tmp_path: Path) -> None:
    long = "a_very_long_column_name_for_the_line_breaks_of_the_prettier_format"
    values = tuple(f"value_number_{index}" for index in range(8))
    table = Table(
        "long_table_name_of_the_prettier_test",
        (
            Column(long, type=ColumnType("Integer")),
            Column(f"{long}_xx_yy_zz", type=ColumnType("Enumeration", values=values)),
            Column(f"{long}_x", type=ColumnType("String")),
            Column("short", type=ColumnType("Enumeration", values=values)),
            Column("status", type=ColumnType("Enumeration", values=("open", "shipped"))),
            Column(f"{long}_k", primary_key=True, type=ColumnType("Uuid")),
            Column(f"{long}_u", type=ColumnType("Uuid"), unique=True),
            Column(f"{long}_r", references=ForeignKey("other", "id"), type=ColumnType("Uuid")),
        ),
    )
    other = Table("other", (_uuid("id", primary_key=True),))
    plain = Table("plain", (_uuid("id"),))
    lines: list[str] = []
    for item in (table, other, plain):
        variables = {name: table_variable(name) for name in ("other", item.name)}
        lines.extend(["", *table_lines(item, variables)[0]])
    text = "\n".join(lines[1:]) + "\n"
    assert _prettier(text, tmp_path / "schema.ts") == text


# trace: PRD-APP-124, PRD-APP-331
def test_sql_of_a_new_primary_key_and_a_quoted_name() -> None:
    uuid = ColumnType("Uuid")
    old = Schema(
        (Table("a", (Column("code", type=uuid), Column("id", primary_key=True, type=uuid))),)
    )
    new = Schema(
        (Table("a", (Column("code", primary_key=True, type=uuid), Column("id", type=uuid))),)
    )
    assert sql_statements(compare(old, new)) == [
        'ALTER TABLE "a" DROP CONSTRAINT "pk_a";',
        'ALTER TABLE "a" ADD CONSTRAINT "pk_a" PRIMARY KEY ("code");',
    ]
    assert identifier('a"b') == '"a""b"'
    assert literal("it's") == "'it''s'"
