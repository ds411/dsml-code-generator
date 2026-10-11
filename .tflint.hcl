# tflint settings for the check of the golden HCL in the toolchain CI
# (story #86). This is a hand-written file.
#
# trace: PRD-IAC-003
#
# The CI installs the AWS rule set of src/dsml/versions.toml in the plugin
# folder of tflint and checks its SHA-256 hash. The version here must agree
# with the version baseline.
plugin "aws" {
  enabled = true
  version = "0.49.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}
