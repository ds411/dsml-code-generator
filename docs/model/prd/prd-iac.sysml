package PrdIac {
    private import DSML::*;
    private import PrdNeeds::*;

    #Requirement requirement <'PRD-IAC-001'> iac001 {
        doc /* The generator must write the folders and root modules of the tree in the section "Output structure and tool compatibility" in the infrastructure output folder of the configuration file. */
        :>> title = "Folder layout"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-002'> iac002 {
        doc /* Each generated HCL file must have a name that ends with .gen.tf. A platform engineer can add hand-written .tf files to a root module, and the generator must not change them. */
        :>> title = "HCL file names"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-003'> iac003 {
        doc /* With the default configuration, the HCL must be valid for the pinned OpenTofu version and for the pinned Terraform version. The required_version constraint must accept the two pinned versions. */
        :>> title = "Two-tool HCL"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-004'> iac004 {
        doc /* A feature of only one tool must be available only through an IaC option in the configuration file, for example OpenTofu state encryption. With such an option, the generator must write a comment that names the one tool that accepts the output. */
        :>> title = "One-tool features"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-005'> iac005 {
        doc /* Each root module must pin the AWS provider to the exact version of the version baseline. */
        :>> title = "Provider pin"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-006'> iac006 {
        doc /* Each root module must use the S3 backend with S3 native state locks (use_lockfile = true) and encryption. The state bucket must be in the AWS account of the root module. */
        :>> title = "S3 backend"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-007'> iac007 {
        doc /* The output must use only aws_* resources and data sources and local modules. It must not use a module from a registry or from a different repository. */
        :>> title = "Raw resources only"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-008'> iac008 {
        doc /* HCL addresses must be the snake case of the element names. AWS resource names must have the form <product>-<environment>-<element>. If a name is longer than the AWS limit, the generator must shorten it and add a hash of the full name. */
        :>> title = "Resource names"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-IAC-009'> iac009 {
        doc /* The image of each container service must be a root module variable <application>_image_digest. The CI/CD pipeline must give its value. */
        :>> title = "Image digest variable"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-010'> iac010 {
        doc /* Each environment root module must output the values that the pipelines need: the ECS cluster and service names, the API URL, the Cognito user pool ID, app client IDs and login domain, and, in phase 2, the S3 bucket and the CloudFront distribution ID. */
        :>> title = "Root outputs"; :>> kind = RequirementKind::interface; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-011'> iac011 {
        doc /* Network: the module must write a VPC with a public and a private subnet in each of two or more availability zones, an internet gateway, and the number of NAT gateways that natGatewayCount gives. */
        :>> title = "Network resources"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-012'> iac012 {
        doc /* Container service: the module must write an ECS cluster, a Fargate service and a task definition with the cpu, memory and desiredCount of the realization. Tasks must be in private subnets with no public IP address. */
        :>> title = "ECS service"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-013'> iac013 {
        doc /* Container service: the module must write target tracking auto scaling on CPU, between minCount and maxCount. */
        :>> title = "Auto scaling"; :>> kind = RequirementKind::performance; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-014'> iac014 {
        doc /* Container service: the module must write an ALB in the public subnets with an HTTPS listener, an ACM certificate for the API domain, a redirect from HTTP to HTTPS, and a Route 53 record. The target group must use /healthz as the health check. */
        :>> title = "Load balancer"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-015'> iac015 {
        doc /* Container service: the task execution role must permit only image pulls from the tooling ECR repository, reads of the secrets that the service uses, and log writes. The task role must permit only access to the elements that the service uses (#Uses). */
        :>> title = "Task roles"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-016'> iac016 {
        doc /* Container service: the module must write a CloudWatch log group with a retention of 30 days, and a second task definition that runs the migration command of the application. */
        :>> title = "Logs and migration task"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-017'> iac017 {
        doc /* Database: the module must write an RDS for PostgreSQL instance in private subnets with the instanceClass and multiAz of the realization, storage encryption with a KMS key, backups for 7 days, and a master password that RDS keeps in Secrets Manager. In prod, deletion protection must be on. */
        :>> title = "RDS instance"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-018'> iac018 {
        doc /* Database: its security group must permit port 5432 only from the security groups of the container services that use it. */
        :>> title = "Database access"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-019'> iac019 {
        doc /* User directory: the module must write one Cognito user pool, one app client for each application that uses it (no client secret, authorization code with PKCE, callback URLs on the environment domain), one group for each role value and a managed login domain. Self sign-up must be off. */
        :>> title = "Cognito resources"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-020'> iac020 {
        doc /* Secret store: the module must write one Secrets Manager secret and one KMS key for each secret element. The HCL must not contain secret values. */
        :>> title = "Secrets"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-021'> iac021 {
        doc /* Phase 2, static site: the module must write a private S3 bucket with versioning, a CloudFront distribution with origin access control, an ACM certificate in us-east-1 and a Route 53 alias. CloudFront must return /index.html with HTTP 200 for paths that do not exist. */
        :>> title = "Static site"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-022'> iac022 {
        doc /* Tooling: the tooling root module must write one ECR repository for each container application, with immutable tags, scan on push and a lifecycle policy. The repository policy must permit pulls by the task execution roles of the environment accounts. */
        :>> title = "ECR repositories"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-023'> iac023 {
        doc /* Each environment root module must call the same local modules. Only the environment attributes of PRD-DSML-042 can make two environments different. */
        :>> title = "Same modules"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-024'> iac024 {
        doc /* The AWS provider of each root module must set allowed_account_ids to the account ID of its environment or of the tooling account. */
        :>> title = "Allowed accounts"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-025'> iac025 {
        doc /* The generator must not create AWS accounts. The accounts and AWS Organizations must exist before the bootstrap. */
        :>> title = "No account creation"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-026'> iac026 {
        doc /* The bootstrap root module of each account must write the state bucket (versioning, encryption, public access blocked), the GitHub OIDC identity provider and the IAM roles for CI. */
        :>> title = "Bootstrap module"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-027'> iac027 {
        doc /* Each environment account must have a plan role with read-only access, which pull requests can use, and a deploy role, which only the GitHub environment of that account can use. The trust policies must check the repository and the environment in the sub claim. */
        :>> title = "Plan and deploy roles"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-028'> iac028 {
        doc /* The tooling account must have a push role, which only workflows of the main branch and of release tags can use. */
        :>> title = "Push role"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-029'> iac029 {
        doc /* The bootstrap root module must start with local state. The generator must write a README that gives the command to move that state into the bucket that the module creates. */
        :>> title = "Bootstrap state"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-030'> iac030 {
        doc /* Each resource that stores data (S3, RDS, Secrets Manager, ECR) must have encryption at rest. */
        :>> title = "Encryption at rest"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-031'> iac031 {
        doc /* Only ALB listeners and CloudFront distributions can accept traffic from the internet. RDS must have publicly_accessible = false, and each S3 bucket must block public access. */
        :>> title = "Private by default"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-032'> iac032 {
        doc /* A security group must not permit ingress from 0.0.0.0/0 or ::/0, except an ALB security group on ports 80 and 443. */
        :>> title = "Ingress rules"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-033'> iac033 {
        doc /* An IAM policy must not use the action * or a service wildcard such as s3:*. It can use the resource * only for actions that have no resource-level permissions in AWS. */
        :>> title = "Least privilege"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-034'> iac034 {
        doc /* Each HTTPS listener must use the TLS security policy that the version baseline gives. */
        :>> title = "TLS policy"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-035'> iac035 {
        doc /* The AWS provider of each root module must set default_tags with dsml:product, dsml:environment and dsml:model-commit. Each resource must add the tag dsml:element with the identity of its model element, and dsml:application where an application owns it. */
        :>> title = "Trace tags"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-IAC-036'> iac036 {
        doc /* The value of dsml:model-commit must come from the root module variable model_commit at plan time. Generated files must not contain the commit. */
        :>> title = "Commit tag source"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-IAC-037'> iac037 {
        doc /* If a tag value is longer than the AWS limit of 256 characters, the generator must shorten it and add a hash of the full value. */
        :>> title = "Tag length"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame traceability;
    }
    #Requirement requirement <'PRD-IAC-038'> iac038 {
        doc /* dsml check-output --infrastructure must run tofu fmt -check, tofu validate (after tofu init -backend=false) and tflint with the AWS rule set on each root module. */
        :>> title = "HCL checks"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-IAC-039'> iac039 {
        doc /* The toolchain CI must also run terraform validate on the golden output of each reference model. */
        :>> title = "Terraform check"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-040'> iac040 {
        doc /* An IaC security scan of the golden output must find no finding with high or critical severity. The version baseline gives the scanner. */
        :>> title = "Security scan"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::draft;
        frame correctModel;
    }
    #Requirement requirement <'PRD-IAC-041'> iac041 {
        doc /* After an apply, a second tofu plan with the same model and the same commit must show no change. */
        :>> title = "Stable plan"; :>> kind = RequirementKind::constraint; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
    #Requirement requirement <'PRD-IAC-042'> iac042 {
        doc /* Container service: the ECS service must ignore changes to its task definition, because the pipeline sets it after the migrations. The service must use the ECS deployment circuit breaker with rollback. */
        :>> title = "Service rollout control"; :>> kind = RequirementKind::functional; :>> priority = Priority::must; :>> status = Status::draft;
        frame deterministicGeneration;
    }
}
