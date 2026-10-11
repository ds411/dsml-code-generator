# Infrastructure generator

Story #76 added the infrastructure generator, the root module of each environment and the names module. The local modules, the tooling root module and the bootstrap root modules come in other M6 stories.

## Output

The generator writes in the folder of the key `infrastructure.output`. Without this key, it writes no file. For each `#Environment` element, the folder `envs/<environment>/` gets these files:

| File | Contents | Requirements |
| --- | --- | --- |
| `versions.gen.tf` | `required_version` and the exact AWS provider version of `src/dsml/versions.toml` | PRD-IAC-003, PRD-IAC-005 |
| `backend.gen.tf` | The S3 backend with `use_lockfile = true` and `encrypt = true`. With `iac.opentofu.state_encryption`, also the OpenTofu `encryption` block and its comment. | PRD-IAC-004, PRD-IAC-006 |
| `providers.gen.tf` | The AWS provider with `allowed_account_ids` and `default_tags` | PRD-IAC-024, PRD-IAC-035 |
| `main.gen.tf` | The values of the environment in `locals`. The module calls come here. | PRD-IAC-023 |
| `variables.gen.tf` | The variable `model_commit` | PRD-IAC-036 |
| `outputs.gen.tf` | The account, the Region, the environment and the product | PRD-IAC-010 |

The templates are in `src/dsml/templates/infrastructure/envs/`. Their format must agree with `tofu fmt` (PRD-CORE-035). Each top-level block of a file is a symbol of the kind `resource` in the trace manifest.

## Names

`dsml.generate.infrastructure.names` gives all names. Use these functions in the other infrastructure and pipeline stories:

| Function | Example | Requirements |
| --- | --- | --- |
| `hcl_address` | `api_service` | PRD-IAC-008 |
| `aws_name` | `order-service-dev-api-service` | PRD-IAC-008 |
| `tag_value` | A value with 256 characters or fewer | PRD-IAC-037 |
| `state_bucket` | `order-service-dev-tfstate-222222222222` | PRD-IAC-006, PRD-IAC-026 |
| `state_key` | `envs/dev/terraform.tfstate` | PRD-IAC-006 |
| `state_kms_alias` | `alias/order-service-dev-tfstate` | PRD-IAC-004 |
| `plan_role`, `deploy_role` | `order-service-dev-ci-plan`, `order-service-dev-ci-deploy` | PRD-IAC-027 |
| `push_role` | `order-service-tooling-ci-push` | PRD-IAC-028 |

The product is the kebab case of the name of the root package of the model, for example `order-service`. If a name is longer than the AWS limit of its resource type, the name gets the start of the full name, then "-" and the first 8 characters of the SHA-256 hash of the full name.

## Notes for the other stories

- The bootstrap root module of each account (#82) must create the state bucket of `state_bucket`. With OpenTofu state encryption, it must also create the KMS key with the alias of `state_kms_alias`.
- The pipelines (#83, #87) must give `model_commit` the full commit hash of the build (PRD-CICD-016).
