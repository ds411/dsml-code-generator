# trace: PRD-APP-124, PRD-APP-127, PRD-CORE-031
"""Compare the schema snapshot with the schema of the IR.

The function `compare` gives the changes from the old schema (the snapshot)
to the new schema (the IR) as a `Changes` object. The FastAPI generator
writes one Alembic migration from these changes (PRD-APP-124).

The tables and the columns match by name. A table or a column with
`@Destructive { renamedFrom }` matches the old table or column with that
name, if the new schema has no table or column with the old name. A table
or a column with no match is a new or a dropped table or column.

The constraints have the names of the naming convention of the generated
declarative base `app/shared/db/base_gen.py`. Thus a migration refers to
the constraints of the database by the names that the models give.

All lists of `Changes` are in a fixed order, so the same two schemas give
the same migration (PRD-CORE-031).
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from dsml.database.schema import Column, ColumnType, ForeignKey, Schema, Table

MAX_NAME_LENGTH: Final = 63
"""The maximum length of a PostgreSQL identifier."""

ConstraintKind = Literal["pk", "fk", "ck"]
"""The kind of a constraint: primary key, foreign key or check."""

_ORDER: Final[dict[ConstraintKind, int]] = {"pk": 0, "fk": 1, "ck": 2}


# trace: PRD-APP-120
def convention_name(name: str) -> str:
    """Give the name of a constraint as SQLAlchemy writes it for PostgreSQL.

    A name of more than 63 characters becomes its first 55 characters, "_"
    and the last 4 characters of its MD5 hash. SQLAlchemy does the same for
    a name of the naming convention.
    """
    if len(name) <= MAX_NAME_LENGTH:
        return name
    digest = hashlib.md5(name.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"{name[: MAX_NAME_LENGTH - 8]}_{digest[-4:]}"


# trace: PRD-APP-120, PRD-APP-121, PRD-APP-122
@dataclass(frozen=True, slots=True)
class Constraint:
    """One constraint of a table, with the name of the naming convention."""

    kind: ConstraintKind
    table: str
    columns: tuple[str, ...]
    """The columns of the constraint. A primary key has its columns in sorted order."""
    references: ForeignKey | None = None
    """The table and the column that a foreign key refers to."""
    values: tuple[str, ...] = ()
    """The permitted values of a check constraint, in the order of the model."""

    @property
    def name(self) -> str:
        """Give the name of the constraint (`NAMING_CONVENTION` of `base_gen.py`)."""
        match self.kind:
            case "pk":
                name = f"pk_{self.table}"
            case "fk":
                assert self.references is not None
                name = f"fk_{self.table}_{self.columns[0]}_{self.references.table}"
            case "ck":
                name = f"ck_{self.table}_{self.columns[0]}_values"
        return convention_name(name)


# trace: PRD-APP-120, PRD-APP-121, PRD-APP-122
def constraints(table: Table) -> list[Constraint]:
    """Give the constraints of a table: the primary key, then the foreign keys and checks."""
    found: list[Constraint] = []
    keys = tuple(sorted(column.name for column in table.columns if column.primary_key))
    if keys:
        found.append(Constraint("pk", table.name, keys))
    for column in table.columns:
        if column.references is not None:
            found.append(Constraint("fk", table.name, (column.name,), column.references))
    for column in table.columns:
        if column.type is not None and column.type.values:
            found.append(Constraint("ck", table.name, (column.name,), values=column.type.values))
    return sorted(found, key=lambda item: (_ORDER[item.kind], item.columns))


# trace: PRD-APP-124
@dataclass(frozen=True, slots=True)
class Rename:
    """A renamed table, column or constraint.

    For a column or a constraint, `table` is the new name of its table.
    """

    old: str
    new: str
    table: str = ""


# trace: PRD-APP-124
@dataclass(frozen=True, slots=True)
class AlteredColumn:
    """A column with a new type or a new nullable flag."""

    table: str
    column: Column
    """The new column."""
    type_changed: bool
    nullable_changed: bool


# trace: PRD-APP-124, PRD-APP-127
@dataclass(frozen=True, slots=True)
class Changes:
    """The changes from an old schema to a new schema, in the order of a migration.

    A migration does the changes in the order of the attributes.
    """

    renamed_tables: tuple[Rename, ...] = ()
    renamed_columns: tuple[Rename, ...] = ()
    renamed_constraints: tuple[Rename, ...] = ()
    dropped_constraints: tuple[Constraint, ...] = ()
    """The constraints to drop, with the new table name and the old constraint name."""
    dropped_columns: tuple[tuple[str, str], ...] = ()
    """The table and the name of each dropped column. The table has its new name."""
    dropped_tables: tuple[Table, ...] = ()
    created_tables: tuple[Table, ...] = ()
    """The new tables, in an order where a table comes after the tables it refers to."""
    added_columns: tuple[tuple[str, Column], ...] = ()
    altered_columns: tuple[AlteredColumn, ...] = ()
    created_constraints: tuple[Constraint, ...] = ()
    """The constraints to add to tables that exist, and the foreign keys of a cycle."""

    @property
    def empty(self) -> bool:
        """Tell if there is no change."""
        return not any(
            (
                self.renamed_tables,
                self.renamed_columns,
                self.renamed_constraints,
                self.dropped_constraints,
                self.dropped_columns,
                self.dropped_tables,
                self.created_tables,
                self.added_columns,
                self.altered_columns,
                self.created_constraints,
            )
        )

    @property
    def tables(self) -> list[str]:
        """Give the names of the tables that the changes touch, sorted."""
        names = {rename.new for rename in self.renamed_tables}
        names.update(rename.table for rename in self.renamed_columns)
        names.update(rename.table for rename in self.renamed_constraints)
        names.update(item.table for item in self.dropped_constraints)
        names.update(table for table, _ in self.dropped_columns)
        names.update(table.name for table in self.dropped_tables)
        names.update(table.name for table in self.created_tables)
        names.update(table for table, _ in self.added_columns)
        names.update(item.table for item in self.altered_columns)
        names.update(item.table for item in self.created_constraints)
        return sorted(names)

    @property
    def slug(self) -> str:
        """Give the short name of the migration, for its file name."""
        tables = self.tables
        created = {table.name for table in self.created_tables}
        only_created = self == Changes(
            created_tables=self.created_tables, created_constraints=self.created_constraints
        ) and all(item.table in created for item in self.created_constraints)
        only_dropped = self == Changes(
            dropped_constraints=self.dropped_constraints, dropped_tables=self.dropped_tables
        )
        if only_created and len(self.created_tables) == 1:
            slug = f"create_{self.created_tables[0].name}"
        elif only_created:
            slug = "create_tables"
        elif only_dropped and len(self.dropped_tables) == 1:
            slug = f"drop_{self.dropped_tables[0].name}"
        elif len(tables) == 1:
            slug = f"change_{tables[0]}"
        else:
            slug = "change_schema"
        return slug[:40].rstrip("_")


# trace: PRD-APP-124, PRD-CORE-031
def compare(old: Schema, new: Schema) -> Changes:
    """Give the changes from the schema `old` to the schema `new`."""
    return _Comparison(old, new).changes()


@dataclass(frozen=True, slots=True)
class _Pair:
    """An old table and the new table that matches it."""

    old: Table
    new: Table
    columns: Mapping[str, str]
    """The new name of each old column that the new table keeps."""


class _Comparison:
    def __init__(self, old: Schema, new: Schema) -> None:
        self.old = old
        self.new = new
        new_names = {table.name for table in new.tables}
        old_names = {table.name for table in old.tables}
        self.pairs: list[_Pair] = []
        self.created: list[Table] = []
        matched: set[str] = set()
        for table in new.tables:
            source = old.table(table.name)
            renamed = table.renamed_from
            if source is None and renamed in old_names and renamed not in new_names:
                source = old.table(renamed)
            if source is None:
                self.created.append(table)
                continue
            matched.add(source.name)
            self.pairs.append(_Pair(source, table, _column_map(source, table)))
        self.dropped = [table for table in old.tables if table.name not in matched]
        self.table_names = {pair.old.name: pair.new.name for pair in self.pairs}
        self.column_names = {pair.old.name: pair.columns for pair in self.pairs}

    def changes(self) -> Changes:
        renamed_columns: list[Rename] = []
        dropped_columns: list[tuple[str, str]] = []
        added_columns: list[tuple[str, Column]] = []
        altered: list[AlteredColumn] = []
        for pair in self.pairs:
            kept = set(pair.columns.values())
            for column in pair.old.columns:
                new_name = pair.columns.get(column.name)
                if new_name is None:
                    dropped_columns.append((pair.new.name, column.name))
                elif new_name != column.name:
                    renamed_columns.append(Rename(column.name, new_name, pair.new.name))
            for column in pair.new.columns:
                if column.name not in kept:
                    added_columns.append((pair.new.name, column))
            old_columns = {
                pair.columns[item.name]: item
                for item in pair.old.columns
                if item.name in pair.columns
            }
            for column in pair.new.columns:
                previous = old_columns.get(column.name)
                if previous is None:
                    continue
                type_changed = _type_changed(previous.type, column.type)
                nullable_changed = previous.nullable != column.nullable
                if type_changed or nullable_changed:
                    altered.append(
                        AlteredColumn(pair.new.name, column, type_changed, nullable_changed)
                    )
        renamed_constraints, dropped_constraints, created_constraints = self._constraints()
        created_tables, deferred = self._created_tables()
        dropped_constraints.extend(self._dropped_table_keys())
        return Changes(
            renamed_tables=tuple(
                sorted(
                    (
                        Rename(pair.old.name, pair.new.name)
                        for pair in self.pairs
                        if pair.old.name != pair.new.name
                    ),
                    key=lambda item: item.new,
                )
            ),
            renamed_columns=tuple(sorted(renamed_columns, key=lambda item: (item.table, item.new))),
            renamed_constraints=tuple(
                sorted(renamed_constraints, key=lambda item: (item.table, item.new))
            ),
            dropped_constraints=tuple(dropped_constraints),
            dropped_columns=tuple(sorted(dropped_columns)),
            dropped_tables=tuple(sorted(self.dropped, key=lambda table: table.name)),
            created_tables=tuple(created_tables),
            added_columns=tuple(sorted(added_columns, key=lambda item: (item[0], item[1].name))),
            altered_columns=tuple(sorted(altered, key=lambda item: (item.table, item.column.name))),
            created_constraints=tuple(_sorted_constraints([*created_constraints, *deferred])),
        )

    def _constraints(self) -> tuple[list[Rename], list[Constraint], list[Constraint]]:
        """Compare the constraints of each table that the new schema keeps."""
        renamed: list[Rename] = []
        dropped: list[Constraint] = []
        created: list[Constraint] = []
        for pair in sorted(self.pairs, key=lambda item: item.new.name):
            old = {_key(item): item for item in map(self._moved, constraints(pair.old))}
            new = {_key(item): item for item in constraints(pair.new)}
            for key in sorted(old.keys() | new.keys()):
                before = old.get(key)
                after = new.get(key)
                if before is not None and after is not None and _same(before, after):
                    if before.name != after.name:
                        renamed.append(Rename(before.name, after.name, pair.new.name))
                    continue
                if before is not None and set(before.columns) <= set(pair.columns.values()):
                    dropped.append(before)
                if after is not None:
                    created.append(after)
        return renamed, _sorted_constraints(dropped, reverse=True), created

    def _moved(self, constraint: Constraint) -> _OldConstraint:
        """Give an old constraint with the new names of its table and its columns.

        The name stays the old name, because the database has that name.
        """
        columns = self.column_names[constraint.table]
        references = constraint.references
        if references is not None and references.table in self.table_names:
            references = ForeignKey(
                self.table_names[references.table],
                self.column_names[references.table].get(references.column, references.column),
            )
        return _OldConstraint(
            kind=constraint.kind,
            table=self.table_names[constraint.table],
            columns=tuple(sorted(columns.get(name, name) for name in constraint.columns))
            if constraint.kind == "pk"
            else tuple(columns.get(name, name) for name in constraint.columns),
            references=references,
            values=constraint.values,
            old_name=constraint.name,
        )

    def _created_tables(self) -> tuple[list[Table], list[Constraint]]:
        """Sort the new tables so that a table comes after the tables it refers to.

        If the new tables refer to each other in a cycle, the foreign keys
        to a table that comes later go to the list of constraints to create.
        """
        remaining = {table.name: table for table in self.created}
        order: list[Table] = []
        deferred: list[Constraint] = []
        while remaining:
            ready = [
                name
                for name in sorted(remaining)
                if not any(
                    item.references is not None
                    and item.references.table in remaining
                    and item.references.table != name
                    for item in constraints(remaining[name])
                )
            ]
            name = ready[0] if ready else sorted(remaining)[0]
            table = remaining.pop(name)
            order.append(table)
            deferred.extend(
                item
                for item in constraints(table)
                if item.references is not None and item.references.table in remaining
            )
        return order, deferred

    def _dropped_table_keys(self) -> list[Constraint]:
        """Give the foreign keys from one dropped table to another dropped table.

        The migration drops these foreign keys first, so it can drop the
        tables in any order.
        """
        dropped = {table.name for table in self.dropped}
        keys = [
            _OldConstraint(
                kind=item.kind,
                table=item.table,
                columns=item.columns,
                references=item.references,
                old_name=item.name,
            )
            for table in self.dropped
            for item in constraints(table)
            if item.references is not None
            and item.references.table in dropped
            and item.references.table != table.name
        ]
        return _sorted_constraints(keys)


# trace: PRD-APP-124
@dataclass(frozen=True, slots=True)
class _OldConstraint(Constraint):
    """A constraint of the database. Its name is the name that the database has."""

    old_name: str = ""

    @property
    def name(self) -> str:
        return self.old_name


def _column_map(old: Table, new: Table) -> dict[str, str]:
    """Give the new name of each old column that the new table keeps."""
    new_names = {column.name for column in new.columns}
    result: dict[str, str] = {}
    for column in new.columns:
        if old.column(column.name) is not None:
            result[column.name] = column.name
        elif (
            column.renamed_from is not None
            and column.renamed_from not in new_names
            and old.column(column.renamed_from) is not None
        ):
            result[column.renamed_from] = column.name
    return result


def _type_changed(old: ColumnType | None, new: ColumnType | None) -> bool:
    if old is None or new is None:
        return False
    return old.postgresql != new.postgresql


def _key(constraint: Constraint) -> tuple[int, tuple[str, ...]]:
    """Give the key that matches an old and a new constraint of one table."""
    if constraint.kind == "pk":
        return (_ORDER["pk"], ())
    return (_ORDER[constraint.kind], constraint.columns)


def _same(old: Constraint, new: Constraint) -> bool:
    """Tell if two constraints have the same definition. The names can be different."""
    return (
        old.columns == new.columns
        and old.references == new.references
        and set(old.values) == set(new.values)
    )


def _sorted_constraints(items: Sequence[Constraint], reverse: bool = False) -> list[Constraint]:
    """Sort constraints: primary keys, foreign keys, checks. `reverse` puts the keys last."""
    return sorted(
        items,
        key=lambda item: (
            -_ORDER[item.kind] if reverse else _ORDER[item.kind],
            item.table,
            item.columns,
        ),
    )
