# Command `dsml check-output`

Story #134 added the subcommand `dsml check-output` (PRD-CORE-011). Story #170 added the tools of the React target. It runs the language tools on the generated code of the selected targets. The module is `src/dsml/check_output.py`.

## Selection

| Option | Targets |
| --- | --- |
| `--application <name>` | The application `<name>` of the model. Its output folder comes from the key `applications.<name>.output`. |
| `--infrastructure` | The folder of the key `infrastructure.output`. |
| No option | Each application of the model, and the infrastructure folder if the configuration file has the key `infrastructure.output`. |

Only an application check reads the model. The model gives the target of each application. `dsml check-output --infrastructure` reads only the configuration file and the generated files.

## Tools

The tools come from `PATH`. The tools of a React application come first from the folder `node_modules/.bin` of the project, then from `PATH`. The tools must have the versions of `src/dsml/versions.toml` or of the generated `package.json`.

| Target | Tools | Folder | Requirements |
| --- | --- | --- | --- |
| FastAPI application | `ruff check --no-cache`, `ruff format --check --no-cache`, `pyright` | The output folder of the application | PRD-CORE-011, PRD-APP-016 |
| React application | `tsc --noEmit`, `eslint .`, `steiger ./src` | The output folder of the application | PRD-CORE-011, PRD-APP-016, PRD-APP-234 |
| Infrastructure | `tofu fmt -check -recursive -diff` | The output folder of the infrastructure | PRD-IAC-038 |
| Infrastructure | `tflint --init` with the AWS rule set | A temporary copy of the output folder | PRD-IAC-038 |
| Each root module | `tofu init -backend=false`, `tofu validate`, `tflint --call-module-type=local` | The root module in the temporary copy | PRD-IAC-038 |

Notes:

- pyright reads the virtual environment `.venv` of the generated project (`[tool.pyright]` in `pyproject.toml`). Run `uv sync` in the folder of the application before the check.
- `tsc`, ESLint and Steiger of a React application come from the dependencies of the generated `package.json`. Run `pnpm install` in the folder of the application before the check. The command puts the folder `node_modules/.bin` of the application first on `PATH` for these tools. If a tool is missing, the message tells you to run `pnpm install`.
- Steiger reads the generated `steiger.config.ts`. ESLint reads the generated `eslint.config.js`.
- A root module is a folder with the file `versions.gen.tf`. The command does not look in a folder with a name that starts with ".", for example `.terraform`.
- `tofu init` writes the folder `.terraform` and the lock file. Thus `tofu init`, `tofu validate` and `tflint` run on a temporary copy of the output folder. The command deletes the copy at the end. The generated folder does not change.
- The command writes the tflint configuration in the temporary folder. It turns on the plugin `aws` with the version `tflint-ruleset-aws` of `src/dsml/versions.toml`. `tflint --init` installs the plugin only if it is not in the plugin folder of tflint.
- `tofu init` gets the AWS provider from the registry, and `tflint --init` can get the AWS rule set from GitHub. This is the network use of the checked tools, not of the toolchain (PRD-TOP-004). To use a provider cache, set `TF_PLUGIN_CACHE_DIR`.
- The command adds the environment variables `NO_COLOR=1`, `TF_IN_AUTOMATION=1` and `TF_INPUT=0`. The tools get no input from a terminal (PRD-CORE-009).

## Report and exit code

The report has one line for each tool and target, sorted by target and tool (PRD-CORE-006). The line starts with the status: `pass`, `error` or `not run`. The output of each tool that did not pass follows its line, with an indent of four spaces. The last line is a summary.

```text
pass infra: tflint --init
pass infra: tofu fmt
error infra/envs/dev: tofu init
    Error: Failed to resolve provider packages
not run infra/envs/dev: tofu validate
    The step did not run, because "tofu init" on "infra/envs/dev" did not pass.
The check found errors. 2 steps of 4 did not pass.
```

| Result | Exit code |
| --- | --- |
| Each tool passed. | 0 |
| A tool found an error, or a tool is missing. A missing tool gives the message `The tool "<tool>" is missing.` | 1 |
| An application with a target that has no tools in this version, for example `nextjs` | 1 |
| A usage error, a missing key in the configuration file, a missing output folder, or an infrastructure folder with no root module | 2 |

`tofu validate` runs only if `tofu init` passed on the same root module. `tflint` on a root module runs only if `tflint --init` passed.

## Targets of later phases

M11 (#156) adds the tools of the Next.js target of phase 3 (PRD-CORE-011, PRD-APP-306). They go in `src/dsml/check_output.py`, with one function for the target, like `react_steps`. Until then, an application with the target `nextjs` gives an error line, and the exit code is 1.

## CI

The job "Infrastructure golden HCL" of `.github/workflows/ci.yml` runs `dsml check-output --infrastructure` on the golden output of the order service. The step copies the output and writes a configuration file in a temporary folder, because a path in the configuration file cannot contain "..".

The job "React golden project" runs `dsml check-output` on the full output of the order portal (stories #170 and #177). The job writes the output with `dsml generate` in a temporary folder, with the order portal model and its configuration file. It runs `pnpm install` in `apps/order-portal` and `uv sync` in `services/order-api` first. The command checks the FastAPI application `orderApi` and the React application `orderPortal`. The job also runs `dsml check-output --application petPortal` on the golden output of the external API model (story #175).

The generated workflow `pr.gen.yml` runs `dsml check-output` through the toolchain action (PRD-CICD-005). The job installs the tools first (story #140, `docs/notes/pipeline-generator.md`).
