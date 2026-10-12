# User guide

This guide is for users of the DSML toolchain. You do not need to know SysML v2, Jinja, OpenTofu or the other target tools before you read it. The guide tells what the model is, what the toolchain does, and how to use it.

## Pages

Read the pages in this order:

1. [Concepts](concepts.md): the problem that the toolchain solves, the five layers of the model, the IR, validation, code generation and traceability.
2. [Glossary](glossary.md): a short meaning for each term and each product name of the guide.
3. [Modeling tutorial](modeling-tutorial.md): write a model step by step, then validate it and generate code from it.
4. [Generated code](generated-code.md): the files that the generators write, and where to add hand-written code.
5. [Reports](reports.md): the validation findings and the trace reports, and how to read them.
6. [Reference](reference/README.md): each DSML keyword, each validation rule and each `dsml` subcommand.
7. [AI assistance](ai-assistance.md): the skills and the MCP server that let an AI agent help you write a model.

## Other documents

- [Configuration file `dsml.toml`](../configuration.md): all keys of the configuration file.
- [GitHub Action](../action.md): run the toolchain in a GitHub Actions workflow.
- [Example model](../model/examples/order-service.sysml): an order service with all five layers.
- [PRD set](../prd/00-top-level-prd.md): the requirements of the toolchain. The guide does not replace them.

## Commands

The command `dsml` has these subcommands. The [reference](reference/README.md) gives all options.

| Command | What it does |
| --- | --- |
| `dsml init` | Writes a starter configuration file and a starter model. |
| `dsml validate` | Validates the model and writes the findings. |
| `dsml generate` | Validates the model, then writes all generated files. |
| `dsml generate --check` | Writes no file, and lists each file that a normal run changes. |
| `dsml trace coverage` | Writes the coverage report. The other reports are `orphans`, `impact` and `suspect`. |
| `dsml ir` | Writes the IR of the model as JSON. |
| `dsml check-output` | Runs the language tools of each target on the generated code. |
| `dsml version` | Writes the versions of the toolchain parts. |
