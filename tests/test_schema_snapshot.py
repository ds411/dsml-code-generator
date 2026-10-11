"""Tests of the database schema and the schema snapshot (story #61).

The tests get the schema of the example model and of the test model
`tests/models/ir/solution-layers.sysml`, which has relations. They also read
and write the snapshot `.dsml/schema-snapshot.json`.
"""

import json
from pathlib import Path

import pytest

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.database.schema import (
    Column,
    ColumnType,
    ForeignKey,
    Schema,
    SchemaError,
    Table,
    application_schema,
    column_type_of,
)
from dsml.database.snapshot import (
    SNAPSHOT_PATH,
    SnapshotError,
    parse_snapshot,
    read_snapshot,
    snapshot_bytes,
    write_snapshot,
)
from dsml.ir.model import Ir
from dsml.library import library_document

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = "docs/model/examples/order-service.sysml"
TEST_MODEL = "tests/models/ir/solution-layers.sysml"
RULE_SNAPSHOT = ROOT / "tests/models/rules/STR-013/reject"


def _convert(engine: Engine, file: str, text: str | None = None) -> Ir:
    source = (ROOT / file).read_text(encoding="utf-8") if text is None else text
    parsed = engine.parse_texts([library_document(), (file, source)])
    assert [str(item) for item in parsed.diagnostics] == []
    return build_ir(parsed, [file])


def _names(schema: Schema) -> dict[str, list[str]]:
    return {table.name: [column.name for column in table.columns] for table in schema.tables}


# trace: PRD-APP-120
def test_the_order_service_has_one_table(rule_engine: Engine) -> None:
    schema = application_schema(_convert(rule_engine, EXAMPLE), "OrderService::orderApi")
    assert schema == Schema(
        (
            Table(
                "order",
                (
                    Column("id", primary_key=True),
                    Column("note", nullable=True),
                    Column("status"),
                    Column("total"),
                ),
            ),
        )
    )
    order = schema.tables[0]
    assert order.element == "OrderService::Order"
    assert [column.element for column in order.columns] == [
        "OrderService::Order::id",
        "OrderService::Order::note",
        "OrderService::Order::status",
        "OrderService::Order::total",
    ]


# trace: PRD-APP-120, PRD-APP-122
def test_relations_give_foreign_keys_and_join_tables(rule_engine: Engine) -> None:
    schema = application_schema(_convert(rule_engine, TEST_MODEL), "Shop::shopApi")
    assert _names(schema) == {
        "category": ["code"],
        "product": ["category_code", "id", "label", "name", "price"],
        "product_related": ["product_id", "related_id"],
    }
    product = schema.table("product")
    assert product is not None
    assert product.column("category_code") == Column(
        "category_code", nullable=True, references=ForeignKey("category", "code")
    )
    assert product.column("label") == Column("label", nullable=True)
    label = product.column("label")
    assert label is not None
    assert label.renamed_from == "title"
    join = schema.table("product_related")
    assert join is not None
    assert join == Table(
        "product_related",
        (
            Column("product_id", primary_key=True, references=ForeignKey("product", "id")),
            Column("related_id", primary_key=True, references=ForeignKey("product", "id")),
        ),
    )
    assert join.element == "Shop::Product::related"


# trace: PRD-APP-122
def test_a_relation_back_to_a_foreign_key_gives_no_join_table(rule_engine: Engine) -> None:
    text = """package OneToMany {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Entity part def Customer {
        #Key attribute id : Uuid [1];
        ref orders : Order [*];
    }
    #Entity part def Order {
        #Key attribute number : Integer [1];
        ref customer : Customer [1];
    }
    #Operation action def FindCustomer {
        in id : Uuid;
        out customer : Customer;
        :>> method = HttpMethod::get;
        :>> path = "/customers/{id}";
    }
    #Application part api {
        :>> target = Target::fastapi;
        #Exposed action findCustomer : FindCustomer;
    }
}
"""
    schema = application_schema(_convert(rule_engine, "one-to-many.sysml", text), "OneToMany::api")
    assert _names(schema) == {"customer": ["id"], "order": ["customer_id", "number"]}
    order = schema.table("order")
    assert order is not None
    assert order.column("customer_id") == Column(
        "customer_id", references=ForeignKey("customer", "id")
    )


def test_two_tables_with_one_name_are_a_schema_error(rule_engine: Engine) -> None:
    text = """package Twice {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Entity part def OrderLines { #Key attribute id : Uuid [1]; }
    #Entity part def Order { #Key attribute id : Uuid [1]; ref lines : OrderLines [*]; }
    #Application part api {
        :>> target = Target::fastapi;
        #Exposed part orders : Order [*];
    }
}
"""
    ir = _convert(rule_engine, "twice.sysml", text)
    with pytest.raises(SchemaError, match='have the name "order_lines"'):
        application_schema(ir, "Twice::api")


# trace: PRD-APP-124, PRD-CORE-028
def test_the_snapshot_is_canonical_json(tmp_path: Path) -> None:
    schema = read_snapshot(RULE_SNAPSHOT)
    assert schema is not None
    assert [table.name for table in schema.tables] == ["customer", "item", "legacy"]
    data = (RULE_SNAPSHOT / SNAPSHOT_PATH).read_bytes()
    assert snapshot_bytes(schema) == data
    shuffled = Schema(tuple(reversed([Table(t.name, t.columns[::-1]) for t in schema.tables])))
    path = write_snapshot(tmp_path / "out", shuffled)
    assert path == tmp_path / "out" / ".dsml" / "schema-snapshot.json"
    assert path.read_bytes() == data
    assert read_snapshot(tmp_path / "out") == schema


# trace: PRD-APP-124
def test_a_foreign_key_goes_into_the_snapshot_and_back(tmp_path: Path) -> None:
    schema = Schema(
        (
            Table("a", (Column("b_id", True, False, ForeignKey("b", "id")),)),
            Table("b", (Column("id", primary_key=True),)),
        )
    )
    write_snapshot(tmp_path, schema)
    data = json.loads((tmp_path / SNAPSHOT_PATH).read_text(encoding="utf-8"))
    assert data["tables"][0]["columns"][0]["references"] == {"column": "id", "table": "b"}
    assert read_snapshot(tmp_path) == schema


def test_no_snapshot_gives_none(tmp_path: Path) -> None:
    assert read_snapshot(tmp_path) is None


BAD_SNAPSHOTS: list[tuple[object, str]] = [
    ([], "The top level must be a JSON object"),
    ({"snapshotVersion": 1, "tables": []}, "The snapshot version 1 is unknown"),
    ({"snapshotVersion": True, "tables": []}, "The snapshot version True is unknown"),
    ({"snapshotVersion": 2, "tables": {}}, 'The key "tables" must be a list'),
    ({"snapshotVersion": 2, "tables": [{"name": "a"}]}, 'Each item of "tables" must be'),
    (
        {"snapshotVersion": 2, "tables": [{"name": "", "columns": []}]},
        "Each table name must be a text",
    ),
    (
        {
            "snapshotVersion": 2,
            "tables": [{"name": "a", "columns": []}, {"name": "a", "columns": []}],
        },
        'More than one table has the name "a"',
    ),
    (
        {
            "snapshotVersion": 2,
            "tables": [
                {
                    "name": "a",
                    "columns": [
                        {
                            "name": "x",
                            "nullable": 1,
                            "primaryKey": False,
                            "references": None,
                            "type": "TEXT",
                            "unique": False,
                            "values": [],
                        }
                    ],
                }
            ],
        },
        "must be true or false",
    ),
    (
        {
            "snapshotVersion": 2,
            "tables": [
                {
                    "name": "a",
                    "columns": [
                        {
                            "name": "x",
                            "nullable": False,
                            "primaryKey": False,
                            "references": None,
                            "type": "TEXT",
                            "unique": False,
                            "values": [],
                        },
                        {
                            "name": "x",
                            "nullable": False,
                            "primaryKey": False,
                            "references": None,
                            "type": "TEXT",
                            "unique": False,
                            "values": [],
                        },
                    ],
                }
            ],
        },
        'More than one column of the table "a" has the name "x"',
    ),
]


def _one_column(column_type: object, values: object) -> dict[str, object]:
    column = {
        "name": "x",
        "nullable": False,
        "primaryKey": False,
        "references": None,
        "type": column_type,
        "unique": False,
        "values": values,
    }
    return {"snapshotVersion": 2, "tables": [{"name": "a", "columns": [column]}]}


BAD_SNAPSHOTS.extend(
    [
        (_one_column("BLOB", []), "The toolchain does not know this type"),
        (_one_column("TEXT", ["a"]), "The toolchain does not know this type"),
        (_one_column(None, ["a"]), "has values, but no type"),
        (_one_column("TEXT", "a"), 'The key "values" of "a.x" must be a list'),
    ]
)


# trace: PRD-APP-121, PRD-APP-124
@pytest.mark.parametrize(
    "column_type",
    [
        ColumnType("String"),
        ColumnType("String", length=80),
        ColumnType("Decimal", precision=10, scale=2),
        ColumnType("Enumeration", values=("open", "closed")),
        *(ColumnType(name) for name in ("Boolean", "Date", "DateTime", "Integer", "Real", "Uuid")),
    ],
)
def test_column_types_go_into_the_snapshot_and_back(column_type: ColumnType) -> None:
    assert column_type_of(column_type.postgresql, column_type.values) == column_type
    schema = Schema((Table("a", (Column("x", type=column_type),)),))
    column = parse_snapshot(json.loads(snapshot_bytes(schema))).tables[0].columns[0]
    assert column.type is not None
    assert column.type.postgresql == column_type.postgresql
    assert sorted(column.type.values) == sorted(column_type.values)


@pytest.mark.parametrize(("data", "message"), BAD_SNAPSHOTS)
def test_a_snapshot_that_is_not_correct_gives_an_error(data: object, message: str) -> None:
    with pytest.raises(SnapshotError, match=message):
        parse_snapshot(data)


def test_a_snapshot_that_is_not_json_gives_an_error(tmp_path: Path) -> None:
    (tmp_path / ".dsml").mkdir()
    (tmp_path / SNAPSHOT_PATH).write_text("{", encoding="utf-8")
    with pytest.raises(SnapshotError, match="is not correct JSON"):
        read_snapshot(tmp_path)
    (tmp_path / SNAPSHOT_PATH).write_text('{"tables": []}', encoding="utf-8")
    with pytest.raises(SnapshotError, match=r"is not correct\. The top level"):
        read_snapshot(tmp_path)
