# Command `dsml check-output`

Story #134 added the subcommand `dsml check-output` (PRD-CORE-011). It runs the language tools on the generated code of the selected targets. The module is `src/dsml/check_output.py`.

## Selection

| Option | Targets |
| --- | --- |
| `--application <name>` | The application `<name>` of the model. Its output folder comes from the key `applications.<name>.output`. |
| `--infrastructure` | The folder of the key `infrastructure.output`. |
| No option | Each application of the model, and the infrastructure folder if the configuration file has the key `infrastructure.output`. |

Only an application check reads the model. The model gives the target of each application. `dsml check-output --infrastructure` reads only the configuration file and the generated files.

## Tools

The tools come from `PATH`. They must have the versions of `src/dsml/versions.toml`.

| Target | Tools | Folder | Requirements |
| --- | --- | --- | --- |
| FastAPI application | `ruff check --no-cache`, `ruff format --check --no-cache`, `pyright` | The output folder of the application | PRD-CORE-011, PRD-APP-016 |
| Infrastructure | `tofu fmt -check -recursive -diff` | The output folder of the infrastructure | PRD-IAC-038 |
| Infrastructure | `tflint --init` with the AWS rule set | A temporary copy of the output folder | PRD-IAC-038 |
| Each root module | `tofu init -backend=false`, `tofu validate`, `tflint --call-module-type=local` | The root module in the temporary copy | PRD-IAC-038 |

Notes:

- pyright reads the virtual environment `.venv` of the generated project (`[tool.pyright]` in `pyproject.toml`). Run `uv sync` in the folder of the application before the check.
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
| A usage error, a missing key in the configuration file, a missing output folder, or an infrastructure folder with no root module | 2 |

`tofu validate` runs only if `tofu init` passed on the same root module. `tflint` on a root module runs only if `tflint --init` passed.

## Targets of later phases

`tsc` and Steiger check the React and Next.js targets of phases 2 and 3 (PRD-CORE-011, PRD-APP-234, PRD-APP-306). They go in `src/dsml/check_output.py`, with one function for each target, like `fastapi_steps`. Until then, an application with a target other than `fastapi` gives an error line, and the exit code is 1.

## CI

The job "Infrastructure golden HCL" of `.github/workflows/ci.yml` runs `dsml check-output --infrastructure` on the golden output of the order service. The step copies the output and writes a configuration file in a temporary folder, because a path in the configuration file cannot contain "..".

The generated workflow `pr.gen.yml` runs `dsml check-output` through the toolchain action (PRD-CICD-005). The job installs the tools first (story #140, `docs/notes/pipeline-generator.md`).
