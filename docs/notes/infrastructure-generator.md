# Infrastructure generator

Story #76 added the infrastructure generator, the root module of each environment and the names module. Story #81 added the local modules `relational-database` and `user-directory`. The other local modules, the tooling root module and the bootstrap root modules come in other M6 stories.

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

## Local modules

The generator writes a local module in `modules/<module>/` only if the model has an element of its kind. Each module has `main.gen.tf`, `variables.gen.tf` and `outputs.gen.tf`. All environments use the same module files (PRD-IAC-023). The file `main.gen.tf` of each environment root module has one module call for each element, with the HCL address of the element, for example `module "order_db"`. The header of a module file gives the logical elements of its kind and their realizations. The header of `main.gen.tf` and `outputs.gen.tf` of a root module also gives the elements of the module calls and the overrides of the environment.

### relational-database

One call for each `#RelationalDatabase` element (PRD-IAC-017, PRD-IAC-018, PRD-IAC-030, PRD-IAC-031):

- An RDS for PostgreSQL instance with the release line of `postgresql` in `src/dsml/versions.toml`, and the `instanceClass` and `multiAz` of the realization and the overrides of the environment.
- A DB subnet group in the private subnets, and `publicly_accessible = false`.
- A KMS key with key rotation for the storage and for the master password. RDS keeps the master password in Secrets Manager (`manage_master_user_password = true`).
- Backups for 7 days. Deletion protection and a final snapshot only in prod.
- A security group with one ingress rule on port 5432 for each container service that has a `#Uses` link to the database. The rule refers to the security group of the service. The module also adds an egress rule on port 5432 from the security group of each service to the database. There is no CIDR rule.

### user-directory

One call for each `#UserDirectory` element (PRD-IAC-019, Q42):

- One Cognito user pool. Only an administrator can create users, thus self sign-up is off.
- A managed login domain with the prefix `<product>-<environment>-<element>`, and the managed login style of Cognito for each app client.
- One user pool group for each value of the `#Roles` enumeration. The group name is the role value.
- One app client for each application that uses the user directory: an application that is allocated to a container service with a `#Uses` link to the user directory, or an application with a `#Uses` link to it. The app client has no client secret and uses the authorization code flow. The application must send a PKCE code challenge. The callback URL is `https://<domain>/auth/callback` and the logout URL is `https://<domain>/`, on the domain of the environment.

The environment root module outputs `<directory>_user_pool_id`, `<directory>_app_client_ids` and `<directory>_login_domain` for each user directory (PRD-IAC-010). In the example model, these are `users_user_pool_id`, `users_app_client_ids` and `users_login_domain`.

## Notes for the other stories

- The bootstrap root module of each account (#82) must create the state bucket of `state_bucket`. With OpenTofu state encryption, it must also create the KMS key with the alias of `state_kms_alias`.
- The pipelines (#83, #87) must give `model_commit` the full commit hash of the build (PRD-CICD-016).
- The module calls of `relational-database` use these outputs of other local modules. The network module (#79) must output `vpc_id` and `private_subnet_ids`. The container service module (#80) must output `security_group_id`. The module address is the HCL address of the element, for example `module.network` and `module.api_service`.
- The container service module (#80) can use the outputs `address`, `port`, `database_name`, `master_user_secret_arn` and `kms_key_arn` of the database module. The task execution role must have `secretsmanager:GetSecretValue` on the secret and `kms:Decrypt` on the key.
