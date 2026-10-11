# Time to make the IR of a model with 1,000 elements

Story #33 measured the time of `dsml ir` for a generated model with 1,000 elements. This document gives the results.

- Script: `scripts/measure_ir.py`. The CI step "Measure the IR time for 1,000 elements" runs it on each platform.
- The script writes a model with 166 units and 3 stakeholders. Each unit has a need, a requirement, an entity with two fields and a verification. The IR has exactly 1,000 elements and 498 links. The model has 4,325 lines.
- The time is for the full command: the start of Python, the start of `sysml-grpc`, the parse, the conversion and the JSON writer. The value is the median of 5 runs, after one run that starts the cache.

## Limit

Decision Q50 gives the limit: `dsml validate` and `dsml generate` on a model with 1,000 elements must finish in less than 10 seconds, on a GitHub-hosted Linux runner with 4 vCPUs. These commands make the IR first. Thus the time of `dsml ir` is a part of this limit.

## Results

| Platform | Runner | `dsml ir`, 1,000 elements |
| --- | --- | --- |
| Linux x64 (cloud container, 4 vCPUs) | not a GitHub runner | 5,703 ms |
| Linux x64 | `ubuntu-24.04` | 3,597 ms |
| Linux arm64 | `ubuntu-24.04-arm` | 3,826 ms |
| macOS arm64 | `macos-15` | 2,266 ms |

The values for the GitHub runners come from the CI run of pull request #49. The `ubuntu-24.04` runner is the reference runner of Q50. On this runner, `dsml ir` uses 3.6 s of the 10 s.

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

Decision Q50 also tells that the toolchain must accept models with up to 10,000 elements. It gives no time limit for these models. In the cloud container, `dsml ir` made the IR of a generated model with 10,000 elements in 66.8 s, with no error. Use `uv run python scripts/measure_ir.py --elements 10000` to measure it again.

## Risk

On the reference runner, the IR uses approximately 36 % of the 10 seconds. In the cloud container, it uses approximately 57 %. Validation and generation must use less than the remaining time. The adapter calls `Model.to_api_json()` only one time for each model. If validation and generation use more time, ask the OpenSysML project for a faster API JSON form, or for a form with only the elements of the model files.
