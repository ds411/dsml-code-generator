# Toolchain core PRD: CLI, IR and determinism

Status date: 10 October 2026

## Summary

The toolchain core reads the model with OpenSysML, writes the IR and runs the validators and generators from one command, `dsml`. It also makes the determinism and generation gap rules that all generators obey.

- **Phase:** 1.
- **Goals covered:** N-002 (deterministic generation) and N-003 (correct model).
- **Prefix:** PRD-CORE.
- **Related PRDs:** the validation PRD gives the rules, the traceability PRD gives the reports, and the generation PRDs give the output of each generator.

## Command line interface

One command, `dsml`, has seven subcommands. All subcommands work in CI with no person present.

| Subcommand | What it does | Main options |
| --- | --- | --- |
| `dsml init` | Writes a starter configuration file and a starter model, as create-once files. | `--target` |
| `dsml validate` | Validates the model and writes the findings. | `--format text\|json\|sarif`, `--output`, `--baseline` |
| `dsml generate` | Validates the model, then writes all generated files. | `--application`, `--infrastructure`, `--pipelines`, `--check` |
| `dsml trace` | Writes a trace report: `coverage`, `orphans`, `impact` or `suspect`. | `--format html\|csv\|json`, `--baseline`, `--output` |
| `dsml ir` | Writes the IR as JSON. | `--output` |
| `dsml check-output` | Runs the language tools on the generated code. | `--application`, `--infrastructure` |
| `dsml version` | Writes the versions of the toolchain, the DSML library, OpenSysML and the IR schema. | none |

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-CORE-001 | The command `dsml` must have the seven subcommands `init`, `validate`, `generate`, `trace`, `ir`, `check-output` and `version`, with the options in the table of the section "Command line interface". | Demonstration | Q5, Q61 |
| PRD-CORE-002 | Each subcommand must stop with exit code 0 if it finds no error, 1 if it finds an error finding or a `--check` difference, and 2 if a usage error or an internal error occurs. | Test | Q28 |
| PRD-CORE-003 | `dsml generate` must validate the model first. If there is an error finding, it must stop and write no file. | Test | Q28 |
| PRD-CORE-004 | `dsml generate --check` must write no file. It must list each file that a normal run would add, change or delete. | Test | Q43 |
| PRD-CORE-005 | `dsml generate` must generate only one part of the output when the user gives `--application <name>`, `--infrastructure` or `--pipelines`. | Test | Q18 |
| PRD-CORE-006 | Each subcommand must write its report to standard output, or to the file that `--output` gives. | Test | Q28, Q31 |
| PRD-CORE-007 | A message about a model location must give the file path, the line and the column. | Test | Q28 |
| PRD-CORE-008 | Messages to the user must use ASD-STE100 Issue 9. | Inspection | Q1 |
| PRD-CORE-009 | A subcommand must not ask for input from a terminal. | Test | Q25 |
| PRD-CORE-010 | The option `--verbose` must write debug messages to standard error. | Test | PRD-TOP-006 |
| PRD-CORE-011 | `dsml check-output` must run `tsc`, `ruff`, `tofu validate`, `tflint` and the FSD linter Steiger on the generated code of the selected targets. It must report a missing tool as an error with the tool name. | Test | Q28 |

## Configuration file

One TOML file, `dsml.toml`, configures the toolchain for a repository. The model, the configuration file and the toolchain version are the only inputs to code generation.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-CORE-012 | The toolchain must read its configuration from `dsml.toml` in the repository root, or from the file that the option `--config` gives. | Test | Q5 |
| PRD-CORE-013 | The configuration file must give: the model files or folders; the output folder of each application, of the infrastructure and of the pipelines; the ID patterns; the optional rule sets; the default trace baseline; and the IaC options for one tool only. | Inspection | Q22, Q45 |
| PRD-CORE-014 | The configuration file must have a schema version. The toolchain must report an unknown key or an unknown schema version as an error. | Test | Q16 |
| PRD-CORE-015 | Environment variables, the user name, the host name, the locale, the time zone and the clock must not change the generated output. | Test | Q16 |
| PRD-CORE-016 | The configuration file must not contain secret values. | Inspection | PRD-TOP-006 |

## OpenSysML integration and the IR

OpenSysML stays behind one adapter module. The adapter writes the IR, and only the IR reaches the validators and generators. The adapter also evaluates the formal constraints and writes the results into the IR. OpenSysML 0.9.2 is not at version 1.0, so golden IR tests protect each version change ([OpenSysML](https://pkg.go.dev/github.com/Open-MBEE/OpenSysML)).

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-CORE-017 | The toolchain must call OpenSysML through the `opensysml` Python client. The client must start `sysml-grpc` as a private child process. | Test | Q38 |
| PRD-CORE-018 | The toolchain must pin one OpenSysML version for the Python package and the `sysml-grpc` binary. The version must come from the version baseline. | Test | Q38, Q49 |
| PRD-CORE-019 | At start, the toolchain must compare the version of `sysml-grpc` with the pinned version. If they are different, it must stop with exit code 2. | Test | Q38 |
| PRD-CORE-020 | Only the IR adapter module must import the `opensysml` package. A lint rule in the toolchain CI must enforce this. | Test | Q8 |
| PRD-CORE-021 | The adapter must convert each OpenSysML diagnostic into a finding of the category SYN of the validation PRD. | Test | Q27 |
| PRD-CORE-022 | The IR must be JSON. The toolchain package must contain the JSON Schema of the IR. | Test | Q8 |
| PRD-CORE-023 | The IR must have a semantic version in the field `irVersion`. A change that removes or renames a field must increase the major version. | Inspection | Q8 |
| PRD-CORE-024 | The IR must hold each element of the five layers, its DSML attributes, its trace links and its source location (file, line, column). | Test | Q8, Q29 |
| PRD-CORE-025 | The IR must not contain an OpenSysML type, an OpenSysML object or an OpenSysML internal ID. | Inspection | Q8 |
| PRD-CORE-026 | Validators and generators must read only the IR. They get the results of formal constraints from the IR (PRD-CORE-054), not from OpenSysML. | Inspection | Q8, Q57 |
| PRD-CORE-027 | The toolchain CI must compare the IR of each reference model with a stored golden IR file. A change of the OpenSysML version must pass this comparison before a release. | Test | Q38 |
| PRD-CORE-054 | The adapter must evaluate each formal constraint of a requirement through OpenSysML, one time for each environment, and write each result into the IR. The evaluation uses the attribute values of that environment. A result is `true`, `false` or `unknown`. An `unknown` result gives the features that have no value. | Test | Q12, Q57 |

## Determinism

The model, the configuration file and the toolchain version are the full input. Each output is byte-identical for the same input on each supported operating system.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-CORE-028 | The same model, configuration file and toolchain version must give byte-identical generated files, IR, reports and trace manifests on each supported operating system. | Test | Q16, N-002 |
| PRD-CORE-029 | The toolchain CI must run each reference model on Linux x64, Linux arm64 and macOS arm64, and compare the outputs byte by byte. | Test | Q16, Q50 |
| PRD-CORE-030 | The toolchain CI must compare the output of each reference model with stored golden files. | Test | Q16 |
| PRD-CORE-031 | Generators must write each list in an output file in a defined order: by element identity, then by name. | Test | Q16 |
| PRD-CORE-032 | The output must not depend on the order of the model files on disk or in the configuration file. | Test | Q16 |
| PRD-CORE-033 | The output must not contain a timestamp, a random value, an absolute path, a user name or a host name. | Test | Q16 |
| PRD-CORE-034 | Each output file must use UTF-8 with no byte order mark, LF line ends and one LF at the end of the file. | Test | Q16 |
| PRD-CORE-035 | Templates must give their output in the format of the pinned formatter for the file type: Prettier for TypeScript, `ruff format` for Python, `tofu fmt` for HCL. The generator must not run a formatter. The toolchain CI must run each formatter in check mode on the golden files and find no change. | Test | Q16 |
| PRD-CORE-036 | The generator must not write lockfiles (`uv.lock`, `pnpm-lock.yaml`, `.terraform.lock.hcl`). The generated CI makes them, and Git keeps them. | Inspection | Q16 |
| PRD-CORE-037 | A minor or patch release of the toolchain must not change the output for an unchanged model, except to fix a defect that its release notes name. | Inspection | Q16 |
| PRD-CORE-038 | The header of a generated file must give the major version of the toolchain only. | Test | Q16, Q30 |

## Generated files and hand-written files

The generator owns generated files and writes them again at each run. Developers own hand-written files, and the generator never changes them. A manifest records which file is which.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-CORE-039 | A generated file must have a name that ends with `.gen.<ext>` or `_gen.py`, or be on the fixed-name list of its target. Each generation PRD gives its fixed-name list, for example `pyproject.toml`, `package.json`, `Dockerfile` and the Next.js `app/` folder. | Test | Q15, Q34 |
| PRD-CORE-040 | The generator must keep a manifest in `.dsml/generated.json`. For each generated file, it must give the path and the SHA-256 hash. For each create-once file, it must give the path. | Test | Q15 |
| PRD-CORE-041 | At each run, the generator must delete each generated file of the old manifest that the new run does not write. | Test | Q15 |
| PRD-CORE-042 | The generator must not write, change or delete a file that is not a generated file of the old or new manifest, except a new create-once file. | Test | Q15 |
| PRD-CORE-043 | If the hash of a generated file is different from its hash in the manifest, `dsml generate` must stop with an error that lists the changed files. The option `--overwrite` must replace them. | Test | Q15 |
| PRD-CORE-044 | The generator must write a create-once file only if no file exists at its path. | Test | Q15, Q34 |
| PRD-CORE-045 | Generated code must call hand-written code through a typed interface, for example a handler function with typed parameters. A difference between the two must cause a type check error. | Inspection | Q15 |
| PRD-CORE-046 | The generator must own the dependency lists of each target. A developer must add a dependency in the configuration file, not in a generated file. | Test | Q17, Q56 |

## Packaging, GitHub Action and releases

The toolchain is one Python package on the internal package index, plus one GitHub Action that the generated workflows use.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-CORE-047 | The toolchain must be a Python package that uv builds. The release process must publish it to the internal package index. A user must be able to install it with `uv tool install`. | Demonstration | Q4, Q5 |
| PRD-CORE-048 | The package must contain the DSML library, the IR schema, the templates and the pinned copy of the shadcn/ui components. | Test | Q41, PRD-DSML-006 |
| PRD-CORE-049 | The installation must supply the `sysml-grpc` binary of the pinned OpenSysML version and check its SHA-256 hash against the release checksums of OpenSysML. | Test | Q38 |
| PRD-CORE-050 | The toolchain must supply a GitHub Action that installs a pinned toolchain version and runs one subcommand. | Test | Q5, Q25 |
| PRD-CORE-051 | When its input `sarif` is `true`, the GitHub Action must upload the SARIF findings to GitHub code scanning. | Test | Q28 |
| PRD-CORE-052 | Toolchain releases must use semantic versioning. The release notes must name each change to the generated output. | Inspection | Q16 |
| PRD-CORE-053 | Before each release, the toolchain CI must generate and deploy each reference model to a sandbox AWS account, and remove it after the test. | Test | Q6 |
