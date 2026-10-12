# Infrastructure generator

Story #76 added the infrastructure generator, the root module of each environment and the names module. Story #79 added the local modules `network` and `secret-store`. Story #81 added the local modules `relational-database` and `user-directory`. Story #80 added the local module `container-service`. The tooling root module and the bootstrap root modules come in other M6 stories. Story #162 (M9) added the local module `static-site` of phase 2.

## Output

The generator writes in the folder of the key `infrastructure.output`. Without this key, it writes no file. For each `#Environment` element, the folder `envs/<environment>/` gets these files:

| File | Contents | Requirements |
| --- | --- | --- |
| `versions.gen.tf` | `required_version` and the exact AWS provider version of `src/dsml/versions.toml` | PRD-IAC-003, PRD-IAC-005 |
| `backend.gen.tf` | The S3 backend with `use_lockfile = true` and `encrypt = true`. With `iac.opentofu.state_encryption`, also the OpenTofu `encryption` block and its comment. | PRD-IAC-004, PRD-IAC-006 |
| `providers.gen.tf` | The AWS provider with `allowed_account_ids` and `default_tags`. A root module with a static site also gets a second AWS provider with the alias `us_east_1` and the Region `us-east-1`. | PRD-IAC-021, PRD-IAC-024, PRD-IAC-035 |
| `main.gen.tf` | The values of the environment in `locals`, and one module call for each logical element | PRD-IAC-023 |
| `variables.gen.tf` | The variable `model_commit`, and the variables of the module calls, for example `<application>_image_digest` | PRD-IAC-009, PRD-IAC-036 |
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
| `container-service` | An ECS cluster, a Fargate service, the service task definition and the migration task definition, CPU target tracking auto scaling, an ALB with an HTTPS listener and an HTTP redirect, an ACM certificate with DNS validation, a Route 53 alias record, a target group, the task execution role, the task role, a log group and two security groups. | `application`, `container_port`, `cpu`, `desired_count`, `domain_name`, `ecr_account_id`, `ecr_region`, `ecr_repository`, `element`, `environment_variables`, `image_digest`, `kms_key_arns`, `max_count`, `memory`, `migration_command`, `min_count`, `names`, `private_subnet_ids`, `public_subnet_ids`, `secret_arns`, `secrets`, `vpc_id`, `zone_name` | PRD-IAC-009, PRD-IAC-012 to PRD-IAC-016, PRD-IAC-031 to PRD-IAC-034, PRD-IAC-042 |
| `static-site` | A private S3 bucket with versioning, SSE-S3 encryption, public access blocked and the owner of all objects, a bucket policy, a CloudFront distribution with origin access control, an ACM certificate in `us-east-1` with DNS validation, and Route 53 alias records `A` and `AAAA`. | `application`, `bucket_name`, `domain_name`, `element`, `origin_access_control_name`, `providers`, `zone_name` | PRD-IAC-021, PRD-IAC-030, PRD-IAC-031, PRD-IAC-034 |
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
- The callback URL is `https://<domain>/auth/callback` and the logout URL is `https://<domain>/`, on the domain of the environment. For a `react` application, the URLs are on its site domain, for example `https://order-portal.portal.dev.example.com/auth/callback` (story #162). For a `nextjs` application, the URLs are on its application domain, the domain of its container service, for example `https://order-web.web.dev.example.com/auth/callback` (story #181). If the authentication story of the Next.js target (#183) uses other paths, it must change `CALLBACK_PATH` and `LOGOUT_PATH` for the `nextjs` target.
- An application that is allocated to a static site with a `#Uses` link to the user directory also gets an app client.
- The managed login domain has the prefix `<product>-<environment>-<element>`.
- The root module outputs `<directory>_user_pool_id`, `<directory>_app_client_ids` and `<directory>_login_domain` (PRD-IAC-010).

These rules apply to the container service:

- Each `#ContainerService` element must have one allocated application with a known target. The FastAPI target uses port 8000 and the migration command `python -m app.migrate_gen`. The Next.js target uses port 3000 (PRD-APP-333) and the migration command `node migrate.gen.mjs` (PRD-APP-332). `TARGETS` in `src/dsml/generate/infrastructure/modules.py` gives these values.
- `cpu`, `memory`, `desired_count`, `min_count` and `max_count` come from the realization. Without a value, `cpu` is 256, `memory` is 512, `desired_count` is 1, `min_count` is `desired_count`, and `max_count` is two times `min_count`. The model must give `min_count <= desired_count <= max_count`.
- The auto scaling tracks an average CPU use of 70 %. The service ignores changes to its task definition and to its desired count, because the pipeline and the auto scaling set them (PRD-IAC-042).
- The API domain is `<application>.<environment domain>`, for example `order-api.orders.dev.example.com`. The public Route 53 hosted zone of the environment domain must exist.
- The HTTPS listener uses `alb-tls-policy` of `src/dsml/versions.toml`. The target group uses the health check `/healthz`. The log group keeps the logs for 30 days.
- The image is `<tooling account>.dkr.ecr.<tooling region>.amazonaws.com/<repository>@<digest>`. The root module variable `<application>_image_digest` gives the digest.
- Only the ALB security group accepts traffic from `0.0.0.0/0`, on ports 80 and 443. The tasks accept traffic only from the ALB, and send traffic only on port 443. The database module adds the rules on port 5432.
- The task execution role can pull images from the ECR repository of the application, write logs, and read the secrets and KMS keys of the elements that the service uses. The task role has no policy, because the database and the user directory need no IAM access.
- The container gets `APP_ENVIRONMENT`, the name of the environment (`local.environment`), and `AWS_REGION` (story #205). A `#Uses` link to a database gives `DATABASE_HOST`, `DATABASE_NAME`, `DATABASE_PORT`, `DATABASE_SSL_MODE` (`require`), and the secrets `DATABASE_USER` and `DATABASE_PASSWORD` from the master user secret. A `#Uses` link to a user directory gives `COGNITO_USER_POOL_ID` and `COGNITO_APP_CLIENT_ID`. A `nextjs` application also gets `COGNITO_LOGIN_DOMAIN`, the output `login_domain` of the user directory. The root layout reads `AWS_REGION` and the three Cognito variables (PRD-APP-325, `docs/notes/nextjs-generator.md`). A `#Uses` link to a secret store gives a secret with the upper snake case of the element name.
- The test `test_container_service_gets_each_mandatory_variable_of_the_application` compares the mandatory variables of the FastAPI target (`VARIABLES` in `src/dsml/generate/fastapi.py`) with the environment variables and the secrets of each container service. It examines the order service and the order portal. The test model `shop` has no user directory, thus it does not get the Cognito variables, and the test does not examine it.
- The root module outputs `<service>_api_url`, `<service>_cluster_name`, `<service>_service_name`, `<service>_migration_task_definition`, `<service>_security_group_id` and `<service>_private_subnet_ids` (PRD-IAC-010). The pipeline uses the last three to run the migration task.

These rules apply to the static site (story #162, Q21):

- Each `#StaticSite` element must have one allocated application with the target `react`.
- The site domain is `<application>.<environment domain>`, the same form as the API domain, for example `order-portal.portal.dev.example.com`. The public Route 53 hosted zone of the environment domain must exist.
- The bucket name is `<product>-<environment>-<element>-<account ID>`, because S3 bucket names are global.
- The bucket policy permits only `s3:GetObject`, only for the service principal `cloudfront.amazonaws.com`, and only with the ARN of the distribution in `AWS:SourceArn`.
- The bucket uses SSE-S3 (PRD-IAC-030). CloudFront with origin access control reads SSE-S3 objects with no KMS key policy.
- CloudFront accepts only ACM certificates of `us-east-1`. Thus the call gives the module the providers `aws` and `aws.us_east_1`, and the certificate and its validation use `aws.us_east_1`.
- The viewer connections use HTTPS. HTTP gets a redirect. The minimum TLS version is `cloudfront-tls-policy` of `src/dsml/versions.toml` (PRD-IAC-034).
- The bucket gives HTTP 403 for an object that does not exist, because the distribution cannot list the bucket. Thus CloudFront returns `/index.html` with HTTP 200 for the errors 403 and 404. The application then shows the route.
- The distribution uses the AWS managed policies `Managed-CachingOptimized` and `Managed-SecurityHeadersPolicy`, and the price class `PriceClass_100`.
- The root module outputs `<site>_bucket_name`, `<site>_distribution_id` and `<site>_url` (PRD-IAC-010).
- The deploy role of each environment account with a static site gets the statements `SiteRead`, `SiteCertificateRequest`, `SiteCertificates`, `SiteDistributions` and `SiteBuckets`. The bucket statement applies only to the site buckets, not to the state bucket. It also permits the upload of the static files and `cloudfront:CreateInvalidation` for the pipeline.
- `.checkov.yaml` skips the access logs, the WAF, the origin failover and the geo restriction of CloudFront. The phase 2 PRD does not give them.

In the trace manifest, each module call, each of its outputs and variables, and each block of its module are symbols of the logical element and of its AWS realization (PRD-TRACE-007).

The example model has no secret store. Thus the golden files of the test model `tests/models/ir/solution-layers.sysml` are in `tests/golden/infrastructure/shop/`. The golden files of the phase 2 reference model `docs/model/examples/order-portal/` are in `tests/golden/infrastructure/order-portal/`. The golden files of the phase 3 reference model `docs/model/examples/order-web/` are in `tests/golden/infrastructure/order-web/` (story #181), and `tests/test_infrastructure_nextjs.py` examines them. `scripts/write_golden_infrastructure.py` writes the golden files of the four models.

## Names

`dsml.generate.infrastructure.names` gives all names. Use these functions in the other infrastructure and pipeline stories:

| Function | Example | Requirements |
| --- | --- | --- |
| `hcl_address` | `api_service` | PRD-IAC-008 |
| `aws_name` | `order-service-dev-api-service` | PRD-IAC-008 |
| `tag_value` | A value with 256 characters or fewer | PRD-IAC-037 |
| `state_bucket` | `order-service-dev-tfstate-222222222222` | PRD-IAC-006, PRD-IAC-026 |
| `site_bucket` | `order-portal-dev-portal-site-222222222222` | PRD-IAC-008, PRD-IAC-021 |
| `state_key` | `envs/dev/terraform.tfstate` | PRD-IAC-006 |
| `state_kms_alias` | `alias/order-service-dev-tfstate` | PRD-IAC-004 |
| `kms_alias` | `alias/shop-dev-secrets` | PRD-IAC-008, PRD-IAC-020 |
| `plan_role`, `deploy_role` | `order-service-dev-ci-plan`, `order-service-dev-ci-deploy` | PRD-IAC-027 |
| `push_role` | `order-service-tooling-ci-push` | PRD-IAC-028 |
| `ecr_repository` | `order-service-tooling-order-api` | PRD-IAC-008, PRD-IAC-022 |
| `task_execution_role`, `task_role` | `order-service-dev-api-service-execution`, `order-service-dev-api-service-task` | PRD-IAC-015, PRD-IAC-022 |

The product is the kebab case of the name of the root package of the model, for example `order-service`. If a name is longer than the AWS limit of its resource type, the name gets the start of the full name, then "-" and the first 8 characters of the SHA-256 hash of the full name.

## Notes for the other stories

- The bootstrap root module of each account (#82) must create the state bucket of `state_bucket`. With OpenTofu state encryption, it must also create the KMS key with the alias of `state_kms_alias`.
- The pipelines (#83, #87) must give `model_commit` the full commit hash of the build (PRD-CICD-016).
- The tooling root module (#82) must create the ECR repository of `ecr_repository`, and permit pulls by the roles of `task_execution_role`.
- The main pipeline (#87) must give `<application>_image_digest`. It must run the migration task with the outputs `<service>_cluster_name`, `<service>_migration_task_definition`, `<service>_private_subnet_ids` and `<service>_security_group_id`, and then set the task definition of the service.
- The arguments function of a `LocalModule` gets a `CallContext` with the IR, the environment element and the product. A `LocalModule` can also give template data for its module files, for example the PostgreSQL version, and root module variables, for example the image digest.
- The pipeline story of M9 (#165) must upload the static files to `<site>_bucket_name` and invalidate `<site>_distribution_id`. The deploy role permits the two actions.
- The CORS story of M9 (#164) sets `CORS_ALLOWED_ORIGINS` of a container service to `https://<site domain>` of each `react` application that calls its application (PRD-APP-136).
