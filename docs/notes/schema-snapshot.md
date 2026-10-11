# Database schema and schema snapshot

Story #61 added the database schema of an application, the schema snapshot `.dsml/schema-snapshot.json` and the rule STR-013. Story #77 added the column types (PRD-APP-121). Story #85 added the column types to the snapshot, and the Alembic migrations.

- Schema from the IR: `src/dsml/database/schema.py`.
- Snapshot reader and writer: `src/dsml/database/snapshot.py`.
- Comparison of two schemas: `src/dsml/database/migration.py`.
- Migration files of the FastAPI generator: `src/dsml/generate/fastapi_migrations.py`.
- Rule STR-013: `src/dsml/validate/rules/str_schema.py`.
- Tests: `tests/test_schema_snapshot.py`, `tests/test_str_013.py` and `tests/test_fastapi_migrations.py`. Rule models: `tests/models/rules/STR-013/`.

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

Each column has a `ColumnType`. A foreign key column has the type of the key field that it refers to. The snapshot keeps the PostgreSQL type and the values of each column. The equality of two `Column` objects ignores the type, so STR-013 ignores a changed type. The migration writer compares the types.

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
  "snapshotVersion": 2,
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
          },
          "type": "UUID",
          "values": []
        }
      ],
      "name": "order"
    }
  ]
}
```

| Key | Value |
| --- | --- |
| `snapshotVersion` | The version of the format. This version is 2. Version 1 had no `type` and no `values`. |
| `tables[].name` | The table name. |
| `tables[].columns[].name` | The column name. |
| `tables[].columns[].nullable` | `true` if the column accepts no value. |
| `tables[].columns[].primaryKey` | `true` if the column is a part of the primary key. |
| `tables[].columns[].references` | The table and the column of a foreign key, or `null`. |
| `tables[].columns[].type` | The PostgreSQL type of the column, for example `VARCHAR(500)`, or `null` for a type that is not supported. |
| `tables[].columns[].values` | The values of the `CHECK` constraint of an enumeration column, sorted. An empty list for other columns. |

The reader accepts only version 2. A snapshot of version 1 gives a `SnapshotError`. No project has a snapshot of version 1, because no generator wrote version 1.

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

## Migrations

The FastAPI generator writes the snapshot and the migrations of each application that has entities (PRD-APP-124 to PRD-APP-128). The snapshot is a generated file. Its path is on the list `STATE_FILES` of the generator, because its name does not end with `.gen.json`.

At each run, the generator does these steps:

1. It reads the snapshot and the files `migrations/versions/<NNNN>_<slug>_gen.py` in the output folder.
2. It compares the snapshot with the schema of the IR (`compare`).
3. It gives each old migration file to the file writer again, byte for byte (PRD-APP-126).
4. If the schemas are different, it writes one new migration with the next number, and the new snapshot.

If the folder has migrations but no snapshot, or a snapshot with tables but no migration, the generator stops with an error.

The revision ID of a migration is the first 12 characters of the SHA-256 hash of the number and the content. The content has 12 zeros in place of the revision ID for the hash. The `down_revision` of a migration is the revision ID of the migration before it (PRD-APP-125).

A migration does the changes in this order:

1. Rename the tables, the columns and the constraints.
2. Drop the changed constraints, the dropped columns and the dropped tables.
3. Create the new tables. Each table comes after the tables that it refers to. In a cycle, the foreign key goes to step 5.
4. Add the new columns, then change the types and the nullable flags.
5. Add the new and the changed constraints.

The constraint names come from `NAMING_CONVENTION` in `app/shared/db/base_gen.py`. A name of more than 63 characters gets the short form that SQLAlchemy gives. A renamed table or column also renames the constraints that have its name.

A drop needs the `#Destructive` metadata of STR-013. The generator also stops with an error if the metadata is missing (PRD-APP-127).

The migrations go forward only. The function `downgrade` stops with an error.

These are limits of the migrations. The developer must examine each new migration before a deployment:

- A new column that is not nullable needs an empty table, because the migration gives no default value.
- A column that becomes not nullable must have a value in each row.
- A changed type uses the PostgreSQL cast `USING "<column>"::<type>`. Some casts fail, for example from `TEXT` to `UUID` for a text that is not a UUID.

The other generated files are:

| File | Purpose |
| --- | --- |
| `alembic.ini` | The Alembic configuration. It gives the folder `migrations`. |
| `migrations/env.py` | The Alembic environment. It gives `Base.metadata` with all models, so that `alembic check` compares the database with the models. |
| `app/migrate_gen.py` | Applies the migrations that the database does not have, and then stops (PRD-APP-128). The one-off migration task runs `python -m app.migrate_gen` (Q53). |
| `tests/test_migrations_gen.py` | Checks the order of the migrations and writes their SQL in offline mode. |

The CI job "FastAPI golden project" applies the migrations of the golden project to PostgreSQL 18. A second run of `app/migrate_gen.py` must apply nothing. Then `alembic check` must find no difference.
