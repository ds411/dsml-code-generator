---
name: dsml-cli
description: Use the dsml CLI in a DSML project. Start a project, validate the model and correct the findings, generate the code, run the language tools on the generated code and write the trace reports. Use this skill when the user asks you to validate a DSML model, generate code from it or report its traceability.
---

# Use the `dsml` CLI

The `dsml` CLI validates a DSML model, generates code from it and writes trace reports. This skill tells you how to use the CLI in a project. The modeling skill `dsml-modeling` tells you how to write the model text.

The CLI does not use the network or an AI model. Each command gives the same output for the same model, configuration and toolchain version.

## Reference files

- `references/commands.md` gives each subcommand and its options.
- `references/rules.md` gives each validation rule, its message and its correction.

The toolchain writes these files from the installed version. They agree with the CLI that the project uses. Read them when you are not sure about an option or a rule.

## Rules for the agent

- Run the commands from the folder of the configuration file `dsml.toml`. The option `--config` selects a different file.
- Do not edit a generated file. The name of a generated file ends with `.gen.<ext>` or `_gen.py`. The file `.dsml/generated.json` lists all generated files.
- Do not use `dsml generate --overwrite` without the approval of the user. This option replaces the changed generated files, and the changes go away.
- Do not add a waiver without a reason from the user.
- A command does not ask for input. Read the exit code and the output of each command.

## Exit codes

| Exit code | Meaning | Your next step |
| --- | --- | --- |
| 0 | The command found no error. | Continue with the next step. |
| 1 | The command found an error finding or a `--check` difference. | Read the output and correct the cause. |
| 2 | A usage error or an internal error occurred. | Read the message on standard error. Correct the command line or the configuration. |

## Start a project

Do these steps in an empty folder:

1. Select the target with the user: `fastapi`, `react` or `nextjs`. The steps below use `fastapi`.
2. Write the starter configuration file and the starter model:

   ```shell
   dsml init --target fastapi
   ```

3. Read the output. The command does not change a file that exists. A line that starts with `keep` tells you about a file that exists.
4. Validate the starter model. The section "Validate the model" gives the steps.

The starter model is `model/model.sysml`. It has one stakeholder, one need and one requirement. Then change the model for the product of the user. The modeling skill tells you how.

## Validate the model

Use the JSON format. It gives each finding as data:

```shell
dsml validate --format json
```

Each item in `findings` has these fields:

| Field | Content |
| --- | --- |
| `rule` | The rule ID, for example `COV-003`. |
| `severity` | `error`, `warning` or `info`. |
| `message` | The problem. |
| `fixHint` | The correction. |
| `element` | The element of the model. |
| `location` | The `file`, the `line` and the `column` of the element. |

The item `summary` gives the number of findings for each severity. The item `waived` gives the findings that a waiver stops.

## Correct the findings

Do these steps until `dsml validate` finds no error:

1. Run `dsml validate --format json`.
2. If the exit code is 0 and `summary.error` is 0, go to step 7.
3. Select the findings with the severity `error`.
4. For each finding, read `message` and `fixHint`. Find the rule in `references/rules.md`.
5. Correct the model text at `location`. Do not change a different element to stop a finding.
6. Go to step 1.
7. Tell the user about the warnings. Correct a warning if the correction is clear. Ask the user if it is not clear.

If a finding stays after three corrections, stop. Tell the user the rule, the message and the corrections that you tried.

A waiver stops one finding of one rule on one element. Use a waiver only when the user gives a reason. Put the waiver on the element of the finding:

```sysml
@Waiver { rule = "COV-003"; reason = "The reason from the user."; owner = "The name of the owner."; }
```

The attribute `expires` is optional. It gives the date when the waiver stops. Give an owner that the user names.

To make a warning into a stop condition, use `--fail-on`:

```shell
dsml validate --format json --fail-on warning
```

## Generate the code

Do these steps:

1. Validate the model with no error. `dsml generate` validates the model first, and it writes no file if it finds an error.
2. Examine the changes before you write files:

   ```shell
   dsml generate --check
   ```

   The command writes no file. It lists each file that a normal run adds, changes or deletes. Exit code 1 tells you that there are changes.
3. Tell the user about each deleted file.
4. Write the files:

   ```shell
   dsml generate
   ```

5. If the command stops because a generated file changed, do not use `--overwrite`. Tell the user the changed files. Move the change into a hand-written file or into the model. Use `--overwrite` only when the user approves it.

To generate only one part, use one of these options:

```shell
dsml generate --application OrderService
dsml generate --infrastructure
dsml generate --pipelines
```

Replace `OrderService` with the name of an application in the model.

## Write the business logic

Put business logic only in hand-written files. The generator does not change a hand-written file.

- The generator writes a create-once file one time. Then the developer owns it. For example, the FastAPI generator writes `handler.py` for each custom operation. Its function `handle` raises `NotImplementedError` until you write the logic.
- A file with `.gen.` or `_gen.py` in its name is a generated file. The next run of `dsml generate` writes it again, and your change goes away.
- To change a generated file, change the model, then run `dsml generate` again.

## Check the generated code

Run the language tools on the generated code and on the hand-written code:

```shell
dsml check-output
```

The report gives one line for each tool and target. Exit code 1 tells you that a tool found an error or that a tool is missing. Do these steps:

1. If a tool is missing, tell the user the name of the tool. Do not install a tool without the approval of the user.
2. If a tool found an error in a hand-written file, correct the hand-written file.
3. If a tool found an error in a generated file, do not edit it. Tell the user. The cause can be in the model or in the toolchain.
4. Run `dsml check-output` again.

To check one part, use `--application` or `--infrastructure`:

```shell
dsml check-output --application OrderService
dsml check-output --infrastructure
```

## Write the trace reports

The trace reports show the links from the stakeholder needs to the code, the tests and the AWS resources. Use the JSON format to read a report:

```shell
dsml trace coverage --format json
dsml trace orphans --format json
dsml trace impact --format json --baseline main
dsml trace suspect --format json --baseline main
```

| Report | Question |
| --- | --- |
| `coverage` | Is each requirement covered? Each row gives the status `missing`, `satisfied` or `verified`. |
| `orphans` | Which elements, trace comments and test files have no link? |
| `impact` | What does a change after the baseline affect? |
| `suspect` | Which links have an end that changed after the baseline? A person must examine each of these links. |

The `impact` and `suspect` reports compare the model with a Git baseline. Replace `main` with the baseline that the user gives. With no `--baseline`, the command uses the default baseline.

Tell the user the result of each report:

- The number of requirements with each status, and each requirement with the status `missing`.
- Each orphan.
- Each suspect link.

For a report that a person reads, use the HTML format and an output file:

```shell
dsml trace coverage --format html --output coverage.html
```

## Other commands

```shell
dsml version
dsml ir
```

`dsml version` gives the versions of the toolchain, the DSML library, OpenSysML and the IR schema. `dsml ir` writes the IR of the model as JSON.
