# trace: PRD-VAL-015, PRD-APP-127, PRD-DSML-034
"""The rule STR-013: a destructive database change with no `#Destructive` metadata.

STR-013 compares the schema of each FastAPI application in the IR with the
schema snapshot `.dsml/schema-snapshot.json` in the output folder of the
application. Thus this rule also reads a file, as its catalog row tells.

These changes need the `#Destructive` metadata (PRD-DSML-034, Q19):

- A renamed table: `@Destructive { renamedFrom = "<old name>"; }` on the
  entity.
- A renamed column: `@Destructive { renamedFrom = "<old name>"; }` on the
  field or the relation.
- A dropped column: `#Destructive` on the entity of the table. For a join
  table, `#Destructive` on its relation.
- A dropped table: `#Destructive` on the application, because the model has
  no entity for the table.

A rename with no `renamedFrom` is a drop and an addition, so it also needs
the metadata. If the application has no output folder or no snapshot, the
rule gives no finding.
"""

from collections.abc import Iterator, Mapping

from dsml.config import Configuration
from dsml.database.schema import (
    SchemaError,
    Table,
    application_schema,
    is_destructive,
)
from dsml.database.snapshot import SnapshotError, read_snapshot
from dsml.ir.model import Element, EnumValue, Ir
from dsml.validate.rule import Hit, Rule, implements

# trace: PRD-VAL-015, PRD-APP-127
STR_013 = Rule(
    id="STR-013",
    severity="error",
    message=(
        "The model drops or renames a table or a column, compared with the schema "
        "snapshot, with no #Destructive metadata."
    ),
    fix_hint=(
        'For a rename, add @Destructive { renamedFrom = "<old name>"; } to the entity '
        "or the field. For a dropped column, add #Destructive to the entity. For a "
        "dropped table, add #Destructive to the application."
    ),
)


def _fastapi_applications(ir: Ir) -> list[Element]:
    """Give the applications with the target `fastapi`, sorted by identity."""
    found: list[Element] = []
    for element in ir.elements:
        if element.kind != "Application":
            continue
        for attribute in element.attributes:
            value = attribute.value
            if (
                attribute.name == "target"
                and isinstance(value, EnumValue)
                and value.literal == "fastapi"
            ):
                found.append(element)
    return sorted(found, key=lambda element: element.identity)


# trace: PRD-VAL-015, PRD-APP-127
@implements(STR_013)
def str_013(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    elements = {element.identity: element for element in ir.elements}
    for application in _fastapi_applications(ir):
        settings = configuration.application(application.name)
        if settings is None or settings.output is None:
            continue
        try:
            snapshot = read_snapshot(configuration.root / settings.output)
            if snapshot is None:
                continue
            schema = application_schema(ir, application.identity)
        except (SnapshotError, SchemaError) as error:
            yield Hit(str(error), application.location, application.identity)
            continue
        current = {table.name: table for table in schema.tables}
        renamed = {
            table.renamed_from: table
            for table in schema.tables
            if table.renamed_from is not None and table.renamed_from not in current
        }
        for old in snapshot.tables:
            table = current.get(old.name) or renamed.get(old.name)
            if table is None:
                if not is_destructive(application):
                    yield Hit(
                        f'The model drops or renames the table "{old.name}" of the '
                        f"application {application.name}, with no #Destructive metadata.",
                        application.location,
                        application.identity,
                    )
                continue
            yield from _dropped_columns(old, table, elements)


def _dropped_columns(old: Table, table: Table, elements: Mapping[str, Element]) -> Iterator[Hit]:
    """Give a hit for each column of `old` that `table` does not keep."""
    source = elements.get(table.element or "")
    if source is None or is_destructive(source):
        return
    names = {column.name for column in table.columns}
    names.update(column.renamed_from for column in table.columns if column.renamed_from)
    for column in old.columns:
        if column.name not in names:
            yield Hit(
                f'The model drops or renames the column "{column.name}" of the table '
                f'"{table.name}", with no #Destructive metadata.',
                source.location,
                source.identity,
            )


RULES = (str_013,)
"""The rules of this module."""
