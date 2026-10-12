# Trace manifest

Story #70 added the symbol interface of the generators and the trace manifest `.dsml/trace.gen.json` (PRD-TRACE-006 to PRD-TRACE-008). The real generators are not in this story. Each M6 generator story gives the symbols of its files.

- Symbols and trace manifest: `src/dsml/generate/trace.py`.
- File writer: `src/dsml/generate/writer.py`. The writer makes the trace manifest from the symbols of the generated files.
- Tests: `tests/test_trace_manifest.py` and `tests/test_generate.py`.
- Golden file: `tests/golden/trace/order-service.trace.gen.json`. The test generator `IrGenerator` in `tests/dsml_test_command.py` writes it for the example model.
- Golden file of a real generator: `tests/golden/react/order-portal/.dsml/trace.gen.json`. The React generator writes it for the order portal model (story #177).

## Symbols

A generator gives the symbols of each generated file in the field `symbols` of `OutputFile`. Each symbol is a `Symbol` with these properties:

| Property | Value |
| --- | --- |
| `kind` | `class`, `function`, `route`, `resource` or `job`. |
| `name` | The name of the class or function, the method and path of a route (for example `POST /orders`), the HCL resource address (for example `aws_ecs_service.order_api`), or the ID of a workflow job (for example `plan-dev`). |
| `first_line`, `last_line` | The line range of the symbol. The first line of the file is line 1. The range includes the two lines. |
| `elements` | The identities of the model elements of the symbol. A symbol must have one or more elements. |

The file writer checks the symbols. An error stops the command with exit code 2, because it is a defect of the toolchain:

- The line range must be in the file, and the first line must not be after the last line.
- The name and each element identity must not be empty. They must not have a line break or a space at the start or at the end.
- A create-once file must not have symbols. A developer owns a create-once file, so its symbols can become wrong.

For an infrastructure element, the generator gives one `resource` symbol for each HCL resource. The elements of the symbol are the AWS realization and the logical element that it realizes. Thus the manifest gives the addresses of each infrastructure element (PRD-TRACE-007).

A file with no symbols is not in the trace manifest. The header of the file still gives its elements (PRD-TRACE-005).

## Format

The trace manifest is in the folder of the configuration file. It is canonical JSON, like `.dsml/generated.json`: sorted keys, two spaces of indent, UTF-8 and one LF at the end.

```json
{
  "elements": [
    {
      "element": "OrderService::apiService",
      "files": [
        {
          "path": "infra/main.gen.tf",
          "symbols": [
            {
              "firstLine": 4,
              "kind": "resource",
              "lastLine": 8,
              "name": "aws_ecs_service.api_service_aws"
            }
          ]
        }
      ]
    }
  ],
  "traceVersion": 1
}
```

- `elements` has one item for each element identity that has one or more symbols.
- `files` has one item for each generated file with a symbol of the element.
- `symbols` has the symbols of the element in the file.
- A symbol with two or more elements is in the list of each element.

The sort order is: element identity, then file path, then first line (PRD-TRACE-008). Symbols with the same first line are sorted by last line, then by kind, then by name. Identities and paths are sorted by their code points, so `OrderService::Order` comes before `OrderService::apiService`.

## Rules of a run

- `dsml generate` writes the trace manifest at each run, also when there are no symbols. Then `elements` is an empty list.
- The trace manifest is in the list of changes, like `.dsml/generated.json`. Thus `dsml generate --check` reports a trace manifest that is missing or not current (PRD-CORE-004).
- A run of some parts keeps the entries of the generated files of the other parts (PRD-CORE-005). For this, the writer reads the old trace manifest. If the old trace manifest is not correct, the command stops with exit code 2. A run of all parts does not read the old trace manifest, so it writes a correct trace manifest again.
- The trace manifest is not in `.dsml/generated.json` and has no hash. If a person changes it, the next run replaces it with no conflict.
