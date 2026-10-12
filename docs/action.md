# GitHub Action of the DSML toolchain

The repository supplies a GitHub Action in `action.yml` (PRD-CORE-050). The action does these steps:

1. It sets up uv and Python 3.14.
2. It installs the wheel of the toolchain version that the input `version` gives. The wheel comes from the assets of the GitHub release `v<version>` (Q63). There is no package index.
3. It gets the `sysml-grpc` binary of the pinned OpenSysML version and checks its SHA-256 hash (PRD-CORE-049). After this step, `dsml` does not use the network.
4. It runs `dsml <command> <args>` in the folder `working-directory`. Standard input is `/dev/null` (PRD-CORE-009).
5. When the input `sarif` is `true`, it uploads the SARIF findings to GitHub code scanning (PRD-CORE-051).
6. It gives the exit code of `dsml` to the job. Exit code 1 (an error finding) or 2 (a usage or toolchain error) makes the step fail.

The action installs the toolchain into its own virtual environment in the temporary folder of the runner. Thus it does not change the Python of the other steps of the job. The action runs on Linux and macOS runners.

## Inputs

| Input | Mandatory | Default | Description |
| --- | --- | --- | --- |
| `version` | Yes | None | The toolchain version to install, for example `0.1.0`. |
| `command` | No | `validate` | The `dsml` subcommand to run, for example `validate` or `generate`. |
| `args` | No | Empty | More arguments for the subcommand, for example `--fail-on warning`. A space separates two arguments. Quotes have no effect. |
| `config` | No | Empty | The configuration file, relative to `working-directory`. When the input is empty, `dsml` uses `dsml.toml`. |
| `sarif` | No | `false` | When `true`, the action runs `dsml validate --format sarif` and uploads the findings to code scanning. The command must be `validate`. |
| `sarif-category` | No | `dsml` | The category of the SARIF upload in code scanning. Give a different category to each upload in one workflow. |
| `working-directory` | No | `.` | The folder in which `dsml` runs, relative to the workspace. |
| `wheel` | No | Empty | A wheel file or a wheel URL to install in place of the wheel of the GitHub release. The tests of the action use it. The version of the wheel must be the same as `version`. |

## Outputs

| Output | Description |
| --- | --- |
| `exit-code` | The exit code of `dsml`: 0 for a success, 1 for an error finding, 2 for a usage or toolchain error. |
| `sarif-file` | The path of the SARIF file, when `sarif` is `true`. |

## SARIF upload

The SARIF upload uses `github/codeql-action/upload-sarif` at the full commit SHA of `src/dsml/versions.toml` (PRD-CICD-014). The job must have the permission `security-events: write`.

In the SARIF file of `dsml validate`, each URI is relative to the folder of the configuration file. Code scanning needs URIs relative to the root of the repository. Thus the action adds the path of that folder to each URI before the upload.

The action uploads the findings also when the model has an error finding. Then the step fails with exit code 1.

## Example

This job validates the model with the configuration file `model/dsml.toml` and uploads the findings to code scanning:

```yaml
jobs:
  validate:
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: ds411/dsml-code-generator@<commit-sha> # v0.1.0
        with:
          version: 0.1.0
          command: validate
          config: model/dsml.toml
          sarif: "true"
```

Pin the action to the full commit SHA of the release tag, and give the release tag in a comment. Give the same version in the input `version`.

To generate the code and stop if a generated file is not current, use `command: generate` and `args: --check`.

## Test

The workflow `.github/workflows/action-test.yml` uses the action from the local path (`uses: ./`). Until a release exists, the job builds the wheel of the toolchain and gives it in the input `wheel`. The workflow does these checks:

- `dsml validate` passes on the example model, and the action uploads its findings to code scanning.
- On the model `tests/models/action/error.sysml`, which has an error finding, the action step fails with exit code 1.
- A wheel with a different version stops the action.
- actionlint finds no error in the workflow.
