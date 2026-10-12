# Pipeline generator

Story #83 added the pipeline generator and the pull request workflow `pr.gen.yml`. Story #87 added the main workflow `main.gen.yml` and the promote workflow `promote.gen.yml`. Story #89 added the README `README.gen.md` with the repository settings.

## Output

The generator writes in the folder of the key `pipelines.output`, normally `.github/workflows`. Without this key, it writes no file. The workflows run their commands in the folder of the configuration file. Thus the configuration file must be in the root of the repository.

The templates are in `src/dsml/templates/pipelines/`. The macro of the deploy job is in `deploy.j2`, and `main.gen.yml.j2` and `promote.gen.yml.j2` import it. The code is in `src/dsml/generate/pipelines/`. The module `deploy.py` gives the build jobs and the deploy jobs.

`main.gen.yml` and `promote.gen.yml` are only in the output if the configuration has the key `infrastructure.output` and the model has a container application. `promote.gen.yml` is only in the output if the model has the environment `staging` or `prod`.

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

## Jobs of `main.gen.yml`

The trigger is a push to the branch `main`. The trust policy of the push role permits only this branch and the release tags (PRD-IAC-028).

| Job | Steps | Permissions | Requirements |
| --- | --- | --- | --- |
| `build-<application>` | For each container application: build the image from the `Dockerfile` of the application folder, push it to the ECR repository of the tooling account with the push role, and give the digest as a job output | `contents: read`, `id-token: write` | PRD-CICD-007, PRD-CICD-010 |
| `deploy-dev` | The deploy steps below, with the digests of the build jobs and `model_commit` set to the commit of the push | `contents: read`, `id-token: write` | PRD-CICD-007, PRD-CICD-009, PRD-CICD-012, PRD-CICD-016 to PRD-CICD-018, PRD-CICD-021 |

The image tag is the commit. The ECR tags are immutable. If the image of the commit is already in ECR, for example in a second run of the workflow, the build job does not build again and gives the digest of the image in ECR.

## Jobs of `promote.gen.yml`

The triggers are a push of a release tag `v*`, and a manual run with the input `commit`: the full commit hash of a main build. The workflow builds no image (PRD-CICD-008).

| Job | Steps | Permissions | Requirements |
| --- | --- | --- | --- |
| `find-build` | Read the commit: the input, or the commit of the tag. Find the image digest of each application with the tag of the commit in ECR, with the push role. If an image is not in ECR, the job fails. | `id-token: write` | PRD-CICD-008, PRD-CICD-010 |
| `deploy-staging` | The deploy steps below, with the digests and the commit of `find-build` | `contents: read`, `id-token: write` | PRD-CICD-008, PRD-CICD-009, PRD-CICD-012, PRD-CICD-016 to PRD-CICD-018, PRD-CICD-021 |
| `deploy-prod` | The same steps. The job needs `find-build` and `deploy-staging`. | `contents: read`, `id-token: write` | PRD-CICD-020 and the requirements of `deploy-staging` |

The deploy jobs check out the commit of the build. Thus they apply the infrastructure code of the same commit.

A required reviewer of the GitHub environment `prod` must approve the job `deploy-prod` (PRD-CICD-020). The repository administrator sets this rule. `README.gen.md` gives the settings (PRD-CICD-013).

## Repository settings

The generator writes `README.gen.md` in the output folder of the workflows (PRD-CICD-013). The README tells a repository administrator which GitHub settings the workflows need. The generator does not change the settings of a repository.

| Section | Contents | Condition |
| --- | --- | --- |
| Order of the setup | Apply the bootstrap root modules, then the tooling root module, then make the GitHub settings. The bootstrap modules write the IAM roles of CI. | The configuration has the key `infrastructure.output`, and the workflows have a plan job or a deploy job. The tooling step needs `main.gen.yml`. |
| GitHub environments | One row for each deploy job: the environment, the workflow, the deployment branches and tags, and the required reviewers. Only `prod` has required reviewers. | The workflows have a deploy job. |
| Branch protection of the main branch | A branch ruleset for `main`. The required status checks are the job names of `pr.gen.yml`. | Always |
| Repository variables | `DSML_INDEX_URL` | Always |
| Code scanning | The upload of the findings needs code scanning. | Always |

The deployment branches and tags of `dev` are the branch `main`. For `staging` and `prod`, they are the branch `main` and the tags `v*`. The trust policy of the push role permits only these refs (PRD-IAC-028). The trust policy of each deploy role permits only its GitHub environment (PRD-IAC-027). Thus the names of the environments must be exactly the same as in the table.

Markdown permits no comment line of the header. Thus the README starts with the HTML comment `<!-- Generated by dsml. Do not edit. -->`, as the README of a bootstrap root module. The README has no trace symbols.

## Deploy steps

Each deploy job has the GitHub environment of its target environment (PRD-CICD-012). Its `concurrency` group is `deploy-<environment>` in all workflows, with `cancel-in-progress: false` (PRD-CICD-009). Thus a new run waits, and it does not cancel a running deployment. GitHub keeps only the newest waiting run of a group: a newer run replaces a waiting run.

The job runs these steps in the folder of the root module of the environment. A failed step stops the job.

1. `tofu init`, then `tofu apply` with `model_commit` and the image digest variable of each application (PRD-CICD-016).
2. For each application with a database: start the migration task definition as a one-off ECS task with the network of the service, and wait until it stops. If the exit code of the container is not 0, the job fails before it changes a service (PRD-CICD-017).
3. For each container service: set the service to the newest revision of its task definition. Then wait until the deployment completes and the service is stable. If the circuit breaker rolls back the deployment, the job fails (PRD-CICD-018).
4. Write the job summary (PRD-CICD-021).

The steps read the cluster, the service, the migration task family, the subnets and the security group from the outputs of the root module (PRD-IAC-010). The task family and the log group come from `dsml.generate.infrastructure.names`.

The ECS service ignores changes to its task definition (PRD-IAC-042). Thus `tofu apply` registers the new task definitions, but it does not change the service.

The job summary gives the environment, the job status, the model commit, the image digest of each application, the migration tasks and the new task definition of each service. The deploy role cannot read CloudWatch logs. Thus the summary gives the log group and the log stream of each migration task, and the log stream gives the applied migrations. The summary gives no secret value (PRD-CICD-015).

## AWS access

The jobs get AWS credentials only through GitHub OIDC (PRD-CICD-010). The workflows use no long-term access key. The functions of `dsml.generate.infrastructure.names` give the role names:

| Role | Function | Example | Jobs |
| --- | --- | --- | --- |
| Plan role | `plan_role` | `order-service-dev-ci-plan` | `plan-dev` |
| Push role | `push_role` | `order-service-tooling-ci-push` | `build-<application>`, `find-build` |
| Deploy role | `deploy_role` | `order-service-staging-ci-deploy` | `deploy-<environment>` |

The role ARN is `arn:aws:iam::<account>:role/<role>`.

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

The header of `pr.gen.yml` gives the root packages, each FastAPI application and the environment `dev`. The headers of `main.gen.yml` and `promote.gen.yml` give the tooling account, each container application and its container service, and the environments of the deploy jobs. Each job is a symbol of the kind `job` in the trace manifest:

| Job | Elements |
| --- | --- |
| `validate`, `generate-check`, `check-output` | The root packages of the model |
| `test-<application>` | The application |
| `plan-dev` | The environment `dev` |
| `build-<application>` | The application |
| `find-build` | The container applications |
| `deploy-<environment>` | The environment |

## Tests

- `tests/test_pipeline_deploy.py` tests the jobs of `main.gen.yml` and `promote.gen.yml`: the job order, the permissions, the concurrency groups and the environments.
- `tests/test_pipeline_readme.py` tests `README.gen.md`. A test compares the environments and the repository variables of the golden workflows with the tables of the golden README.
- `tests/test_pipeline_generator.py` compares the output of the example model with `tests/golden/pipelines/order-service/`. If a change of the output is correct, run `uv run python scripts/write_golden_pipelines.py`.
- The CI step "Lint the golden workflows" runs actionlint on the golden workflows. The items `actionlint` and `actionlint-sha256` of `src/dsml/versions.toml` give the release and the SHA-256 hash of its archive. actionlint also runs shellcheck on the `run` scripts.
