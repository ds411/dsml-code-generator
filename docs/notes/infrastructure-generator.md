# Infrastructure generator

Story #76 added the infrastructure generator, the root module of each environment and the names module. Story #79 added the local modules `network` and `secret-store`. Story #81 added the local modules `relational-database` and `user-directory`. The other local modules, the tooling root module and the bootstrap root modules come in other M6 stories.

## Output

The generator writes in the folder of the key `infrastructure.output`. Without this key, it writes no file. For each `#Environment` element, the folder `envs/<environment>/` gets these files:

| File | Contents | Requirements |
| --- | --- | --- |
| `versions.gen.tf` | `required_version` and the exact AWS provider version of `src/dsml/versions.toml` | PRD-IAC-003, PRD-IAC-005 |
| `backend.gen.tf` | The S3 backend with `use_lockfile = true` and `encrypt = true`. With `iac.opentofu.state_encryption`, also the OpenTofu `encryption` block and its comment. | PRD-IAC-004, PRD-IAC-006 |
| `providers.gen.tf` | The AWS provider with `allowed_account_ids` and `default_tags` | PRD-IAC-024, PRD-IAC-035 |
| `main.gen.tf` | The values of the environment in `locals`, and one module call for each logical element | PRD-IAC-023 |
| `variables.gen.tf` | The variable `model_commit` | PRD-IAC-036 |
| `outputs.gen.tf` | The account, the Region, the environment and the product, and the outputs of the module calls | PRD-IAC-010 |

The templates are in `src/dsml/templates/infrastructure/envs/`. Their format must agree with `tofu fmt` (PRD-CORE-035). Each top-level block of a file is a symbol of the kind `resource` in the trace manifest.

## Local modules

`dsml.generate.infrastructure.modules` gives the local modules in `MODULES`. Each module has the files `main.gen.tf`, `variables.gen.tf` and `outputs.gen.tf` in `modules/<module>/`. The templates are in `src/dsml/templates/infrastructure/modules/`. The generator writes a module only if the model has an element of its logical kind.

Each environment root module calls a module one time for each logical element of its kind. The name of the call is the snake case of the element name, for example `module "network"`. The arguments come from the AWS realization of the element in the environment, with the overrides of the environment (PRD-DSML-042). Each call gives the module the identity of the logical element in the variable `element`. Each resource that accepts tags has the tag `dsml:element` with this value (PRD-IAC-035).

| Module | Resources | Arguments of the call | Requirements |
| --- | --- | --- | --- |
| `network` | A VPC, an internet gateway, a public and a private subnet in each availability zone, the route tables, and one NAT gateway with an Elastic IP address in each of the first `nat_gateway_count` zones. The default security group permits no traffic. | `element`, `name`, `nat_gateway_count`, `zone_count` | PRD-IAC-011 |
| `secret-store` | One KMS key with key rotation, its alias, and one Secrets Manager secret that the key encrypts. The HCL contains no secret value. | `element`, `key_alias`, `name` | PRD-IAC-020, PRD-IAC-030 |
| `relational-database` | An RDS for PostgreSQL instance in a DB subnet group of the private subnets, a KMS key with key rotation and its alias, a security group, and the rules on port 5432. | `database_name`, `deletion_protection`, `element`, `instance_class`, `master_username`, `multi_az`, `name`, `source_security_group_ids`, `subnet_ids`, `vpc_id` | PRD-IAC-017, PRD-IAC-018, PRD-IAC-030, PRD-IAC-031 |
| `user-directory` | One Cognito user pool, a managed login domain, one group for each role value, and one app client and its managed login style for each application. | `clients`, `domain_prefix`, `element`, `groups`, `name` | PRD-IAC-019 |

These rules apply to the network:

- `nat_gateway_count` is the value of `natGatewayCount`. If the realization does not set it, the value is 1, because the tasks in the private subnets must get to ECR and to the AWS APIs.
- `zone_count` is 2, or the number of NAT gateways if that number is more than 2.
- The VPC CIDR block is `10.0.0.0/16`. Each subnet gets one sixteenth of it.
- Each private subnet sends its internet traffic to a NAT gateway. With no NAT gateway, the private subnets have no internet route.

These rules apply to the database:

- The PostgreSQL version is the release line of `postgresql` in `src/dsml/versions.toml`. `instance_class` and `multi_az` come from `instanceClass` and `multiAz` of the realization.
- `publicly_accessible = false`. The storage and the master password use the KMS key of the database. RDS keeps the master password in Secrets Manager (`manage_master_user_password = true`). The backups stay for 7 days.
- Deletion protection and a final snapshot are on only in prod.
- `source_security_group_ids` gives the security group of each container service with a `#Uses` link to the database. The database security group permits port 5432 only from these security groups. The module also adds an egress rule on port 5432 from each of these security groups to the database, because the container service module permits egress only on port 443. There is no CIDR rule.
- `vpc_id` and `subnet_ids` come from the outputs `vpc_id` and `private_subnet_ids` of the one network of the model. A model with a database must have one `#Network` element.

These rules apply to the user directory (Q42):

- Only an administrator can create users, thus self sign-up is off.
- `groups` has one value for each value of the `#Roles` enumeration. The group name is the role value.
- `clients` has one app client for each application that uses the user directory: an application with a `#Uses` link to it, or an application that is allocated to a container service with a `#Uses` link to it. The app client has no client secret and uses the authorization code flow. The application must send a PKCE code challenge.
- The callback URL is `https://<domain>/auth/callback` and the logout URL is `https://<domain>/`, on the domain of the environment.
- The managed login domain has the prefix `<product>-<environment>-<element>`.
- The root module outputs `<directory>_user_pool_id`, `<directory>_app_client_ids` and `<directory>_login_domain` (PRD-IAC-010).

In the trace manifest, each module call, each of its outputs and each block of its module are symbols of the logical element and of its AWS realization (PRD-TRACE-007).

The example model has no secret store. Thus the golden files of the test model `tests/models/ir/solution-layers.sysml` are in `tests/golden/infrastructure/shop/`. `scripts/write_golden_infrastructure.py` writes the golden files of the two models.

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
| `kms_alias` | `alias/shop-dev-secrets` | PRD-IAC-008, PRD-IAC-020 |
| `plan_role`, `deploy_role` | `order-service-dev-ci-plan`, `order-service-dev-ci-deploy` | PRD-IAC-027 |
| `push_role` | `order-service-tooling-ci-push` | PRD-IAC-028 |

The product is the kebab case of the name of the root package of the model, for example `order-service`. If a name is longer than the AWS limit of its resource type, the name gets the start of the full name, then "-" and the first 8 characters of the SHA-256 hash of the full name.

## Notes for the other stories

- The bootstrap root module of each account (#82) must create the state bucket of `state_bucket`. With OpenTofu state encryption, it must also create the KMS key with the alias of `state_kms_alias`.
- The pipelines (#83, #87) must give `model_commit` the full commit hash of the build (PRD-CICD-016).
- The container service module (#80) must add a `LocalModule` to `MODULES` in `dsml.generate.infrastructure.modules`, with their templates in `src/dsml/templates/infrastructure/modules/<module>/`. Use the outputs `vpc_id`, `public_subnet_ids` and `private_subnet_ids` of the network module, and `secret_arn` and `key_arn` of the secret store module.
- The container service module (#80) must output `security_group_id`. The database call uses `module.<service>.security_group_id`. The container service can use the outputs `address`, `port`, `database_name`, `master_user_secret_arn` and `kms_key_arn` of the database module. The task execution role must have `secretsmanager:GetSecretValue` on the secret and `kms:Decrypt` on the key.
- The arguments function of a `LocalModule` gets a `CallContext` with the IR, the environment element and the product. A `LocalModule` can also give template data for its module files, for example the PostgreSQL version.
