# Decision record 04: formal constraints and the AWS test schedule

Status date: 10 October 2026

## Purpose and status

This record holds 2 questions, Q57 and Q58, that came up in the phase 1 plan. Q57 changes the PRDs, and the changed requirements give Q57 in the Source column. Q58 changes only the schedule of the AWS deployment tests. No requirement changes for Q58.

Status: closed. On 10 October 2026, the product owner accepted the two answers.

## T. Formal constraints and the IR

PRD-VAL-012 and PRD-CORE-026 did not agree. PRD-VAL-012 told the validator to evaluate formal constraints through the OpenSysML adapter. PRD-CORE-026 permits validators to read only the IR.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q57 | Which part evaluates the formal constraints of requirements? Options: (a) the IR adapter evaluates each constraint for each environment and writes the result into the IR; (b) the validator calls the adapter, as an exception to PRD-CORE-026; (c) the validator evaluates the constraints in Python from the IR. | (a). The validator does not need OpenSysML, and the IR holds all inputs of the validator. Option (b) breaks PRD-CORE-026. Option (c) needs a second expression evaluator. Changed requirements: PRD-CORE-026, PRD-VAL-012 and rule FCN-002. New requirement: PRD-CORE-054. | Decided |

## U. Phase 1 schedule

The product owner has no AWS account at this time.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q58 | When do the tests that deploy to AWS run? Options: (a) in phase 1, as the PRDs give; (b) later, when an AWS account is available. | (b). The phase 1 work continues with no AWS account. These items wait for an AWS account: the phase 1 exit criterion "deploys to the dev account", the sandbox deployment of PRD-CORE-053, and the second plan of PRD-IAC-041. Checks with no AWS access stay in phase 1, for example `tofu validate`, `terraform validate`, `tflint` and Checkov. An issue with the label `deferred` tracks the items that wait. | Decided |
