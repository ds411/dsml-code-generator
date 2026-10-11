# File writer and manifest

Story #36 added the file writer of all generators, the manifest `.dsml/generated.json` and the subcommand `dsml generate`. The real generators are not in this story (M5, M6, M7). Until they exist, the list of generators is empty, and the tests use a test generator.

- File writer: `src/dsml/generate/writer.py`.
- Manifest: `src/dsml/generate/manifest.py`.
- Generator interface and list: `src/dsml/generate/generators.py`.
- Subcommand: `run_generate` in `src/dsml/cli.py`.
- Tests: `tests/test_generate.py`. The test generator is `StaticGenerator` in this file.

## Output files

A generator writes no file. It gives the full list of its output files to the file writer. Each output file has these properties:

| Property | Value |
| --- | --- |
| Path | A relative path with "/", from the folder of the configuration file. The path must not contain "..", "\\" or ":". It must not be in `.dsml/` or `.git/`. |
| Bytes | UTF-8 text with no byte order mark, LF line ends and one LF at the end (PRD-CORE-034). |
| Kind | `generated` or `create-once`. |
| Part | `application/<name>`, `infrastructure` or `pipelines` (PRD-CORE-005). |

The writer checks each output file. An error in the output of a generator is a defect of the toolchain, so the command stops with exit code 2:

- The name of a generated file must end with `.gen.<ext>` or `_gen.py`, or agree with the fixed-name list of its generator (PRD-CORE-039). A create-once file can have any name.
- An item of the fixed-name list with no "/" agrees with each file of that name, for example `pyproject.toml`. An item with "/" agrees with each path that ends with it, for example `migrations/env.py`. An item that ends with "/" agrees with each file in a folder of that name, for example the Next.js `app/` folder.
- The generator must not write the lockfiles `uv.lock`, `pnpm-lock.yaml` and `.terraform.lock.hcl` (PRD-CORE-036).
- Two output files must not have the same path.

## Manifest

The manifest `.dsml/generated.json` is in the folder of the configuration file. It is canonical JSON: sorted keys, lists sorted by path, two spaces of indent, UTF-8 and one LF at the end (PRD-CORE-040).

```json
{
  "createOnce": [
    {
      "part": "application/orderApi",
      "path": "services/orders/handler.py"
    }
  ],
  "generated": [
    {
      "part": "application/orderApi",
      "path": "services/orders/api_gen.py",
      "sha256": "<64 hexadecimal digits>"
    }
  ],
  "manifestVersion": 1
}
```

The manifest gives the part of each file. Thus a run of one part keeps the entries and the files of the other parts.

## Rules of a run

| Case | Result |
| --- | --- |
| A new generated file, and no file at its path | Add the file. |
| A generated file of the old manifest, and the file is the same as its hash | Replace the file. |
| A generated file of the old manifest that the new run does not give | Delete the file (PRD-CORE-041). Then delete each folder that becomes empty. |
| A generated file that is different from its hash in the old manifest | Conflict "changed" (PRD-CORE-043). |
| A file at the path of a new generated file, but not a generated file of the old manifest | Conflict "not in manifest" (PRD-CORE-042). |
| A create-once file, and no file at its path | Add the file. |
| A create-once file, and a file at its path | Do not touch the file (PRD-CORE-044). |
| A file that is not a generated file of the old or the new manifest | Do not touch the file (PRD-CORE-042). |

The function `write_create_once` writes only create-once files, with the same rule. It does not read or write the manifest. `dsml init` uses it for the starter files (story #38).

If there is a conflict, `dsml generate` writes no file. It lists the conflicts and stops with exit code 1. With `--overwrite`, it replaces or deletes the files of the conflicts.

A conflict is not an internal error or a usage error, so the exit code is 1, not 2 (PRD-CORE-002). The user must look at the listed files.

## Subcommand `dsml generate`

1. Read the configuration and the model files of the key `model.paths`.
2. Make the IR. If the IR has an error finding, write the findings to standard error, write no file and stop with exit code 1 (PRD-CORE-003). The validator of M4 adds its findings to this step.
3. Run the generators of the selected parts. `--application <name>`, `--infrastructure` and `--pipelines` select parts. The options can go together. With no option, the run selects all parts (PRD-CORE-005).
4. Compare the output files with the old manifest and with the files on disk.
5. With `--check`, write no file. List each file to add, change or delete, and stop with exit code 1 if there is a difference (PRD-CORE-004). A conflict is a change in this list.
6. Write and delete the files. Then write the manifest. The report lists each file to add, change or delete, one line for each file, for example `add services/orders/api_gen.py`.

The manifest is also in the list of changes. Thus `dsml generate --check` finds a manifest that does not agree with the files.
