# DSML toolchain: PRD bundle

Status date: 10 October 2026. All decisions (Q1 to Q61, AD1 to AD3) are closed. The text uses ASD-STE100 Simplified Technical English, Issue 9.

## Contents

```text
CLAUDE.md                                  Project brief for Claude Code
docs/
├── prd/
│   ├── 00-top-level-prd.md                Goals, users, architecture, phases, conventions, dictionary
│   ├── 01-dsml-prd.md                     PRD-DSML
│   ├── 02-toolchain-core-prd.md           PRD-CORE
│   ├── 03-application-generation/         PRD-APP, one file for each target
│   ├── 04-infrastructure-generation-prd.md  PRD-IAC
│   ├── 05-cicd-generation-prd.md          PRD-CICD
│   ├── 06-validation-prd.md               PRD-VAL
│   └── 07-traceability-prd.md             PRD-TRACE
├── decisions/                             Decision records 01 to 09
├── model/
│   ├── README.md
│   ├── prd/*.sysml                        All PRD requirements as a DSML model
│   └── examples/order-service.sysml       Example model with all five layers
└── index/
    ├── requirements.csv                   One row for each PRD requirement
    └── decisions.csv                      One row for each decision
```

## Development

The toolchain is a Python 3.14 project that uv manages. pnpm manages only the Node.js dev tools, for example the type checker pyright. pnpm also installs the Node.js runtime that `package.json` gives (Node.js 26). The package is in `src/dsml/`, and the tests are in `tests/`.

1. Install uv and pnpm 12.
2. Install Python 3.14 and the dependencies:

   ```sh
   uv python install 3.14
   uv sync
   pnpm install
   ```

3. Get the `sysml-grpc` binary of OpenSysML and check its SHA-256 hash. After this step, the toolchain does not use the network:

   ```sh
   uv run python -m dsml.adapter.binary
   ```

4. Run the command `dsml`:

   ```sh
   uv run dsml version
   ```

5. Run the checks. Each check must pass before you open a pull request:

   ```sh
   uv run ruff check
   uv run ruff format --check
   pnpm typecheck
   uv run pytest
   ```

6. Build the package. The wheel and the source archive go to `dist/`:

   ```sh
   uv build
   ```

`docs/release.md` gives the steps of a release, from the tag to the installation with `uv tool install`. `CHANGELOG.md` gives the changes of each release.

In a Claude Code cloud session, the SessionStart hook `.claude/hooks/session-start.sh` does steps 1 and 2 at the start of the session.

### CI

The workflow `.github/workflows/ci.yml` runs the checks of step 5 on each pull request and on each push to `main`. It runs only on Linux x64 (`ubuntu-24.04`), as decision record 07 gives (Q62). The steps are:

1. `uv sync --frozen`
2. `pnpm install --frozen-lockfile`
3. `uv run ruff check`
4. `uv run ruff format --check`
5. `pnpm typecheck`
6. `uv run pytest`

The job "Infrastructure golden HCL" checks the golden HCL in `tests/golden/infrastructure/` (PRD-IAC-003, PRD-IAC-039, PRD-IAC-040). On each root module, it runs `tofu fmt -check`, `tofu validate`, `terraform validate` and `tflint` with the AWS rule set. Then Checkov scans the golden HCL. The job gets the tool versions from `src/dsml/versions.toml`. `.tflint.hcl` and `.checkov.yaml` give the settings of tflint and Checkov.

The workflow `.github/workflows/pilot.yml` checks the DSML library with the Jupyter kernel of the OMG pilot implementation (PRD-DSML-005, Q60). It runs on Linux x64 when the library or the check changes. To run the check on your computer, install Java 17 or later and use this command:

```sh
uv run python scripts/check_pilot.py src/dsml/library/DSML.sysml
```

Only the IR adapter module `src/dsml/adapter/` can import `opensysml` (PRD-CORE-020). The ruff rule TID251 in `pyproject.toml` enforces this. An import of `opensysml` in a different file causes `uv run ruff check` and the CI to fail.

The file `src/dsml/versions.toml` holds the version baseline of decision record 03 (Q49). To change a pinned version, change this file.

## Command `dsml`

The command `dsml` has seven subcommands (PRD-CORE-001). `dsml --help` lists them, and `dsml <subcommand> --help` gives the options of one subcommand.

| Subcommand | Status |
| --- | --- |
| `init` | Writes a starter configuration file and a starter model as create-once files. See "Command `dsml init`". |
| `validate` | Runs the validation rules on the model and writes the findings as text, JSON or SARIF. See "Command `dsml validate`". |
| `trace` | Writes the coverage report or the orphans report as JSON or as CSV. See "Command `dsml trace`". |
| `check-output` | Runs the language tools on the generated code: ruff and pyright on each FastAPI application, and `tofu fmt`, `tofu init`, `tofu validate` and `tflint` on the infrastructure. A tool error or a missing tool gives exit code 1. `docs/notes/check-output.md` gives the rules. |
| `generate` | Validates the model, then writes the generated files through the file writer and keeps the manifest `.dsml/generated.json`. An error finding stops it before it writes a file. The infrastructure generator writes the root modules of the environments and the local modules of the databases and the user directories. The other generators come in M6. `docs/notes/file-writer.md` gives the rules. |
| `ir` | Writes the IR of the model files as JSON. See "Command `dsml ir`". |
| `version` | Writes the versions of the toolchain, the DSML library, OpenSysML and the IR schema. |

Each subcommand has these common options:

- `--config <file>`: read the configuration from this file. The default is `dsml.toml`. `docs/configuration.md` gives all keys of the file.
- `--output <file>`: write the report to this file, not to standard output.
- `--verbose`: write debug messages to standard error.

The exit codes are (PRD-CORE-002):

- 0: the subcommand found no error.
- 1: the subcommand found an error finding or a `--check` difference.
- 2: a usage error or an internal error occurred. The command writes a short message, not a traceback. With `--verbose`, the traceback is a debug message.

No subcommand reads from a terminal (PRD-CORE-009).

### Command `dsml init`

`dsml init [--target fastapi|react]` writes two starter files in the current folder:

- `dsml.toml`: a configuration file that reads the model in the folder `model`.
- `model/model.sysml`: a model with one stakeholder, one need, one requirement and the `@DsmlVersion` metadata. It parses and resolves with the DSML library.

With `--target react`, the starter model also has a FastAPI application `itemApi` and a React application `itemPortal` that calls it. It also has the infrastructure, the tooling account and the environments `dev`, `staging` and `prod`. Replace the account IDs, the regions and the domains with real values. `dsml.toml` gives the output folders `services/item-api` and `apps/item-portal`. `dsml validate` finds no error, and `dsml generate` writes the two projects.

The files are create-once files (PRD-CORE-044). The command writes a file only if no file exists at its path. For a file that exists, the report gives the line `keep <path>: The file exists. The command did not change it.` The command writes no manifest. `dsml generate` writes the manifest.

- The command accepts the targets `fastapi` and `react`. The default target is `fastapi`. M11 adds the target `nextjs`.
- With `--config <file>`, the command writes the configuration file at this path, and the model in the folder of this file.
- The starter files are package data in `src/dsml/starter/<target>/`.

### Command `dsml ir`

`dsml ir [<model-file>...]` parses the model files with the DSML library and writes the IR as JSON. For example:

```sh
uv run dsml ir docs/model/prd/*.sysml --output prd.ir.json
```

- The model files must be in the current folder or below it. The IR gives each file name relative to the current folder.
- If the command line gives no model file, the command reads the model files of the key `model.paths` in the configuration file.
- The exit code is 1 if the IR has an error finding, for example SYN-001. The command writes the IR also in this case.

### Command `dsml validate`

`dsml validate [--format text|json|sarif] [--fail-on error|warning] [--baseline <git-ref>] [--date <YYYY-MM-DD>]` reads the model files of the key `model.paths`, runs all enabled rules on the IR and writes the findings. For example:

```sh
uv run dsml validate --format json --output findings.json
```

- The findings are sorted by file, line, column and rule ID (PRD-VAL-007).
- The text format gives one line for each finding, then one line with the fix hint of the rule. The last line gives the number of findings of each severity. This is the default format.
- The JSON format gives the list `findings`, the list `waived` and the object `summary`.
- A `@Waiver` on an element stops the findings of one rule on that element (PRD-VAL-009). The reports give the waived findings in a separate group, and SARIF gives them as suppressions with the reason. A waived finding does not change the exit code.
- After the `expires` date of a waiver, its findings come back, and the validator reports STR-014 (PRD-VAL-010). `--date` gives the date of this check. The default is the commit date of `HEAD`, thus the clock does not change the report. `docs/notes/validator.md` tells more.
- The SARIF format gives a SARIF 2.1.0 log for GitHub code scanning (PRD-VAL-006). `tool.driver.rules` has the metadata of each rule: the ID, the message, the fix hint as help text and the default severity. The levels are `error`, `warning` and `note` (for `info`). Each URI is relative to the folder of the configuration file.
- The exit code is 1 if there is a finding with the severity `error`. With `--fail-on warning`, the exit code is also 1 if there is a warning (PRD-VAL-005).
- The keys `rules.severity` and `rules.optional` of the configuration file change the severities and turn on the optional rule sets. `docs/configuration.md` gives the rules.
- The identity rules (IDN) run only with a baseline: `--baseline <git-ref>`, or the key `trace.baseline` of the configuration file (PRD-VAL-011). The toolchain reads the baseline model from the local Git repository. A Git reference that does not exist stops the command with exit code 2.

The rules are in `src/dsml/validate/rules/`. `docs/notes/validator.md` tells how to add a rule.

Each reference model has a configuration file in its folder: `docs/model/examples/dsml.toml` for the example model and `docs/model/prd/dsml.toml` for the PRD model. To validate the example model, run this command from the root of the repository:

```sh
uv run dsml validate --config docs/model/examples/dsml.toml
```

- The example model has no error finding. CI runs this command in the step "Validate the example model".
- The golden findings of the two reference models are in `tests/golden/validate/`, as text, JSON and SARIF. CI compares the findings with these files. After a change of the findings, run `uv run python scripts/write_golden_findings.py` and examine the differences before you commit them.
- `tests/test_rule_catalog.py` makes sure that the validator contains each rule of the catalog in `docs/prd/06-validation-prd.md` with its default severity (PRD-VAL-015). It also makes sure that each rule has one model that it accepts and one model that it rejects (PRD-VAL-008).

The golden IR files of the two reference models are in `tests/golden/ir/`. CI compares the IR with these files on Linux x64 (PRD-CORE-027, PRD-CORE-029). After a change of the IR, run `uv run python scripts/write_golden_ir.py` and examine the differences before you commit them.

### Command `dsml trace`

`dsml trace <report> --format html|csv|json [--baseline <git-ref>]` reads the model, the trace manifest `.dsml/trace.gen.json` and the trace comments in the hand-written files. Then it writes one report (PRD-TRACE-013). For example:

```sh
uv run dsml trace coverage --format csv --output coverage.csv
```

- The report `coverage` has one row for each requirement: its needs, its satisfying elements, its generated files, its trace comments, its verifications and its status. The status is `missing` (no satisfying element), `satisfied` (no verification) or `verified` (PRD-TRACE-014).
- The report `orphans` has one row for each item with no link: a need with no requirement, a requirement with no need, an application or infrastructure element that satisfies no requirement, a trace comment ID that is not in the model (PRD-TRACE-012) and a test file that no verification names.
- The command reads the trace comments and the test files in the output folders and in the test folders of the configuration file (`trace.tests`). A test file has a name such as `test_*.py`, `*_test.py`, `*.test.ts` or `*.spec.ts`.
- Each report gives the model commit, the commit `HEAD` of the local Git repository. If the folder is not in a Git repository, the report says so in place of the commit. A report gives no date or time (PRD-TRACE-018).
- The JSON format gives the report name, the columns, the rows, the model commit and the baseline commit. The CSV format starts with three comment lines that start with `#`, then one header line. A list cell has its items with `; ` between them.
- A trace comment that the command cannot read gives a warning on standard error. The exit code is 0 also if a requirement is `missing`.
- The report `impact` has one row for each element that changed after the baseline: the affected needs, requirements, verifications, generated files and HCL addresses. An element is changed if the hash of its IR form, with no source locations, is different from the hash in the baseline (PRD-TRACE-015). A new or removed element is also changed.
- The report `suspect` has one row for each trace link with an end that changed after the baseline. The row gives the changed ends and the changed elements.
- A change of an element also changes its owners and the elements that use it. For example, a changed field changes its entity, and the application that exposes the entity.
- The reports `impact` and `suspect` compare the model in the work tree with a Git baseline (PRD-TRACE-016). `--baseline <git-ref>` gives the baseline. If it does not, the key `trace.baseline` of the configuration file gives it. If neither gives it, the baseline is the newest release tag `v*` before `HEAD` (Q54). If there is no baseline, the command stops with exit code 2. These reports also give the baseline commit.
- The reports `coverage` and `orphans` use no baseline. With `--baseline`, they stop the command with exit code 2.
- The HTML format is the default. It gives one HTML file with its styles in the file, and no script and no external resource (PRD-TRACE-017). The file shows the model commit, the baseline commit and the table of the report.

The golden reports of the example model and of the order portal model are in `tests/golden/trace/`. After a change of the reports, run `uv run python scripts/write_golden_reports.py` and examine the differences before you commit them.

## Use with Claude Code

1. Unzip the bundle into the root of the toolchain repository. `CLAUDE.md` goes to the root, and the documents go to `docs/`.
2. If the repository already has a `CLAUDE.md`, merge the two files. Keep the result short, because Claude Code loads `CLAUDE.md` into each session.
3. Start Claude Code in the repository. A good first prompt is: "Read CLAUDE.md and docs/prd/00-top-level-prd.md, then do the first task in CLAUDE.md."

## Live documents

The bundle is a copy. The live documents are on claude.ai:

- [Top-level PRD](https://claude.ai/code/artifact/1ca8c61d-af04-469c-b04c-755aa8d7c128)
- [DSML PRD](https://claude.ai/code/artifact/2f3caccc-85d1-45cc-a570-d4493d16b9fd)
- [Toolchain core PRD](https://claude.ai/code/artifact/4f8c2692-e430-46b5-ad01-4483ca117079)
- [Application generation PRD](https://claude.ai/code/artifact/38be587f-3959-4d4d-a39f-a1923313e1ec)
- [Infrastructure generation PRD](https://claude.ai/code/artifact/8c075844-7325-402b-badd-87cbbdd90faa)
- [CI/CD generation PRD](https://claude.ai/code/artifact/40a79a1f-2760-4796-8de9-85822cab2353)
- [Validation PRD](https://claude.ai/code/artifact/6095f07a-e81c-48ac-9d33-ed548690a4e6)
- [Traceability PRD](https://claude.ai/code/artifact/9d874245-dfbb-4712-8370-c56252131dd8)
- [Decision record 01](https://claude.ai/code/artifact/7699d83f-b0de-4dc9-a037-644454a8988d), [02](https://claude.ai/code/artifact/d36abca8-3e59-487c-9f81-bb2dcad0d633), [03](https://claude.ai/code/artifact/85af4b8d-0ba4-442b-94e9-a5d80200d255)

If you change a live document, export the bundle again.

## Model status

The example model and the PRD model parse and resolve with OpenSysML 0.9.2 and the DSML library with no error (PRD-TOP-011, PRD-DSML-004). The tests `tests/test_example_model.py` and `tests/test_prd_model.py` make sure of this. `docs/model/syntax-changes.md` gives each change to the sketch syntax of the PRDs.
