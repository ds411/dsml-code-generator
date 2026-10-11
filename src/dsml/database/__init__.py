# trace: PRD-APP-120, PRD-APP-122, PRD-APP-124
"""The database schema of an application and its schema snapshot.

- `dsml.database.schema` gets the tables and the columns of one application
  from the IR.
- `dsml.database.snapshot` reads and writes the schema snapshot
  `.dsml/schema-snapshot.json`.

`docs/notes/schema-snapshot.md` gives the rules and the file format.
"""
