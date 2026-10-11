# Configuration file `dsml.toml`

One TOML file configures the toolchain for a repository (PRD-CORE-012). This document gives all keys of schema version 1. The module `src/dsml/config.py` reads the file.

## Location of the file

- The toolchain reads `dsml.toml` in the current folder. Run the command `dsml` in the repository root.
- The option `--config <file>` gives a different file. This file must exist.
- If there is no `--config` and no `dsml.toml`, the toolchain uses the default value of each key.
- Each path in the file is relative to the folder of the file. Use "/" as the separator. Do not use an absolute path or "..". These rules keep absolute paths out of the output (PRD-CORE-033).

## Errors

The toolchain stops with exit code 2 if the file is not correct (PRD-CORE-002, PRD-CORE-014). It writes one line for each error, with the file, the line and the key. For example:

```text
dsml: error: dsml.toml:4: The key "model.pths" is unknown.
dsml: error: dsml.toml:9: The key "iac.opentofu.state_encryption" must be true or false, not "yes".
```

The toolchain reports these errors:

- The file is not correct TOML.
- The key `schema` is missing, or its value is not a known schema version.
- A key is unknown. The schema has no key for a secret value, so a secret value in the file gives an error (PRD-CORE-016).
- A value has the wrong type, for example a text in place of a list.
- A value is not correct, for example a path with "..", a regular expression with an error, or an unknown severity.

If a key is in an inline table, the line of the error is the line of the inline table.

## Example

```toml
schema = 1

[model]
paths = ["model"]

[applications.orders]
output = "services/orders"
dependencies = ["httpx==0.28.1"]

[infrastructure]
output = "infra"

[pipelines]
output = ".github/workflows"

[ids]
need = "N-[0-9]{3,}"
requirement = "R-[0-9]{3,}"
verification = "V-[0-9]{3,}"

[rules]
optional = ["TXT"]

[rules.severity]
"COV-003" = "error"

[trace]
baseline = "trace-baseline"
tests = ["tests"]

[aws]
regions = ["eu-central-1", "eu-west-1"]

[iac.opentofu]
state_encryption = false
```

## Keys

All keys are optional, except `schema`. The milestone that uses a key tells what occurs if the key is missing. Each list is sorted when the toolchain reads it, and a duplicate item has no effect (PRD-CORE-032).

| Key | Type | Default | Description | Requirements |
| --- | --- | --- | --- | --- |
| `schema` | integer | None. The key is mandatory. | The schema version of the file. This toolchain reads schema version 1. | PRD-CORE-014 |
| `model.paths` | list of paths | No path | The files and the folders of the model. The toolchain reads each `.sysml` file in a folder and in its subfolders. | PRD-CORE-013, PRD-DSML-007 |
| `applications.<name>.output` | path | No folder | The output folder of the application `<name>`. `<name>` is the name of the application in the model. It starts with a letter, then has letters, digits, "_" or "-". | PRD-CORE-013, PRD-APP-002 |
| `applications.<name>.dependencies` | list of texts | No dependency | The extra dependencies of the application. The generator adds them to the dependency list of the target. | PRD-CORE-046, Q56 |
| `infrastructure.output` | path | No folder | The output folder of the infrastructure code. | PRD-CORE-013, PRD-IAC-001 |
| `pipelines.output` | path | No folder | The output folder of the pipelines. | PRD-CORE-013 |
| `ids.need` | regular expression | `N-[0-9]{3,}` | The pattern of the ID of a need. | PRD-DSML-050, PRD-DSML-051 |
| `ids.requirement` | regular expression | `R-[0-9]{3,}` | The pattern of the ID of a requirement. | PRD-DSML-050, PRD-DSML-051 |
| `ids.verification` | regular expression | `V-[0-9]{3,}` | The pattern of the ID of a verification. | PRD-DSML-050, PRD-DSML-051 |
| `rules.optional` | list of texts | No rule set | The optional rule sets to turn on. The only optional rule set is `TXT`. | PRD-CORE-013, PRD-VAL-013 |
| `rules.severity.<rule>` | text | The default severity of the rule | The severity of the rule `<rule>`, for example `COV-003`: `error`, `warning`, `info` or `off`. | PRD-VAL-004 |
| `trace.baseline` | text | The newest release tag `v*` before `HEAD` | The default trace baseline, a Git reference, for example the tag `trace-baseline`. | PRD-CORE-013, PRD-VAL-011, PRD-TRACE-016, Q54 |
| `trace.tests` | list of paths | No folder | The folders of the hand-written tests. The toolchain reads the trace comments in these folders. | PRD-TRACE-010 |
| `aws.regions` | list of texts | No Region | The permitted AWS Regions. | AWS-002 |
| `iac.opentofu.state_encryption` | boolean | `false` | Turn on OpenTofu state encryption. Only OpenTofu accepts the output with this option. | PRD-CORE-013, PRD-IAC-004, Q22 |

## Rules for the values

- An ID pattern is a Python regular expression. An ID agrees with the pattern if the full ID matches it.
- The schema gives the IaC options for OpenTofu only in the table `iac.opentofu`. The default HCL is correct for OpenTofu and for Terraform (PRD-IAC-003). A table for a different tool is an unknown key.
- The validator rules for the values, for example the rule that a severity `error` cannot decrease (PRD-VAL-004), are in the validator. The configuration reader checks only the form of each value.
