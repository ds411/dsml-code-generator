# trace: PRD-APP-124, PRD-CORE-028, PRD-CORE-034
"""Read and write the schema snapshot `.dsml/schema-snapshot.json`.

The schema snapshot is in the output folder of the application. It holds the
schema of the application when the generator wrote the newest migration
(PRD-APP-124, Q19). The file is canonical JSON (Q16):

- The object keys are in sorted order.
- The tables and the columns of each table are sorted by name.
- The text is UTF-8 with LF line ends and one LF at the end.

`docs/notes/schema-snapshot.md` gives the format.
"""

import json
from pathlib import Path
from typing import Final, cast

from dsml.database.schema import Column, ForeignKey, Schema, Table
from dsml.errors import ToolchainError
from dsml.ir.writer import JsonValue, canonical_json

SNAPSHOT_PATH: Final = ".dsml/schema-snapshot.json"
"""The path of the snapshot, relative to the output folder of the application."""

SNAPSHOT_VERSION: Final = 1
"""The version of the snapshot format."""


# trace: PRD-APP-124
class SnapshotError(ToolchainError):
    """The schema snapshot is not correct, or the toolchain cannot read it."""


# trace: PRD-APP-124, PRD-CORE-028, PRD-CORE-034
def snapshot_bytes(schema: Schema) -> bytes:
    """Write the schema as the canonical JSON bytes of a snapshot."""
    tables: list[JsonValue] = []
    for table in sorted(schema.tables, key=lambda item: item.name):
        columns: list[JsonValue] = []
        for column in sorted(table.columns, key=lambda item: item.name):
            references: JsonValue = None
            if column.references is not None:
                references = {"column": column.references.column, "table": column.references.table}
            columns.append(
                {
                    "name": column.name,
                    "nullable": column.nullable,
                    "primaryKey": column.primary_key,
                    "references": references,
                }
            )
        tables.append({"columns": columns, "name": table.name})
    return canonical_json({"snapshotVersion": SNAPSHOT_VERSION, "tables": tables})


# trace: PRD-APP-124
def write_snapshot(folder: Path, schema: Schema) -> Path:
    """Write the snapshot of the schema into the output folder `folder`.

    The function makes the folder `.dsml` if it does not exist. It gives the
    path of the snapshot.
    """
    path = folder / SNAPSHOT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(snapshot_bytes(schema))
    return path


# trace: PRD-APP-124
def read_snapshot(folder: Path) -> Schema | None:
    """Read the snapshot in the output folder `folder`.

    If there is no snapshot, the function gives `None`. A snapshot that is
    not correct gives a `SnapshotError`.
    """
    path = folder / SNAPSHOT_PATH
    try:
        text = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        return None
    except OSError as error:
        raise SnapshotError(f"Cannot read the schema snapshot {path}: {error.strerror}.") from None
    except UnicodeDecodeError:
        raise SnapshotError(f"The schema snapshot {path} does not have UTF-8 encoding.") from None
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as error:
        raise SnapshotError(
            f"The schema snapshot {path} is not correct JSON: {error.msg} "
            f"at line {error.lineno}, column {error.colno}."
        ) from None
    try:
        return parse_snapshot(data)
    except SnapshotError as error:
        raise SnapshotError(f"The schema snapshot {path} is not correct. {error}") from None


# trace: PRD-APP-124
def parse_snapshot(data: object) -> Schema:
    """Convert the JSON data of a snapshot into a schema."""
    top = _object(data, {"snapshotVersion", "tables"}, "The top level")
    version = top["snapshotVersion"]
    if type(version) is not int or version != SNAPSHOT_VERSION:
        raise SnapshotError(
            f"The snapshot version {version!r} is unknown. "
            f"This toolchain reads snapshot version {SNAPSHOT_VERSION}."
        )
    tables = tuple(_table(item) for item in _list(top["tables"], '"tables"'))
    _unique([table.name for table in tables], "table")
    return Schema(tuple(sorted(tables, key=lambda table: table.name)))


def _table(data: object) -> Table:
    table = _object(data, {"columns", "name"}, 'Each item of "tables"')
    name = _name(table["name"], "table")
    columns = tuple(
        _column(item, name) for item in _list(table["columns"], f'"columns" of "{name}"')
    )
    _unique([column.name for column in columns], f'column of the table "{name}"')
    return Table(name, tuple(sorted(columns, key=lambda column: column.name)))


def _column(data: object, table: str) -> Column:
    column = _object(
        data,
        {"name", "nullable", "primaryKey", "references"},
        f'Each column of the table "{table}"',
    )
    name = _name(column["name"], "column")
    nullable = column["nullable"]
    primary_key = column["primaryKey"]
    if not isinstance(nullable, bool) or not isinstance(primary_key, bool):
        raise SnapshotError(
            f'The keys "nullable" and "primaryKey" of the column "{table}.{name}" '
            "must be true or false."
        )
    references: ForeignKey | None = None
    if column["references"] is not None:
        target = _object(
            column["references"], {"column", "table"}, f'"references" of "{table}.{name}"'
        )
        references = ForeignKey(_name(target["table"], "table"), _name(target["column"], "column"))
    return Column(name, nullable, primary_key, references)


def _object(data: object, keys: set[str], what: str) -> dict[str, object]:
    if not isinstance(data, dict) or set(cast(dict[str, object], data)) != keys:
        names = ", ".join(f'"{key}"' for key in sorted(keys))
        raise SnapshotError(f"{what} must be a JSON object with only the keys {names}.")
    return cast(dict[str, object], data)


def _list(data: object, what: str) -> list[object]:
    if not isinstance(data, list):
        raise SnapshotError(f"The key {what} must be a list.")
    return cast(list[object], data)


def _name(data: object, what: str) -> str:
    if not isinstance(data, str) or not data:
        raise SnapshotError(f"Each {what} name must be a text that is not empty.")
    return data


def _unique(names: list[str], what: str) -> None:
    for name in sorted(names):
        if names.count(name) > 1:
            raise SnapshotError(f'More than one {what} has the name "{name}".')
