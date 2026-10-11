# Pipeline generator

Story #83 added the pipeline generator and the pull request workflow `pr.gen.yml`. The workflows `main.gen.yml` and `promote.gen.yml` come in the next pipeline story.

## Output

The generator writes in the folder of the key `pipelines.output`, normally `.github/workflows`. Without this key, it writes no file. The workflows run their commands in the folder of the configuration file. Thus the configuration file must be in the root of the repository.

The template is `src/dsml/templates/pipelines/pr.gen.yml.j2`. The code is in `src/dsml/generate/pipelines/`.

## Jobs of `pr.gen.yml`

The trigger is `pull_request`. The workflow sets `permissions: {}`. Each job then declares the smallest set that it needs (PRD-CICD-011).

| Job | Steps | Permissions | Requirements |
| --- | --- | --- | --- |
| `validate` | `dsml validate --format sarif`, then the upload of `dsml.sarif` to code scanning | `actions: read`, `contents: read`, `security-events: write` | PRD-CICD-002 |
| `generate-check` | `dsml generate --check` | `contents: read` | PRD-CICD-003 |
| `check-output` | `dsml check-output` | `contents: read` | PRD-CICD-005 |
| `test-<application>` | For each FastAPI application: `uv lock --check`, `uv sync --frozen`, ruff, the format check, pyright and pytest | `contents: read` | PRD-CICD-004 |
| `plan-dev` | `tofu init`, `tofu plan` with the plan role, and the plan text in the job summary | `contents: read`, `id-token: write` | PRD-CICD-006, PRD-CICD-010 |

Notes:

- `uv sync --frozen` does not compare the lockfile with `pyproject.toml`. Thus the step `uv lock --check` comes first. A lockfile that does not agree makes the job fail (PRD-CICD-004).
- The upload of the findings also runs when `dsml validate` fails, if the SARIF file exists.
- `dsml check-output` comes in M7. Until then, the job fails with the message of the subcommand.
- The plan job is only in the workflow if the model has the environment `dev` and the configuration has the key `infrastructure.output`. It uses the root module `<infrastructure.output>/envs/dev`.
- The plan role is read-only. It cannot write the S3 state lock, thus `tofu plan` uses `-lock=false`. The job does not apply.
- `model_commit` is the head commit of the pull request.
- OpenTofu does not show sensitive values in the plan text. The workflow uses no secret (PRD-CICD-015).

## AWS access

The plan job gets AWS credentials only through GitHub OIDC (PRD-CICD-010). The role ARN is `arn:aws:iam::<account>:role/<plan role>`. The function `plan_role` of `dsml.generate.infrastructure.names` gives the name, for example `order-service-dev-ci-plan`. The workflow uses no long-term access key.

## Toolchain install

The toolchain GitHub Action comes in M7 (PRD-CORE-050). Until then, each job that runs `dsml` installs the toolchain with `uv tool install`, at the version of the toolchain that wrote the workflow. The repository variable `DSML_INDEX_URL` gives the URL of the package index. M7 can change this step to the GitHub Action.

The workflow gives the full toolchain version. Thus a new toolchain release changes `pr.gen.yml`, and the golden file changes with it. The header still gives only the major version (PRD-CORE-038).

## Pinned actions

Each third-party action is pinned to a full commit SHA, with its version in a comment (PRD-CICD-014). The items `action-*` of `src/dsml/versions.toml` give the action, the SHA and the version:

| Item | Action | Version |
| --- | --- | --- |
| `action-checkout` | `actions/checkout` | 7.0.1 |
| `action-configure-aws-credentials` | `aws-actions/configure-aws-credentials` | 6.3.0 |
| `action-setup-opentofu` | `opentofu/setup-opentofu` | 2.0.2 |
| `action-setup-uv` | `astral-sh/setup-uv` | 10.3.0 |
| `action-upload-sarif` | `github/codeql-action/upload-sarif` | 4.38.3 |

The SHA is the commit of the release tag. For an annotated tag, it is the commit that the tag points to, not the tag object. The plan job installs the OpenTofu version of the item `opentofu`.

## Values in the workflow

A value from the model or the configuration goes into the workflow through the template filter `yaml_string`. The filter writes a YAML string in double quotes. It refuses a value that contains `${{`, so a value cannot add a GitHub Actions expression.

## Trace

The header gives the root packages, each FastAPI application and the environment `dev`. Each job is a symbol of the kind `job` in the trace manifest:

| Job | Elements |
| --- | --- |
| `validate`, `generate-check`, `check-output` | The root packages of the model |
| `test-<application>` | The application |
| `plan-dev` | The environment `dev` |

## Tests

- `tests/test_pipeline_generator.py` compares the output of the example model with `tests/golden/pipelines/order-service/`. If a change of the output is correct, run `uv run python scripts/write_golden_pipelines.py`.
- The CI step "Lint the golden workflows" runs actionlint on the golden workflows. The items `actionlint` and `actionlint-sha256` of `src/dsml/versions.toml` give the release and the SHA-256 hash of its archive. actionlint also runs shellcheck on the `run` scripts.
