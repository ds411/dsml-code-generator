# Time of the toolchain for a model with 1,000 elements

Story #33 measured the time of `dsml ir` for a generated model with 1,000 elements. Story #139 added `dsml validate` and `dsml generate` (PRD-TOP-012). This document gives the results.

- Script: `scripts/measure_ir.py`. The CI step "Measure the IR time for 1,000 elements" runs it on Linux x64 (Q62).
- The script writes a model with 140 units, 5 stakeholders, one FastAPI application and the infrastructure of one container service. Each unit has a need, a requirement, an entity with two fields, an exposed part of the application and a verification. The infrastructure has a network, a container service, a database, a user directory, their AWS parts, a tooling account and three environments.
- The IR has exactly 1,000 elements and 567 links. The model has 4,378 lines. `dsml validate` gives no finding. `dsml generate` writes 1,638 files: the FastAPI code, the HCL and the workflows.
- The time is for the full command: the start of Python, the start of `sysml-grpc`, the parse, the conversion, the validation and the writers. The value is the median of 5 runs, after one run that starts the cache.
- Before each run of `dsml generate`, the script deletes the output of the earlier run. Thus each run writes all files.
- If `dsml validate` or `dsml generate` takes 10 seconds or more, the script stops with exit code 1. This check applies to models with 1,000 elements or fewer.

## Limit

Decision Q50 gives the limit: `dsml validate` and `dsml generate` on a model with 1,000 elements must finish in less than 10 seconds, on a GitHub-hosted Linux runner with 4 vCPUs. These commands make the IR first. Thus the time of `dsml ir` is a part of this limit.

## Results

| Platform | Runner | `dsml ir` | `dsml validate` | `dsml generate` |
| --- | --- | --- | --- | --- |
| Linux x64 | `ubuntu-24.04` | 3,725 ms | 3,686 ms | 4,787 ms |
| Linux x64 (cloud container, 4 vCPUs) | not a GitHub runner | 7,002 ms | 6,704 ms | 9,097 ms |

The values for the `ubuntu-24.04` runner come from the CI run of pull request #149. This runner is the reference runner of Q50. On this runner, `dsml validate` uses 3.7 s and `dsml generate` uses 4.8 s of the 10 s. Both commands are in the limit.

Story #33 measured `dsml ir` on a model with no application and no infrastructure. These older values are for that model:

| Platform | Runner | `dsml ir`, 1,000 elements |
| --- | --- | --- |
| Linux x64 | `ubuntu-24.04` | 3,597 ms |
| Linux arm64 | `ubuntu-24.04-arm` | 3,826 ms |
| macOS arm64 | `macos-15` | 2,266 ms |

Q62 removed the arm64 and macOS runners from CI. Thus there are no new values for these platforms.

## Parts of the time

A measurement in the cloud container gave these parts:

| Part | Time |
| --- | --- |
| Start of `sysml-grpc` | 0.1 s |
| Parse of the library and the model | 0.3 s |
| `Model.to_api_json()` of OpenSysML | 3.5 s |
| Other conversion and the evaluation of values | 1.0 s |
| Stop of `sysml-grpc` | less than 0.1 s |

The API JSON form of OpenSysML uses approximately 60 % of the time. The adapter needs this form, because only this form gives the source locations, the metadata usages and the values of the features (`docs/notes/ir-solution-layers.md`).

## Model with 10,000 elements

Decision Q50 also tells that the toolchain must accept models with up to 10,000 elements. It gives no time limit for these models. The script does not apply the limit to them. In the cloud container, story #139 ran each command one time on a generated model with 10,000 elements:

| Command | Time | Result |
| --- | --- | --- |
| `dsml ir` | 79.9 s | 10,000 elements, no finding |
| `dsml validate` | 77.2 s | 0 errors, 0 warnings, 2 info |
| `dsml generate` | 93.8 s | 15,784 files |

The toolchain accepts the model. Use `uv run python scripts/measure_ir.py --elements 10000` to measure it again. This command does 6 runs of each command, thus it takes approximately 25 minutes in the cloud container.

## Risk

On the reference runner, the IR uses approximately 37 % of the 10 seconds, and `dsml generate` uses approximately 48 %. In the cloud container, `dsml generate` uses approximately 91 %. The IR is the largest part of the time of each command. The adapter calls `Model.to_api_json()` only one time for each model. If validation and generation use more time, ask the OpenSysML project for a faster API JSON form, or for a form with only the elements of the model files.
