"""Tests of the schema snapshot and the Alembic migrations of the FastAPI generator (story #85).

The tests generate the project of a test model into a temporary folder,
change the model and generate again. The CI job "FastAPI golden project"
applies the migrations of the golden project to PostgreSQL.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.config import Configuration, parse_configuration
from dsml.database.migration import Changes, compare, constraints, convention_name
from dsml.database.schema import Column, ColumnType, ForeignKey, Schema, Table
from dsml.database.snapshot import SNAPSHOT_PATH, read_snapshot, snapshot_bytes
from dsml.errors import ToolchainError
from dsml.generate.fastapi import FastApiGenerator
from dsml.generate.fastapi_migrations import (
    Call,
    code_lines,
    python_string,
    revision_id,
    upgrade_statements,
)
from dsml.generate.generators import collect
from dsml.generate.writer import OutputFile, apply_plan, make_plan
from dsml.ir.model import Ir
from dsml.library import library_document

VERSIONS = "app/migrations/versions"
HEAD = """package Shop {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
"""
FIRST = (
    HEAD
    + """
    enum def OrderStatus { open; shipped; }
    #Entity part def Customer {
        #Key attribute id : Uuid [1];
        attribute name : String [1] { @FieldRules { maxLength = 80; } }
        ref favourite : Order [0..1];
    }
    #Entity part def Tag { #Key attribute code : String [1] { @FieldRules { maxLength = 20; } } }
    #Entity part def Order {
        #Key attribute number : Integer [1];
        attribute status : OrderStatus [1];
        attribute note : String [0..1];
        ref customer : Customer [1];
        ref tags : Tag [*];
    }
    #Application part shopApi {
        :>> target = Target::fastapi;
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
        attribute name : String [0..1] { @FieldRules { maxLength = 120; } }
        ref favourite : Order [0..1];
    }
    #Entity part def Tag { #Key attribute code : String [1] { @FieldRules { maxLength = 20; } } }
    #Entity part def Order {
        #Key attribute number : Integer [1];
        attribute status : OrderStatus [1];
        attribute remark : String [0..1] { @Destructive { renamedFrom = "note"; } }
        attribute total : Decimal [0..1];
        ref customer : Client [1];
        ref tags : Tag [*];
    }
    #Entity part def Invoice {
        #Key attribute id : Uuid [1];
        ref order : Order [1];
    }
    #Application part shopApi {
        :>> target = Target::fastapi;
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
        attribute name : String [1] { @FieldRules { maxLength = 80; } }
        ref favourite : Order [0..1];
    }
    #Entity DESTRUCTIVE_ORDER part def Order {
        #Key attribute number : Integer [1];
        attribute status : OrderStatus [1];
        ref customer : Customer [1];
    }
    #Application DESTRUCTIVE_APP part shopApi {
        :>> target = Target::fastapi;
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
        'schema = 1\n\n[applications.shopApi]\noutput = "app"\n', root / "dsml.toml"
    )


def _generate(engine: Engine, text: str, root: Path) -> list[OutputFile]:
    """Generate the project of the model into `root`. Give the output files."""
    files = collect([FastApiGenerator()], _ir(engine, text), _configuration(root), None)
    apply_plan(root, make_plan(root, files, None))
    return files


def _migrations(root: Path) -> dict[str, bytes]:
    folder = root / VERSIONS
    return {path.name: path.read_bytes() for path in sorted(folder.glob("*_gen.py"))}


def _revision(content: bytes, name: str = "revision") -> str:
    match = re.search(rf'^{name}(?:: str \| None)? = "?([0-9a-f]+|None)"?$', content.decode(), re.M)
    assert match is not None
    return match.group(1)


# trace: PRD-APP-124, PRD-APP-125
def test_first_migration_creates_the_tables_and_the_snapshot(
    rule_engine: Engine, tmp_path: Path
) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    migrations = _migrations(tmp_path)
    assert list(migrations) == ["0001_create_tables_gen.py"]
    text = migrations["0001_create_tables_gen.py"].decode()
    assert "down_revision: str | None = None\n" in text
    # Each table comes after the tables that it refers to. The cycle between
    # customer and order gets its foreign key after the tables.
    created = re.findall(r'op\.create_table\(\n        "(\w+)"', text)
    assert created == ["tag", "customer", "order", "order_tags"]
    assert text.index('"order_tags",') < text.index("op.create_foreign_key(")
    assert '"fk_customer_favourite_number_order"' in text
    snapshot = read_snapshot(tmp_path / "app")
    assert snapshot is not None
    assert [table.name for table in snapshot.tables] == ["customer", "order", "order_tags", "tag"]
    assert (tmp_path / "app" / SNAPSHOT_PATH).read_bytes() == snapshot_bytes(snapshot)


# trace: PRD-APP-124, PRD-APP-126
def test_model_change_gives_one_new_migration_and_keeps_the_old_one(
    rule_engine: Engine, tmp_path: Path
) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    first = _migrations(tmp_path)
    old_snapshot = (tmp_path / "app" / SNAPSHOT_PATH).read_bytes()
    files = collect([FastApiGenerator()], _ir(rule_engine, SECOND), _configuration(tmp_path), None)
    plan = make_plan(tmp_path, files, None)
    changes = {str(change) for change in plan.changes}
    assert f"add {VERSIONS}/0002_change_schema_gen.py" in changes
    assert f"change app/{SNAPSHOT_PATH}" in changes
    assert not [change for change in changes if "0001" in change]
    apply_plan(tmp_path, plan)
    second = _migrations(tmp_path)
    assert list(second) == ["0001_create_tables_gen.py", "0002_change_schema_gen.py"]
    assert second["0001_create_tables_gen.py"] == first["0001_create_tables_gen.py"]
    assert _revision(second["0002_change_schema_gen.py"], "down_revision") == _revision(
        first["0001_create_tables_gen.py"]
    )
    assert (tmp_path / "app" / SNAPSHOT_PATH).read_bytes() != old_snapshot
    text = second["0002_change_schema_gen.py"].decode()
    for statement in (
        'op.rename_table("customer", "client")',
        'op.alter_column("order", "note", new_column_name="remark")',
        'rename_constraint("client", "pk_customer", "pk_client")',
        '"order", "fk_order_customer_id_customer", "fk_order_customer_id_client"',
        'op.drop_constraint(op.f("ck_order_status_values"), "order", type_="check")',
        'op.add_column("order", sa.Column("total", sa.Numeric(18, 4), nullable=True))',
        "type_=sa.String(120),",
        "postgresql_using='\"name\"::VARCHAR(120)',",
        'sa.column("status").in_(("open", "shipped", "cancelled")),',
        '["order_number"], ["order.number"], name=op.f("fk_invoice_order_number_order")',
    ):
        assert statement in text, statement


# trace: PRD-APP-124
def test_no_change_gives_no_migration(rule_engine: Engine, tmp_path: Path) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    files = collect([FastApiGenerator()], _ir(rule_engine, FIRST), _configuration(tmp_path), None)
    assert make_plan(tmp_path, files, None).changes == ()
    assert list(_migrations(tmp_path)) == ["0001_create_tables_gen.py"]


# trace: PRD-APP-125, PRD-CORE-028, PRD-CORE-033
def test_two_runs_give_the_same_revision_id(rule_engine: Engine, tmp_path: Path) -> None:
    _generate(rule_engine, FIRST, tmp_path / "a")
    _generate(rule_engine, FIRST, tmp_path / "b")
    first = _migrations(tmp_path / "a")
    assert first == _migrations(tmp_path / "b")
    content = first["0001_create_tables_gen.py"]
    revision = _revision(content)
    assert len(revision) == 12
    draft = content.replace(revision.encode(), b"0" * 12)
    assert revision_id(1, draft) == revision


# trace: PRD-APP-125
def test_revision_id_comes_from_the_number_and_the_content() -> None:
    assert revision_id(1, b"a\n") == revision_id(1, b"a\n")
    assert revision_id(1, b"a\n") != revision_id(2, b"a\n")
    assert revision_id(1, b"a\n") != revision_id(1, b"b\n")
    assert re.fullmatch(r"[0-9a-f]{12}", revision_id(1, b"a\n"))


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
        collect([FastApiGenerator()], ir, _configuration(tmp_path), None)


# trace: PRD-APP-127
def test_drop_with_destructive_metadata_drops_the_tables_and_the_column(
    rule_engine: Engine, tmp_path: Path
) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    _generate(rule_engine, _drops(order=True, application=True), tmp_path)
    text = _migrations(tmp_path)["0002_change_schema_gen.py"].decode()
    assert "import sqlalchemy" not in text
    assert (
        '    op.drop_constraint(op.f("fk_order_tags_tags_code_tag"), "order_tags", '
        'type_="foreignkey")\n'
        '    op.drop_column("order", "note")\n'
        '    op.drop_table("order_tags")\n'
        '    op.drop_table("tag")\n'
    ) in text


# trace: PRD-CORE-035
def test_migrations_and_env_pass_ruff(rule_engine: Engine, tmp_path: Path) -> None:
    for text in (FIRST, SECOND, _drops(order=True, application=True)):
        _generate(rule_engine, text, tmp_path)
    assert len(_migrations(tmp_path)) == 3
    for command in (["format", "--check"], ["check"]):
        result = subprocess.run(
            [sys.executable, "-m", "ruff", *command, "--no-cache", "migrations"],
            capture_output=True,
            text=True,
            cwd=tmp_path / "app",
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_migrations_with_no_snapshot_are_an_error(rule_engine: Engine, tmp_path: Path) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    (tmp_path / "app" / SNAPSHOT_PATH).unlink()
    with pytest.raises(ToolchainError, match="there is no schema snapshot"):
        collect([FastApiGenerator()], _ir(rule_engine, FIRST), _configuration(tmp_path), None)


def test_snapshot_with_no_migration_is_an_error(rule_engine: Engine, tmp_path: Path) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    for path in (tmp_path / VERSIONS).iterdir():
        path.unlink()
    with pytest.raises(ToolchainError, match="has no migration"):
        collect([FastApiGenerator()], _ir(rule_engine, FIRST), _configuration(tmp_path), None)


def test_two_migrations_with_one_number_are_an_error(rule_engine: Engine, tmp_path: Path) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    folder = tmp_path / VERSIONS
    (folder / "0001_other_gen.py").write_bytes((folder / "0001_create_tables_gen.py").read_bytes())
    with pytest.raises(ToolchainError, match="have the same number"):
        collect([FastApiGenerator()], _ir(rule_engine, FIRST), _configuration(tmp_path), None)


def test_migration_with_no_revision_is_an_error(rule_engine: Engine, tmp_path: Path) -> None:
    _generate(rule_engine, FIRST, tmp_path)
    (tmp_path / VERSIONS / "0001_create_tables_gen.py").write_text("x = 1\n")
    with pytest.raises(ToolchainError, match="has no line"):
        collect([FastApiGenerator()], _ir(rule_engine, FIRST), _configuration(tmp_path), None)


# trace: PRD-APP-120
def test_long_constraint_names_are_shortened_as_sqlalchemy_does() -> None:
    # SQLAlchemy 2.1 gives this name to the check constraint of the column
    # in PostgreSQL.
    name = (
        "ck_long_entity_name_for_the_truncation_of_constraint_names_"
        "colour_of_the_very_long_entity_name_for_the_truncation_test_values"
    )
    assert convention_name(name) == "ck_long_entity_name_for_the_truncation_of_constraint_na_1ca4"
    assert convention_name("pk_order") == "pk_order"


def _table(name: str, *columns: Column) -> Table:
    return Table(name, tuple(sorted(columns, key=lambda column: column.name)))


UUID = ColumnType("Uuid")
STATUS = ColumnType("Enumeration", values=("open", "shipped"))


# trace: PRD-APP-124
def test_same_schemas_give_no_change() -> None:
    schema = Schema((_table("a", Column("id", primary_key=True, type=UUID)),))
    assert compare(schema, schema).empty
    assert compare(schema, schema) == Changes()


# trace: PRD-APP-124
def test_other_order_of_values_gives_no_change() -> None:
    old = Schema((_table("a", Column("s", type=STATUS)),))
    new = Schema(
        (_table("a", Column("s", type=ColumnType("Enumeration", values=("shipped", "open")))),)
    )
    assert compare(old, new).empty


# trace: PRD-APP-124
def test_new_primary_key_drops_the_old_key_first() -> None:
    old = Schema(
        (_table("a", Column("id", primary_key=True, type=UUID), Column("code", type=UUID)),)
    )
    new = Schema(
        (_table("a", Column("id", type=UUID), Column("code", primary_key=True, type=UUID)),)
    )
    changes = compare(old, new)
    assert [item.name for item in changes.dropped_constraints] == ["pk_a"]
    assert [(item.name, item.columns) for item in changes.created_constraints] == [
        ("pk_a", ("code",))
    ]
    assert upgrade_statements(changes) == [
        '    op.drop_constraint(op.f("pk_a"), "a", type_="primary")',
        '    op.create_primary_key(op.f("pk_a"), "a", ["code"])',
    ]


# trace: PRD-APP-122
def test_constraints_of_a_join_table() -> None:
    table = _table(
        "a_b",
        Column("a_id", primary_key=True, references=ForeignKey("a", "id"), type=UUID),
        Column("b_id", primary_key=True, references=ForeignKey("b", "id"), type=UUID),
    )
    assert [(item.name, item.columns) for item in constraints(table)] == [
        ("pk_a_b", ("a_id", "b_id")),
        ("fk_a_b_a_id_a", ("a_id",)),
        ("fk_a_b_b_id_b", ("b_id",)),
    ]


# trace: PRD-CORE-035
def test_code_lines_give_the_form_of_ruff_format() -> None:
    values = tuple(python_string(f"value_{index}") for index in range(12))
    call = Call(
        "op.create_check_constraint",
        ('op.f("ck_a_s_values")', '"a"', Call('sa.column("s").in_', (Call("", values, True),))),
    )
    assert code_lines(call, 1) == [
        "    op.create_check_constraint(",
        '        op.f("ck_a_s_values"),',
        '        "a",',
        '        sa.column("s").in_(',
        "            (",
        *(f"                {value}," for value in values),
        "            )",
        "        ),",
        "    )",
    ]
    assert code_lines(Call("NAMES = ", ("a",), True), 0) == ["NAMES = (a,)"]
    assert python_string('"a"::TEXT') == "'\"a\"::TEXT'"
    assert python_string("a") == '"a"'
