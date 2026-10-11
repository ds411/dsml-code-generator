# Database schema and schema snapshot

Story #61 added the database schema of an application, the schema snapshot `.dsml/schema-snapshot.json` and the rule STR-013. Story #77 added the column types (PRD-APP-121). The M6 migration story adds the Alembic migrations, and adds the column types to the snapshot.

- Schema from the IR: `src/dsml/database/schema.py`.
- Snapshot reader and writer: `src/dsml/database/snapshot.py`.
- Rule STR-013: `src/dsml/validate/rules/str_schema.py`.
- Tests: `tests/test_schema_snapshot.py` and `tests/test_str_013.py`. Rule models: `tests/models/rules/STR-013/`.

## Tables and columns

The function `application_schema(ir, application)` gives the tables of one application. It reads only the IR (PRD-CORE-026).

The entities of an application are:

1. The entities that the application exposes.
2. The entities that type a parameter of an operation that the application exposes.
3. Each entity that a relation of an entity of the application refers to.

| Model element | Schema |
| --- | --- |
| Entity | One table. The table name is the entity name in snake case (PRD-APP-120). |
| Field | One column with the field name in snake case. `#Key` gives a primary key column. The lower multiplicity 0 gives a nullable column. |
| `[0..1]` or `[1]` relation | A foreign key column `<relation>_<key>` for each key field of the related entity (PRD-APP-122). |
| `[*]` relation | A join table `<table>_<relation>` with a foreign key column for each key field of the two entities (PRD-APP-122). |

If the related entity of a `[*]` relation has a `[0..1]` or `[1]` relation back to the entity, the two relations are one one-to-many relation. Then the foreign key holds the link, and there is no join table.

## Column types

Each column has a `ColumnType`. A foreign key column has the type of the key field that it refers to. The snapshot does not keep the type at this time, and a comparison of two columns ignores it.

| DSML field type | PostgreSQL type |
| --- | --- |
| `String` with `maxLength` | `VARCHAR(<maxLength>)` |
| `String` with no `maxLength` | `TEXT` |
| `Integer` | `BIGINT` |
| `Real` | `DOUBLE PRECISION` |
| `Decimal` | `NUMERIC(<precision>, <scale>)`, default `NUMERIC(18, 4)` |
| `Boolean` | `BOOLEAN` |
| `Date` | `DATE` |
| `DateTime` | `TIMESTAMPTZ` |
| `Uuid` | `UUID` |
| Enumeration | `VARCHAR(64)`. The literals are the values of the `CHECK` constraint. |

The `@FieldRules` attributes `maxLength`, `precision` and `scale` give the parameters. A field type that is not supported (STR-007) gives the type `None`.

For the example model, the application `orderApi` has one table `order` with the columns `id`, `note`, `status` and `total`.

Two tables with the same name, or two columns of one table with the same name, give a `SchemaError`.

## Snapshot format

The snapshot is in the output folder of the application: `<output>/.dsml/schema-snapshot.json` (PRD-APP-124). It is canonical JSON, as the IR (Q16):

- The object keys are in sorted order.
- The tables and the columns of each table are sorted by name.
- The text is UTF-8 with no byte order mark, 2 spaces of indent, LF line ends and one LF at the end.

```json
{
  "snapshotVersion": 1,
  "tables": [
    {
      "columns": [
        {
          "name": "customer_id",
          "nullable": false,
          "primaryKey": false,
          "references": {
            "column": "id",
            "table": "customer"
          }
        }
      ],
      "name": "order"
    }
  ]
}
```

| Key | Value |
| --- | --- |
| `snapshotVersion` | The version of the format. This version is 1. |
| `tables[].name` | The table name. |
| `tables[].columns[].name` | The column name. |
| `tables[].columns[].nullable` | `true` if the column accepts no value. |
| `tables[].columns[].primaryKey` | `true` if the column is a part of the primary key. |
| `tables[].columns[].references` | The table and the column of a foreign key, or `null`. |

The M6 migration story adds the PostgreSQL type of each column. That change increases `snapshotVersion`.

`read_snapshot(folder)` gives `None` if there is no snapshot. A file that is not correct gives a `SnapshotError` with the cause. `write_snapshot(folder, schema)` writes the file, and `snapshot_bytes(schema)` gives its bytes.

## Rule STR-013

STR-013 compares the schema of each FastAPI application with its snapshot. The rule also reads a file, as its catalog row tells. If the configuration gives no output folder for the application, or the folder has no snapshot, the rule gives no finding.

| Change | Metadata that permits it |
| --- | --- |
| Renamed table | `@Destructive { renamedFrom = "<old entity name>"; }` on the entity. |
| Renamed column | `@Destructive { renamedFrom = "<old field name>"; }` on the field or the relation. |
| Dropped column | `#Destructive` on the entity. For a join table, `#Destructive` on its relation. |
| Dropped table | `#Destructive` on the application. |

A rename with no `renamedFrom` is a drop and an addition. Thus it also needs the metadata.

PRD-DSML-034 puts the metadata "on the changed entity or field". A dropped table has no entity in the model, so STR-013 uses the metadata on the application. This is a default of story #61, not a decision of the product owner.

A snapshot that is not correct gives one STR-013 finding on the application.
