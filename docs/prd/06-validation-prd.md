# Validation PRD: rules and findings

Status date: 10 October 2026

## Summary

Validation examines the IR with a catalog of rules before code generation starts. Each rule is Python code with an ID, a severity, a message and a fix hint. An error finding stops code generation.

- **Phase:** 1.
- **Goals covered:** N-003 (correct model) and N-004 (traceability, through the coverage rules).
- **Prefix:** PRD-VAL. Rule IDs have their own form: `<CATEGORY>-<NNN>`, for example `COV-003`.
- **Related PRDs:** the toolchain core PRD runs validation in `dsml validate` and `dsml generate`. The DSML PRD gives the model structure that the rules check.

## Rule engine, severities and output formats

The validator runs all enabled rules on the IR and writes the findings in a fixed order. Three formats serve people, scripts and code review tools.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-VAL-001 | Each rule must be Python code that reads only the IR. Each rule must have an ID, a category, a default severity, a message and a fix hint. | Test | Q26 |
| PRD-VAL-002 | Rule IDs must have the form `<CATEGORY>-<NNN>`. A deleted rule ID must not be used again. | Inspection | Q26 |
| PRD-VAL-003 | The severities must be `error`, `warning` and `info`. A finding with the severity `error` must stop code generation. | Test | Q28 |
| PRD-VAL-004 | The configuration file can increase the severity of a rule, or turn off a rule with the default severity `warning` or `info`. It must not decrease the severity of a rule with the default severity `error` or turn it off. | Test | Q28 |
| PRD-VAL-005 | The option `--fail-on warning` must make `dsml validate` stop with exit code 1 if there is a warning. | Test | Q28 |
| PRD-VAL-006 | The validator must write findings as text, as JSON, or as SARIF 2.1.0 with the rule metadata and the source locations. | Test | Q28 |
| PRD-VAL-007 | The validator must sort findings by file, line, column and rule ID. | Test | Q16 |
| PRD-VAL-008 | The toolchain CI must have, for each rule, one model that the rule accepts and one model that the rule rejects. | Test | Q26 |

## Waivers, baselines, formal constraints and text rules

A waiver stops one rule for one element and stays visible in the report. Identity rules compare the model with a Git baseline. OpenSysML evaluates formal constraints. The STE text rules are optional.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-VAL-009 | A `#Waiver` must stop the findings of its rule on its element only. The report must list waived findings in a separate group, and SARIF must give them as suppressions with the reason. | Test | Q28 |
| PRD-VAL-010 | After the `expires` date of a waiver, its findings must come back, and the validator must report rule `STR-014`. | Test | Q28 |
| PRD-VAL-011 | The identity rules (category IDN) must run only when the user gives `--baseline <git-ref>` or the configuration file gives a default baseline. The validator must read the baseline model from the local Git repository. | Test | Q10, Q54 |
| PRD-VAL-012 | The validator must evaluate each formal constraint of a requirement through the OpenSysML adapter, one time for each environment, with the attribute values of that environment. | Test | Q12 |
| PRD-VAL-013 | The text rules (category TXT) must be off by default. The configuration file must be able to turn them on. | Test | Q3 |
| PRD-VAL-014 | The text rules must use the project dictionary of the top-level PRD as a list of additional approved words. The toolchain must not claim full STE compliance. | Inspection | Q2, Q3 |

## Rule catalog for phase 1

The catalog has 45 rules in eight categories. Each rule reports a finding when the condition in the table is true.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-VAL-015 | The validator must contain each rule in the catalog below, with its default severity. | Test | Q27 |

| Rule | Severity | The rule reports a finding when |
| --- | --- | --- |
| SYN-001 | error | OpenSysML reports a syntax error or a name that it cannot resolve. |
| SYN-002 | warning | OpenSysML reports a warning. |
| STR-001 | error | The model has no `#DsmlVersion`, or a DSML version that the toolchain does not support. |
| STR-002 | error | A need, requirement or verification has no value for a mandatory attribute. |
| STR-003 | error | A short name does not agree with the ID pattern of its kind. |
| STR-004 | error | Two elements have the same short name. |
| STR-005 | error | An application has no target, or a target that the toolchain does not know. |
| STR-006 | error | An entity has no `#Key` field, or more than one. |
| STR-007 | error | A field type is not a supported type. |
| STR-008 | error | A custom operation has no HTTP method or no path. |
| STR-009 | error | Two operations of one application have the same method and path. |
| STR-010 | error | An exposed entity, operation or view has no `allowedRoles` and is not public. |
| STR-011 | error | The environments `dev`, `staging` or `prod` are missing, or an environment has no account ID, Region or domain. |
| STR-012 | error | An environment changes an attribute that is not on the list of PRD-DSML-042. |
| STR-013 | error | The model drops or renames a table or a column, compared with the schema snapshot, with no `#Destructive` metadata. |
| STR-014 | warning | A waiver is after its `expires` date. |
| STR-015 | error | A waiver has no reason or no owner, or names a rule that does not exist. |
| STR-016 | error | A logical infrastructure element has an AWS attribute. |
| COV-001 | warning | No requirement frames a need. |
| COV-002 | warning | A requirement frames no need and is not derived from a different requirement. |
| COV-003 | warning | A requirement with the status `approved` or later has no satisfying element. |
| COV-004 | warning | A requirement with the status `approved` or later has no verification. |
| COV-005 | error | A requirement has the status `verified` but no verification. |
| COV-006 | warning | A verification with the method `test` refers to a test file that does not exist. |
| COV-007 | info | A stakeholder has no need. |
| XLY-001 | error | An application is not allocated to a logical element. |
| XLY-002 | error | An application is allocated to a logical element of the wrong kind. |
| XLY-003 | error | A logical element has no AWS realization, or more than one. |
| XLY-004 | error | A `react` application uses a database. |
| XLY-005 | error | A `react` application has no `#Calls` dependency and no imported OpenAPI file. |
| XLY-006 | error | An application exposes entities, but its container service uses no database. |
| XLY-007 | error | An application has protected operations or views, but its service or site uses no user directory. |
| AWS-001 | error | An account ID does not have 12 digits, two environments use one account, or an environment uses the tooling account. |
| AWS-002 | error | A Region is not on the list of permitted Regions in the configuration file. |
| AWS-003 | error | The `cpu` and `memory` of a Fargate service are not a valid pair. |
| AWS-004 | warning | The prod database has `multiAz = false`. |
| AWS-005 | warning | A prod container service has `minCount` less than 2. |
| FCN-001 | error | A formal constraint is false for an environment. |
| FCN-002 | warning | The validator cannot evaluate a formal constraint, because a feature has no value. |
| IDN-001 | error | A short name that the baseline used for an element of a different kind is used again. |
| IDN-002 | info | An element with a short name has a different qualified name from the baseline. |
| IDN-003 | warning | An element with no short name has a different qualified name from the baseline, so its trace identity changes. |
| TXT-001 | warning | A sentence in the text of a need or requirement has more than 25 words. |
| TXT-002 | warning | A requirement text uses "shall", "should", "may" or "will" in place of "must". |
| TXT-003 | warning | A requirement text has more than one "must", so it can contain more than one requirement. |
