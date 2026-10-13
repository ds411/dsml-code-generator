<!-- The script scripts/write_guide_reference.py writes this page from the installed toolchain. Do not change it. -->

[Reference](README.md) | [User guide](../README.md)

# DSML commands

This page gives the subcommands of the command `dsml`, sorted by name.
Write the subcommand after `dsml`, then its arguments and options, for example `dsml validate --format json`.

## Common options

Each subcommand accepts these options, except `dsml mcp` and `dsml skills`.

| Argument | Value | Description |
| --- | --- | --- |
| `--config` | `<file>` | read the configuration from this file (default: dsml.toml) |
| `--output` | `<file>` | write the report to this file, not to standard output |
| `--verbose` | No value | write debug messages to standard error |

## `dsml check-output`

Run the language tools on the generated code.

| Argument | Value | Description |
| --- | --- | --- |
| `--application` | `<name>` | check only the code of this application |
| `--infrastructure` | No value | check only the infrastructure code |

## `dsml generate`

Validate the model, then write all generated files.

| Argument | Value | Description |
| --- | --- | --- |
| `--application` | `<name>` | generate only the files of this application |
| `--check` | No value | write no file and list each file that a normal run changes |
| `--date` | `<YYYY-MM-DD>` | the date of the expiry check of the waivers (default: the commit date of HEAD) |
| `--infrastructure` | No value | generate only the infrastructure files |
| `--overwrite` | No value | replace the generated files that are different from the manifest |
| `--pipelines` | No value | generate only the pipeline files |

## `dsml init`

Write a starter configuration file and a starter model.

| Argument | Value | Description |
| --- | --- | --- |
| `--target` | `fastapi`, `react`, `nextjs` | the target of the starter files (default: fastapi) |

## `dsml ir`

Write the IR as JSON.

| Argument | Value | Description |
| --- | --- | --- |
| `<model-file>` | (zero or more) | a SysML v2 file of the model, in the current folder or below it |

## `dsml mcp`

Start the local MCP server with the stdio transport.

| Argument | Value | Description |
| --- | --- | --- |
| `--project` | `<folder>` | the project folder of the server (default: the current folder) |
| `--verbose` | No value | write debug messages to standard error |

## `dsml skills`

Install the skills for AI agents.

### `dsml skills install`

Write the skills for AI agents into the project.

| Argument | Value | Description |
| --- | --- | --- |
| `--output` | `<folder>` | write the skills into this folder (default: .claude/skills) |
| `--verbose` | No value | write debug messages to standard error |

## `dsml trace`

Write a trace report.

| Argument | Value | Description |
| --- | --- | --- |
| `report` | `coverage`, `orphans`, `impact`, `suspect` | the report to write |
| `--baseline` | `<git-ref>` | the baseline for the impact and suspect reports |
| `--format` | `html`, `csv`, `json` | the format of the report (default: html) |

## `dsml validate`

Validate the model and write the findings.

| Argument | Value | Description |
| --- | --- | --- |
| `--baseline` | `<git-ref>` | the baseline model for the identity rules |
| `--date` | `<YYYY-MM-DD>` | the date of the expiry check of the waivers (default: the commit date of HEAD) |
| `--fail-on` | `error`, `warning` | stop with exit code 1 if a finding has this severity or a higher one (default: error) |
| `--format` | `text`, `json`, `sarif` | the format of the findings (default: text) |

## `dsml version`

Write the versions of the toolchain, the DSML library, OpenSysML and the IR schema.

The subcommand has no other options.
