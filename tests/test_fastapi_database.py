"""Tests of the database code of the FastAPI generator (story #77).

The golden files in `tests/golden/fastapi/order-service/` hold the database
code of the example model. These tests use a small IR with each DSML field
type, a `[0..1]` relation and a `[*]` relation.
"""

import ast
from pathlib import Path

import pytest

from dsml.config import Configuration, parse_configuration
from dsml.database.schema import ColumnType, SchemaError
from dsml.generate.fastapi import DATABASE_VARIABLES, FastApiGenerator
from dsml.generate.fastapi_database import python_call, sql_type
from dsml.generate.header import FileType, header
from dsml.generate.trace import SymbolKind
from dsml.ir.model import (
    Annotation,
    Attribute,
    Element,
    EnumValue,
    IntegerValue,
    Ir,
    ListValue,
    Location,
    Multiplicity,
)

GOLDEN = Path(__file__).resolve().parent / "golden" / "fastapi" / "order-service"
PROJECT = GOLDEN / "services" / "order-api"
LOCATION = Location(file="model.sysml", line=1, column=1)
ONE = Multiplicity(1, 1)
OPTIONAL = Multiplicity(0, 1)
MANY = Multiplicity(0, None)


def configuration() -> Configuration:
    return parse_configuration(
        'schema = 1\n\n[applications.shopApi]\noutput = "api"\n', Path("dsml.toml")
    )


def element(
    identity: str,
    kind: str,
    *,
    types: tuple[str, ...] = (),
    multiplicity: Multiplicity | None = None,
    attributes: tuple[Attribute, ...] = (),
    annotations: tuple[Annotation, ...] = (),
) -> Element:
    owner, _, name = identity.rpartition("::")
    return Element(
        identity=identity,
        kind=kind,  # type: ignore[arg-type]
        name=name,
        qualified_name=identity,
        location=LOCATION,
        owner=owner or None,
        multiplicity=multiplicity,
        types=types,
        attributes=attributes,
        annotations=annotations,
    )


def rules(**values: int) -> tuple[Annotation, ...]:
    return (
        Annotation(
            "FieldRules",
            tuple(Attribute(name, IntegerValue(value)) for name, value in values.items()),
        ),
    )


KEY = (Annotation("Key"),)


def field(
    entity: str, name: str, type_: str, multiplicity: Multiplicity = ONE, **values: int
) -> Element:
    return element(
        f"Shop::{entity}::{name}",
        "Field",
        types=(type_,),
        multiplicity=multiplicity,
        annotations=KEY if name == "id" else rules(**values) if values else (),
    )


def shop_ir() -> Ir:
    """Give an IR with each field type, a `[0..1]` relation and a `[*]` relation."""
    status = element(
        "Shop::Status",
        "Enumeration",
        attributes=(
            Attribute(
                "literals",
                ListValue((EnumValue("Shop::Status", "new"), EnumValue("Shop::Status", "done"))),
            ),
        ),
    )
    return Ir(
        elements=(
            element(
                "Shop::shopApi",
                "Application",
                attributes=(Attribute("target", EnumValue("DSML::Target", "fastapi")),),
            ),
            element("Shop::shopApi::items", "Exposed", types=("Shop::Item",)),
            element("Shop::shopApi::tags", "Exposed", types=("Shop::Tag",)),
            status,
            element("Shop::Item", "Entity"),
            field("Item", "id", "DSML::Uuid"),
            field("Item", "name", "ScalarValues::String", maxLength=80),
            field("Item", "text", "ScalarValues::String", OPTIONAL),
            field("Item", "count", "ScalarValues::Integer"),
            field("Item", "weight", "ScalarValues::Real", OPTIONAL),
            field("Item", "price", "DSML::Decimal", precision=10, scale=2),
            field("Item", "cost", "DSML::Decimal"),
            field("Item", "active", "ScalarValues::Boolean"),
            field("Item", "day", "DSML::Date"),
            field("Item", "changed", "DSML::DateTime"),
            field("Item", "status", "Shop::Status"),
            field("Item", "class", "ScalarValues::String", OPTIONAL),
            element("Shop::Item::owner", "Relation", types=("Shop::Tag",), multiplicity=OPTIONAL),
            element("Shop::Item::tags", "Relation", types=("Shop::Tag",), multiplicity=MANY),
            element("Shop::Tag", "Entity"),
            field("Tag", "id", "ScalarValues::Integer"),
        )
    )


def generate(ir: Ir) -> dict[str, bytes]:
    files = FastApiGenerator().generate(ir, configuration(), None)
    return {file.path: file.content for file in files}


# trace: PRD-APP-121
@pytest.mark.parametrize(
    ("column_type", "postgresql", "expression", "python"),
    [
        (ColumnType("String", length=500), "VARCHAR(500)", "String(500)", "str"),
        (ColumnType("String"), "TEXT", "Text", "str"),
        (ColumnType("Integer"), "BIGINT", "BigInteger", "int"),
        (ColumnType("Real"), "DOUBLE PRECISION", "Double", "float"),
        (
            ColumnType("Decimal", precision=10, scale=2),
            "NUMERIC(10, 2)",
            "Numeric(10, 2)",
            "Decimal",
        ),
        (ColumnType("Boolean"), "BOOLEAN", "Boolean", "bool"),
        (ColumnType("Date"), "DATE", "Date", "date"),
        (ColumnType("DateTime"), "TIMESTAMPTZ", "DateTime(timezone=True)", "datetime"),
        (ColumnType("Uuid"), "UUID", "Uuid", "UUID"),
        (ColumnType("Enumeration", values=("a", "b")), "VARCHAR(64)", "String(64)", "str"),
    ],
)
def test_each_dsml_field_type_has_its_postgresql_type(
    column_type: ColumnType, postgresql: str, expression: str, python: str
) -> None:
    assert column_type.postgresql == postgresql
    assert sql_type(column_type).expression == expression
    assert sql_type(column_type).python == python


# trace: PRD-APP-120, PRD-APP-121
def test_model_has_the_column_type_of_each_field() -> None:
    text = generate(shop_ir())["api/app/shared/db/models/item_gen.py"].decode()
    for line in (
        "    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)",
        "    name: Mapped[str] = mapped_column(String(80))",
        "    text: Mapped[str | None] = mapped_column(Text)",
        "    count: Mapped[int] = mapped_column(BigInteger)",
        "    weight: Mapped[float | None] = mapped_column(Double)",
        "    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))",
        "    cost: Mapped[Decimal] = mapped_column(Numeric(18, 4))",
        "    active: Mapped[bool] = mapped_column(Boolean)",
        "    day: Mapped[date] = mapped_column(Date)",
        "    changed: Mapped[datetime] = mapped_column(DateTime(timezone=True))",
        "    status: Mapped[str] = mapped_column(String(64))",
        '    class_: Mapped[str | None] = mapped_column("class", Text)',
    ):
        assert f"{line}\n" in text
    assert "from datetime import date, datetime\n" in text
    assert "from decimal import Decimal\n" in text
    assert "from uuid import UUID\n" in text
    assert 'STATUS_VALUES = (\n    "new",\n    "done",\n)\n' in text
    assert 'column("status").in_(STATUS_VALUES),\n            name="status_values",' in text
    ast.parse(text)


# trace: PRD-APP-122
def test_relations_give_a_foreign_key_and_a_join_table() -> None:
    text = generate(shop_ir())["api/app/shared/db/models/item_gen.py"].decode()
    assert (
        '    owner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tag.id"))\n'
        in text
    )
    assert (
        "item_tags_table = Table(\n"
        '    "item_tags",\n'
        "    Base.metadata,\n"
        '    Column[UUID]("item_id", Uuid, ForeignKey("item.id"), primary_key=True),\n'
        '    Column[int]("tags_id", BigInteger, ForeignKey("tag.id"), primary_key=True),\n'
        ")\n"
    ) in text


# trace: PRD-APP-017, PRD-APP-120, PRD-TRACE-005, PRD-TRACE-006
def test_each_entity_has_one_model_file_with_its_header_and_symbol() -> None:
    files = FastApiGenerator().generate(shop_ir(), configuration(), None)
    models = {file.path: file for file in files if "/db/models/" in file.path}
    assert sorted(models) == [
        "api/app/shared/db/models/__init__.py",
        "api/app/shared/db/models/item_gen.py",
        "api/app/shared/db/models/tag_gen.py",
    ]
    item = models["api/app/shared/db/models/item_gen.py"]
    assert item.content.decode().startswith(
        header(FileType.PYTHON, ["Shop::Item", "Shop::Item::tags"])
    )
    [symbol] = item.symbols
    assert (symbol.kind, symbol.name, symbol.elements) == (
        SymbolKind.CLASS,
        "Item",
        ("Shop::Item",),
    )


# trace: PRD-APP-123
def test_application_with_entities_gets_the_database_packages_and_variables() -> None:
    files = generate(shop_ir())
    pyproject = files["api/pyproject.toml"].decode()
    assert '"psycopg[binary]==' in pyproject
    assert '"sqlalchemy[asyncio]==' in pyproject
    config = files["api/app/shared/config_gen.py"].decode()
    for variable in DATABASE_VARIABLES:
        assert f'"{variable.name}"' in config
    assert "database_password: str = field(repr=False)\n" in config
    session = files["api/app/shared/db/session_gen.py"].decode()
    assert 'DRIVER = "postgresql+psycopg"\n' in session
    assert "AsyncSession" in session


def test_application_with_no_entity_gets_no_database_code() -> None:
    ir = Ir(elements=shop_ir().elements[:1])
    files = generate(ir)
    assert not [path for path in files if "/db/" in path or path.endswith("test_db_gen.py")]
    assert b"sqlalchemy" not in files["api/pyproject.toml"]
    assert b"DATABASE_" not in files["api/app/shared/config_gen.py"]


def test_field_type_that_is_not_supported_is_a_schema_error() -> None:
    ir = shop_ir()
    wrong = field("Tag", "label", "ScalarValues::Natural")
    with pytest.raises(SchemaError, match='"label" of the table "tag"'):
        generate(Ir(elements=(*ir.elements, wrong)))


# trace: PRD-CORE-035
def test_python_call_gives_the_form_of_ruff_format() -> None:
    assert python_call("f", ["a", "b"], 1) == ["    f(a, b)"]
    head = "x" * 30
    assert python_call(head, ["a" * 40, "b" * 40], 1) == [
        f"    {head}(",
        f"        {'a' * 40}, {'b' * 40}",
        "    )",
    ]
    assert python_call("f", ["a" * 60, "b" * 60], 1, ",") == [
        "    f(",
        f"        {'a' * 60},",
        f"        {'b' * 60},",
        "    ),",
    ]


# trace: PRD-APP-120, PRD-APP-123
def test_golden_project_has_the_database_code() -> None:
    assert (PROJECT / "app" / "shared" / "db" / "models" / "order_gen.py").is_file()
    assert (PROJECT / "app" / "shared" / "db" / "session_gen.py").is_file()
    assert (PROJECT / "tests" / "test_db_gen.py").is_file()
