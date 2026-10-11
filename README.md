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
├── decisions/                             Decision records 01 to 06
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

3. Run the command `dsml`:

   ```sh
   uv run dsml version
   ```

4. Run the checks. Each check must pass before you open a pull request:

   ```sh
   uv run ruff check
   uv run ruff format --check
   pnpm typecheck
   uv run pytest
   ```

5. Build the package. The wheel and the source archive go to `dist/`:

   ```sh
   uv build
   ```

In a Claude Code cloud session, the SessionStart hook `.claude/hooks/session-start.sh` does steps 1 and 2 at the start of the session.

### CI

The workflow `.github/workflows/ci.yml` runs the checks of step 4 on each pull request and on each push to `main`. It runs on Linux x64 (`ubuntu-24.04`), Linux arm64 (`ubuntu-24.04-arm`) and macOS arm64 (`macos-15`), the operating systems of decision record 03 (Q50). The steps are:

1. `uv sync --frozen`
2. `pnpm install --frozen-lockfile`
3. `uv run ruff check`
4. `uv run ruff format --check`
5. `pnpm typecheck`
6. `uv run pytest`

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
| `validate`, `trace`, `check-output` | Not available yet. The subcommand stops with exit code 2. |
| `generate` | Writes the generated files through the file writer and keeps the manifest `.dsml/generated.json`. There are no generators yet (M5, M6, M7). `docs/notes/file-writer.md` gives the rules. |
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

`dsml init [--target fastapi]` writes two starter files in the current folder:

- `dsml.toml`: a configuration file that reads the model in the folder `model`.
- `model/model.sysml`: a model with one stakeholder, one need, one requirement and the `@DsmlVersion` metadata. It parses and resolves with the DSML library.

The files are create-once files (PRD-CORE-044). The command writes a file only if no file exists at its path. For a file that exists, the report gives the line `keep <path>: The file exists. The command did not change it.` The command writes no manifest. `dsml generate` writes the manifest.

- Phase 1 accepts only the target `fastapi`. This is also the default target.
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

The golden IR files of the two reference models are in `tests/golden/ir/`. CI compares the IR with these files on each platform (PRD-CORE-027, PRD-CORE-029). After a change of the IR, run `uv run python scripts/write_golden_ir.py` and examine the differences before you commit them.

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
