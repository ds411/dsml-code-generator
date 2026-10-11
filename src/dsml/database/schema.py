# trace: PRD-APP-120, PRD-APP-122
"""Get the database schema of one application from the IR.

The schema holds the tables and the columns of the entities of the
application. The entities of an application are:

1. The entities that the application exposes.
2. The entities that type a parameter of an operation that the application
   exposes.
3. Each entity that a relation of an entity of the application refers to.

These rules make the tables and the columns:

- Each entity gives one table. The table name is the entity name in snake
  case (PRD-APP-120).
- Each field gives one column. The column name is the field name in snake
  case. A field with `#Key` is a primary key column. A field with the lower
  multiplicity 0 gives a nullable column.
- A `[0..1]` or `[1]` relation gives a foreign key column for each key field
  of the related entity: `<relation>_<key>` (PRD-APP-122).
- A `[*]` relation gives a join table `<table>_<relation>`, with a foreign
  key column for each key field of the two entities (PRD-APP-122). If the
  related entity has a `[0..1]` or `[1]` relation back to the entity, the
  foreign key of that relation holds the link. Then there is no join table.

The validator and the generators read the schema only from the IR
(PRD-CORE-026).
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate import names
from dsml.ir.model import Element, Ir, StringValue

DESTRUCTIVE: Final = "Destructive"
"""The annotation of a destructive database change (PRD-DSML-034)."""

KEY: Final = "Key"
"""The annotation of a primary key field."""


# trace: PRD-APP-120
class SchemaError(ToolchainError):
    """The model gives a schema that is not correct, for example two tables with one name."""


# trace: PRD-APP-122
@dataclass(frozen=True, slots=True)
class ForeignKey:
    """The table and the column that a foreign key column refers to."""

    table: str
    column: str


# trace: PRD-APP-120, PRD-APP-122
@dataclass(frozen=True, slots=True)
class Column:
    """One column of a table.

    `element` and `renamed_from` come from the model. The snapshot does not
    keep them, and a comparison of two columns ignores them.
    """

    name: str
    nullable: bool = False
    primary_key: bool = False
    references: ForeignKey | None = None
    element: str | None = field(default=None, compare=False)
    """The identity of the field or the relation of the column."""
    renamed_from: str | None = field(default=None, compare=False)
    """The old name of the column, from `@Destructive { renamedFrom }`."""


# trace: PRD-APP-120, PRD-APP-122
@dataclass(frozen=True, slots=True)
class Table:
    """One table. The columns are sorted by name.

    `element` and `renamed_from` come from the model. The snapshot does not
    keep them, and a comparison of two tables ignores them.
    """

    name: str
    columns: tuple[Column, ...] = ()
    element: str | None = field(default=None, compare=False)
    """The identity of the entity, or of the relation of a join table."""
    renamed_from: str | None = field(default=None, compare=False)
    """The old name of the table, from `@Destructive { renamedFrom }`."""

    def column(self, name: str) -> Column | None:
        """Give the column with the name, or `None`."""
        return next((column for column in self.columns if column.name == name), None)


# trace: PRD-APP-120, PRD-APP-124
@dataclass(frozen=True, slots=True)
class Schema:
    """The tables of one application, sorted by name."""

    tables: tuple[Table, ...] = ()

    def table(self, name: str) -> Table | None:
        """Give the table with the name, or `None`."""
        return next((table for table in self.tables if table.name == name), None)


# trace: PRD-DSML-034
def is_destructive(element: Element) -> bool:
    """Tell if the element has the `#Destructive` metadata."""
    return any(annotation.name == DESTRUCTIVE for annotation in element.annotations)


# trace: PRD-DSML-034
def renamed_from(element: Element) -> str | None:
    """Give the old name of the element from `@Destructive { renamedFrom }`, or `None`."""
    for annotation in element.annotations:
        if annotation.name != DESTRUCTIVE:
            continue
        for attribute in annotation.attributes:
            if attribute.name == "renamedFrom" and isinstance(attribute.value, StringValue):
                return attribute.value.value
    return None


# trace: PRD-APP-120, PRD-APP-122
def application_schema(ir: Ir, application: str) -> Schema:
    """Give the schema of the application with the identity `application`.

    Two tables or two columns of one table with the same name give a
    `SchemaError`.
    """
    return _SchemaReader(ir).schema(application)


class _SchemaReader:
    """Read the schema of an application from the elements of the IR."""

    def __init__(self, ir: Ir) -> None:
        self.elements: Mapping[str, Element] = {item.identity: item for item in ir.elements}
        owned: dict[str, list[Element]] = {}
        for item in ir.elements:
            if item.owner is not None:
                owned.setdefault(item.owner, []).append(item)
        self.owned: Mapping[str, list[Element]] = owned

    def schema(self, application: str) -> Schema:
        tables: dict[str, Table] = {}
        for entity in self._entities(application):
            for table in self._tables(entity):
                if table.name in tables:
                    raise SchemaError(
                        f'Two tables of the application {application} have the name "{table.name}".'
                    )
                tables[table.name] = table
        return Schema(tuple(tables[name] for name in sorted(tables)))

    def _entities(self, application: str) -> list[Element]:
        """Give the entities of the application, sorted by identity."""
        found: set[str] = set()
        queue: list[str] = []
        for exposed in self._children(application, "Exposed"):
            for identity in exposed.types:
                typed = self.elements.get(identity)
                if typed is None:
                    continue
                if typed.kind == "Entity":
                    queue.append(identity)
                elif typed.kind == "Operation":
                    for parameter in self._children(identity, "Parameter"):
                        queue.extend(parameter.types)
        while queue:
            identity = queue.pop()
            entity = self.elements.get(identity)
            if identity in found or entity is None or entity.kind != "Entity":
                continue
            found.add(identity)
            for relation in self._children(identity, "Relation"):
                queue.extend(relation.types)
        return [self.elements[identity] for identity in sorted(found)]

    def _children(self, owner: str, kind: str) -> list[Element]:
        return [item for item in self.owned.get(owner, []) if item.kind == kind]

    def _target(self, relation: Element) -> Element | None:
        return next(
            (
                self.elements[identity]
                for identity in relation.types
                if identity in self.elements and self.elements[identity].kind == "Entity"
            ),
            None,
        )

    def _keys(self, entity: Element) -> list[Element]:
        fields = self._children(entity.identity, "Field")
        return sorted(
            (item for item in fields if any(note.name == KEY for note in item.annotations)),
            key=lambda item: snake_case(item.name),
        )

    def _tables(self, entity: Element) -> Iterator[Table]:
        table = snake_case(entity.name)
        old_table = _snake(renamed_from(entity))
        columns: list[Column] = []
        for item in self._children(entity.identity, "Field"):
            columns.append(
                Column(
                    name=snake_case(item.name),
                    nullable=_optional(item),
                    primary_key=any(note.name == KEY for note in item.annotations),
                    element=item.identity,
                    renamed_from=_snake(renamed_from(item)),
                )
            )
        for relation in self._children(entity.identity, "Relation"):
            target = self._target(relation)
            if target is None:
                continue
            if _single(relation):
                columns.extend(self._foreign_keys(relation, target, _optional(relation)))
            elif not self._has_back_reference(target, entity):
                yield self._join_table(entity, table, old_table, relation, target)
        yield Table(
            name=table,
            columns=_sorted_columns(columns),
            element=entity.identity,
            renamed_from=old_table,
        )

    def _foreign_keys(self, relation: Element, target: Element, nullable: bool) -> list[Column]:
        name = snake_case(relation.name)
        old_name = _snake(renamed_from(relation))
        return [
            Column(
                name=f"{name}_{snake_case(key.name)}",
                nullable=nullable,
                references=ForeignKey(snake_case(target.name), snake_case(key.name)),
                element=relation.identity,
                renamed_from=None if old_name is None else f"{old_name}_{snake_case(key.name)}",
            )
            for key in self._keys(target)
        ]

    def _join_table(
        self, entity: Element, table: str, old_table: str | None, relation: Element, target: Element
    ) -> Table:
        name = snake_case(relation.name)
        old_name = _snake(renamed_from(relation))
        columns = [
            Column(
                name=f"{table}_{snake_case(key.name)}",
                primary_key=True,
                references=ForeignKey(table, snake_case(key.name)),
                element=key.identity,
            )
            for key in self._keys(entity)
        ]
        columns.extend(
            Column(
                name=column.name,
                primary_key=True,
                references=column.references,
                element=column.element,
                renamed_from=column.renamed_from,
            )
            for column in self._foreign_keys(relation, target, nullable=False)
        )
        renamed = None
        if old_table is not None or old_name is not None:
            renamed = f"{old_table or table}_{old_name or name}"
        return Table(
            name=f"{table}_{name}",
            columns=_sorted_columns(columns),
            element=relation.identity,
            renamed_from=renamed,
        )

    def _has_back_reference(self, target: Element, entity: Element) -> bool:
        """Tell if the target has a `[0..1]` or `[1]` relation to the entity."""
        return any(
            _single(relation) and entity.identity in relation.types
            for relation in self._children(target.identity, "Relation")
        )


def _single(element: Element) -> bool:
    """Tell if the multiplicity of the element is `[0..1]` or `[1]`."""
    multiplicity = element.multiplicity
    return multiplicity is None or multiplicity.upper == 1


def _optional(element: Element) -> bool:
    """Tell if the lower multiplicity of the element is 0."""
    return element.multiplicity is not None and element.multiplicity.lower == 0


def snake_case(name: str) -> str:
    """Give the name in snake case. A name with no letter or digit is a schema error."""
    try:
        return names.snake_case(name)
    except ValueError as error:
        raise SchemaError(str(error)) from None


def _snake(name: str | None) -> str | None:
    return None if name is None else snake_case(name)


def _sorted_columns(columns: list[Column]) -> tuple[Column, ...]:
    names = [column.name for column in columns]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise SchemaError(f'A table has two columns with the name "{duplicates[0]}".')
    return tuple(sorted(columns, key=lambda column: column.name))
