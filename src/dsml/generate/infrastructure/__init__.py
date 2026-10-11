"""The infrastructure generator: OpenTofu and Terraform code from the infrastructure layer.

- `dsml.generate.infrastructure.generator`: the generator of the root modules.
- `dsml.generate.infrastructure.names`: the HCL addresses, AWS names, tag
  values and CI role names that all infrastructure and pipeline code uses.
- `dsml.generate.infrastructure.accounts`: the tooling root module and the
  bootstrap root module of each AWS account.
- `dsml.generate.infrastructure.policies`: the IAM policies of the CI roles
  and of the ECR repositories.
- `dsml.generate.infrastructure.hcl`: HCL string literals and the symbols of
  HCL blocks.
"""
