<!-- The module dsml.assist.reference writes this file from the installed toolchain. Do not change it. -->

# DSML configuration file

This part gives the keys of the configuration file `dsml.toml`, schema version 1.
`dsml init` writes a starter `dsml.toml`. Each command reads `dsml.toml` in the current folder. The option `--config` selects a different file.
A key in the table `[model]` has the dotted name `model.<key>`. A word in angle brackets, for example `<name>`, is a name that you select.

## Keys

All keys are optional, except `schema`. A key that is not in this table is an error.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `schema` | integer | None. The key is mandatory. | The schema version of the file. This toolchain reads schema version 1. |
| `model.paths` | list of paths | No path | The files and the folders of the model. The toolchain reads each `.sysml` file in a folder and in its subfolders. |
| `applications.<name>.output` | path | No folder | The output folder of the application `<name>`. `<name>` is the name of the application in the model. It starts with a letter, then has letters, digits, "_" or "-". `dsml generate` stops with an error if an application of the run has no output folder. |
| `applications.<name>.dependencies` | list of texts | No dependency | The extra dependencies of the application. The generator adds them to the dependency list of the target. |
| `infrastructure.output` | path | No folder | The output folder of the infrastructure code. Without this key, `dsml generate` writes no infrastructure file. |
| `pipelines.output` | path | No folder | The output folder of the pipelines. |
| `ids.need` | regular expression | `N-[0-9]{3,}` | The pattern of the ID of a need. The full ID must match the pattern. |
| `ids.requirement` | regular expression | `R-[0-9]{3,}` | The pattern of the ID of a requirement. The full ID must match the pattern. |
| `ids.verification` | regular expression | `V-[0-9]{3,}` | The pattern of the ID of a verification. The full ID must match the pattern. |
| `rules.optional` | list of texts | No rule set | The optional rule sets to turn on. The optional rule sets are: `TXT`. |
| `rules.severity.<rule>` | text | The default severity of the rule | The severity of the rule `<rule>`, for example `COV-003`: `error`, `warning`, `info`, `off`. You cannot decrease the severity of a rule with the default severity `error`. |
| `trace.baseline` | text | The newest release tag `v*` before `HEAD` | The default trace baseline, a Git reference, for example the tag `trace-baseline`. If you set it, `dsml validate` runs the IDN rules with this baseline. If you do not set it, the IDN rules do not run. |
| `trace.tests` | list of paths | No folder | The folders of the hand-written tests. The toolchain reads the trace comments in these folders. |
| `aws.regions` | list of texts | No Region | The permitted AWS Regions. If the key is missing or the list is empty, the rule AWS-002 gives no finding. |
| `iac.opentofu.state_encryption` | boolean | `false` | Turn on OpenTofu state encryption. Only OpenTofu accepts the output with this option. |

## Example

This file gives each key of the schema.

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

## Rules for the values

- Each path is relative to the folder of the configuration file. Use "/" as the separator. Do not use an absolute path or "..".
- Each list is sorted when the toolchain reads it. A duplicate item has no effect.
- Do not put a secret value in the file. The schema has no key for a secret value, so a secret value gives an error.
- If the file is not correct, each command stops with exit code 2. It gives one line for each error, with the file, the line and the key.
- For each application of the model that `dsml generate` writes, add a table `[applications.<name>]` with the key `output`.
