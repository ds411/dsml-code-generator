# Infrastructure generation PRD: OpenTofu and Terraform

Status date: 10 October 2026

## Summary

The infrastructure generator writes HCL that OpenTofu and Terraform both accept, from the infrastructure layer of the IR. It writes raw `aws_*` resources in local modules, one root module for each environment, and one bootstrap module for each AWS account.

- **Phase:** 1. The static site resources are in phase 2.
- **Goals covered:** N-002 (deterministic generation), N-004 (traceability to AWS resources) and N-005 (no dependency on one cloud).
- **Prefix:** PRD-IAC.
- **Related PRDs:** the DSML PRD gives the infrastructure layer. The CI/CD PRD runs `tofu plan` and `tofu apply`. Decision record 03 gives the tool and provider versions.

## Output structure and tool compatibility

One local module for each logical kind holds the resources. Each environment, the tooling account and the bootstrap of each account have their own root module.

```text
infra/
├── modules/
│   ├── network/{main,variables,outputs}.gen.tf
│   ├── container-service/
│   ├── relational-database/
│   ├── user-directory/
│   ├── secret-store/
│   └── static-site/                  # phase 2
├── envs/
│   ├── dev/{main,backend,providers,versions,variables,outputs}.gen.tf
│   ├── staging/
│   └── prod/
├── tooling/                          # ECR repositories
└── bootstrap/                        # one root for each account
    ├── tooling/
    ├── dev/
    ├── staging/
    └── prod/
```

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-IAC-001 | The generator must write the folders and root modules of the tree in the section "Output structure and tool compatibility" in the infrastructure output folder of the configuration file. | Test | Q23, Q24, Q61 |
| PRD-IAC-002 | Each generated HCL file must have a name that ends with `.gen.tf`. A platform engineer can add hand-written `.tf` files to a root module, and the generator must not change them. | Test | Q15 |
| PRD-IAC-003 | With the default configuration, the HCL must be valid for the pinned OpenTofu version and for the pinned Terraform version. The `required_version` constraint must accept the two pinned versions. | Test | Q22 |
| PRD-IAC-004 | A feature of only one tool must be available only through an IaC option in the configuration file, for example OpenTofu state encryption. With such an option, the generator must write a comment that names the one tool that accepts the output. | Test | Q22 |
| PRD-IAC-005 | Each root module must pin the AWS provider to the exact version of the version baseline. | Test | Q22, Q49 |
| PRD-IAC-006 | Each root module must use the S3 backend with S3 native state locks (`use_lockfile = true`) and encryption. The state bucket must be in the AWS account of the root module. | Test | Q22, Q44 |
| PRD-IAC-007 | The output must use only `aws_*` resources and data sources and local modules. It must not use a module from a registry or from a different repository. | Test | Q23 |
| PRD-IAC-008 | HCL addresses must be the snake case of the element names. AWS resource names must have the form `<product>-<environment>-<element>`. If a name is longer than the AWS limit, the generator must shorten it and add a hash of the full name. | Test | Q27 |
| PRD-IAC-009 | The image of each container service must be a root module variable `<application>_image_digest`. The CI/CD pipeline must give its value. | Test | Q25 |
| PRD-IAC-010 | Each environment root module must output the values that the pipelines need: the ECS cluster and service names, the API URL, the Cognito user pool ID, app client IDs and login domain, and, in phase 2, the S3 bucket and the CloudFront distribution ID. | Test | Q43 |

## Resources for each logical kind

Each local module writes the AWS resources of one logical kind. Values come from the AWS realization and the environment.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-IAC-011 | Network: the module must write a VPC with a public and a private subnet in each of two or more availability zones, an internet gateway, and the number of NAT gateways that `natGatewayCount` gives. | Test | Q21 |
| PRD-IAC-012 | Container service: the module must write an ECS cluster, a Fargate service and a task definition with the `cpu`, `memory` and `desiredCount` of the realization. Tasks must be in private subnets with no public IP address. | Test | Q21 |
| PRD-IAC-013 | Container service: the module must write target tracking auto scaling on CPU, between `minCount` and `maxCount`. | Test | Q21, Q24 |
| PRD-IAC-014 | Container service: the module must write an ALB in the public subnets with an HTTPS listener, an ACM certificate for the API domain, a redirect from HTTP to HTTPS, and a Route 53 record. The target group must use `/healthz` as the health check. | Test | Q21, PRD-APP-012 |
| PRD-IAC-015 | Container service: the task execution role must permit only image pulls from the tooling ECR repository, reads of the secrets that the service uses, and log writes. The task role must permit only access to the elements that the service uses (`#Uses`). | Test | Q21, Q27 |
| PRD-IAC-016 | Container service: the module must write a CloudWatch log group with a retention of 30 days, and a second task definition that runs the migration command of the application. | Test | Q21, Q53 |
| PRD-IAC-017 | Database: the module must write an RDS for PostgreSQL instance in private subnets with the `instanceClass` and `multiAz` of the realization, storage encryption with a KMS key, backups for 7 days, and a master password that RDS keeps in Secrets Manager. In prod, deletion protection must be on. | Test | Q21 |
| PRD-IAC-018 | Database: its security group must permit port 5432 only from the security groups of the container services that use it. | Test | Q21, Q27 |
| PRD-IAC-019 | User directory: the module must write one Cognito user pool, one app client for each application that uses it (no client secret, authorization code with PKCE, callback URLs on the environment domain), one group for each role value and a managed login domain. Self sign-up must be off. | Test | Q42 |
| PRD-IAC-020 | Secret store: the module must write one Secrets Manager secret and one KMS key for each secret element. The HCL must not contain secret values. | Test | PRD-TOP-006 |
| PRD-IAC-021 | Phase 2, static site: the module must write a private S3 bucket with versioning, a CloudFront distribution with origin access control, an ACM certificate in `us-east-1` and a Route 53 alias. CloudFront must return `/index.html` with HTTP 200 for paths that do not exist. | Test | Q21 |
| PRD-IAC-022 | Tooling: the tooling root module must write one ECR repository for each container application, with immutable tags, scan on push and a lifecycle policy. The repository policy must permit pulls by the task execution roles of the environment accounts. | Test | Q44 |
| PRD-IAC-042 | Container service: the ECS service must ignore changes to its task definition, because the pipeline sets it after the migrations. The service must use the ECS deployment circuit breaker with rollback. | Test | Q53 |

## Environments, AWS accounts and bootstrap

Each environment has its own AWS account, and a shared tooling account holds ECR. A bootstrap module prepares each account one time, before CI can deploy.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-IAC-023 | Each environment root module must call the same local modules. Only the environment attributes of PRD-DSML-042 can make two environments different. | Test | Q24 |
| PRD-IAC-024 | The AWS provider of each root module must set `allowed_account_ids` to the account ID of its environment or of the tooling account. | Test | Q44 |
| PRD-IAC-025 | The generator must not create AWS accounts. The accounts and AWS Organizations must exist before the bootstrap. | Inspection | Q44 |
| PRD-IAC-026 | The bootstrap root module of each account must write the state bucket (versioning, encryption, public access blocked), the GitHub OIDC identity provider and the IAM roles for CI. | Test | Q43, Q44 |
| PRD-IAC-027 | Each environment account must have a plan role with read-only access, which pull requests can use, and a deploy role, which only the GitHub environment of that account can use. The trust policies must check the repository and the environment in the `sub` claim. | Test | Q43 |
| PRD-IAC-028 | The tooling account must have a push role, which only workflows of the main branch and of release tags can use. | Test | Q43, Q44 |
| PRD-IAC-029 | The bootstrap root module must start with local state. The generator must write a README that gives the command to move that state into the bucket that the module creates. | Demonstration | Q44 |

## Security baseline and tags

The generated infrastructure is encrypted, private by default and uses least-privilege IAM. Tags connect each AWS resource to its model element.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-IAC-030 | Each resource that stores data (S3, RDS, Secrets Manager, ECR) must have encryption at rest. | Test | Q27 |
| PRD-IAC-031 | Only ALB listeners and CloudFront distributions can accept traffic from the internet. RDS must have `publicly_accessible = false`, and each S3 bucket must block public access. | Test | Q27 |
| PRD-IAC-032 | A security group must not permit ingress from `0.0.0.0/0` or `::/0`, except an ALB security group on ports 80 and 443. | Test | Q27 |
| PRD-IAC-033 | An IAM policy must not use the action `*` or a service wildcard such as `s3:*`. It can use the resource `*` only for actions that have no resource-level permissions in AWS. | Test | Q27 |
| PRD-IAC-034 | Each HTTPS listener must use the TLS security policy that the version baseline gives. | Test | Q49 |
| PRD-IAC-035 | The AWS provider of each root module must set `default_tags` with `dsml:product`, `dsml:environment` and `dsml:model-commit`. Each resource must add the tag `dsml:element` with the identity of its model element, and `dsml:application` where an application owns it. | Test | Q30 |
| PRD-IAC-036 | The value of `dsml:model-commit` must come from the root module variable `model_commit` at plan time. Generated files must not contain the commit. | Test | Q16, Q30, Q52 |
| PRD-IAC-037 | If a tag value is longer than the AWS limit of 256 characters, the generator must shorten it and add a hash of the full value. | Test | Q30 |

## Output checks

The language tools, a security scanner and a real deployment check the generated HCL.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-IAC-038 | `dsml check-output --infrastructure` must run `tofu fmt -check`, `tofu validate` (after `tofu init -backend=false`) and `tflint` with the AWS rule set on each root module. | Test | Q28 |
| PRD-IAC-039 | The toolchain CI must also run `terraform validate` on the golden output of each reference model. | Test | Q22 |
| PRD-IAC-040 | An IaC security scan of the golden output must find no finding with high or critical severity. The version baseline gives the scanner. | Test | Q27, Q49 |
| PRD-IAC-041 | After an apply, a second `tofu plan` with the same model and the same commit must show no change. | Test | Q16 |
