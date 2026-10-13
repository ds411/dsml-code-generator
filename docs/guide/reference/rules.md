<!-- The script scripts/write_guide_reference.py writes this page from the installed toolchain. Do not change it. -->

[Reference](README.md) | [User guide](../README.md)

# DSML validation rules

This page gives the rules of the validation rule catalog, sorted by rule ID.
`dsml validate` gives a finding with the rule ID for each problem.
Do the correction of the rule, then run `dsml validate` again.
The table `[rules.severity]` of the configuration file can change the severity of a rule, for example `"COV-003" = "error"`.
The optional rule sets are: `TXT`.

## AWS

### `AWS-001`

- Severity: error
- Message: An account ID does not have 12 digits, two environments use one account, or an environment uses the tooling account.
- Correction: Give each environment its own AWS account. The ID of an account has 12 digits.

### `AWS-002`

- Severity: error
- Message: A Region is not on the list of permitted Regions in the configuration file.
- Correction: Use a Region from the key aws.regions, or add the Region to aws.regions.

### `AWS-003`

- Severity: error
- Message: The cpu and memory of a Fargate service are not a valid pair.
- Correction: Use a pair of cpu and memory that AWS Fargate accepts.

### `AWS-004`

- Severity: warning
- Message: The prod database has multiAz = false.
- Correction: Set multiAz = true for the database in the environment prod.

### `AWS-005`

- Severity: warning
- Message: A prod container service has minCount less than 2.
- Correction: Set minCount to 2 or more for the service in the environment prod.

## COV

### `COV-001`

- Severity: warning
- Message: No requirement frames a need.
- Correction: Add a requirement with `frame <need>;`, or remove the need.

### `COV-002`

- Severity: warning
- Message: A requirement frames no need and is not derived from a different requirement.
- Correction: Add `frame <need>;` to the requirement, or derive it from a different requirement.

### `COV-003`

- Severity: warning
- Message: A requirement with the status "approved" or later has no satisfying element.
- Correction: Add `satisfy <requirement> by <element>;` to the application layer.

### `COV-004`

- Severity: warning
- Message: A requirement with the status "approved" or later has no verification.
- Correction: Add a verification with `verify <requirement>;` in its objective.

### `COV-005`

- Severity: error
- Message: A requirement has the status "verified" but no verification.
- Correction: Add a verification with `verify <requirement>;` in its objective, or change the status.

### `COV-006`

- Severity: warning
- Message: A verification with the method "test" refers to a test file that does not exist.
- Correction: Correct the path in `testFiles`, or add the test file. The path is relative to the folder of the configuration file.

### `COV-007`

- Severity: info
- Message: A stakeholder has no need.
- Correction: Add a need with `stakeholder <name> : <stakeholder>;`, or remove the stakeholder.

## FCN

### `FCN-001`

- Severity: error
- Message: A formal constraint is false for an environment.
- Correction: Change the model so that the constraint is true in the environment, or correct the constraint.

### `FCN-002`

- Severity: warning
- Message: The adapter cannot evaluate a formal constraint for an environment, because a feature has no value.
- Correction: Give a value to each feature that the message names, in the AWS realization or in an override of the environment.

## IDN

### `IDN-001`

- Severity: error
- Message: A short name that the baseline used for an element of a different kind is used again.
- Correction: Give the element a new short name. Do not use a short name again for a different kind of element.

### `IDN-002`

- Severity: info
- Message: An element with a short name has a different qualified name from the baseline.
- Correction: No change is necessary. The short name keeps the identity of the element.

### `IDN-003`

- Severity: warning
- Message: An element with no short name has a different qualified name from the baseline, so its trace identity changes.
- Correction: Use the qualified name of the baseline again, or give the element a short name.

## STR

### `STR-001`

- Severity: error
- Message: The model has no #DsmlVersion, or a DSML version that the toolchain does not support.
- Correction: Put @DsmlVersion { major = 1; minor = 0; } on the root package. Use a major version and a minor version that the toolchain supports.

### `STR-002`

- Severity: error
- Message: A need, requirement or verification has no value for a mandatory attribute.
- Correction: Give a value for the attribute. docs/prd/01-dsml-prd.md gives the attributes.

### `STR-003`

- Severity: error
- Message: A short name does not agree with the ID pattern of its kind.
- Correction: Change the short name, or change the pattern in the keys ids.* of dsml.toml.

### `STR-004`

- Severity: error
- Message: Two elements have the same short name.
- Correction: Give each element a different short name. Do not use a deleted ID again.

### `STR-005`

- Severity: error
- Message: An application has no target, or a target that the toolchain does not know.
- Correction: Set the attribute target of the application to Target::fastapi, Target::react or Target::nextjs.

### `STR-006`

- Severity: error
- Message: An entity has no #Key field, or more than one.
- Correction: Put the #Key metadata on one field of the entity.

### `STR-007`

- Severity: error
- Message: A field type is not a supported type.
- Correction: Use String, Integer, Boolean, Real, Decimal, Date, DateTime, Uuid or an enumeration definition of the model as the field type.

### `STR-008`

- Severity: error
- Message: A custom operation has no HTTP method or no path.
- Correction: Set the attributes method and path of the operation, for example :>> method = HttpMethod::post; :>> path = "/orders/{orderId}/cancel";.

### `STR-009`

- Severity: error
- Message: Two operations of one application have the same method and path.
- Correction: Change the path or the method of one operation, or expose the operation in a different application.

### `STR-010`

- Severity: error
- Message: An exposed entity, operation or view has no allowedRoles and is not public.
- Correction: Give the roles that can use the element in the attribute allowedRoles, or set public = true.

### `STR-011`

- Severity: error
- Message: The environments dev, staging or prod are missing, or an environment has no account ID, Region or domain.
- Correction: Add the #Environment parts dev, staging and prod. Give each environment the attributes accountId, region and domain.

### `STR-012`

- Severity: error
- Message: An environment changes an attribute that is not on the list of PRD-DSML-042.
- Correction: Change only cpu, memory, instanceClass, desiredCount, minCount, maxCount, multiAz or natGatewayCount in an override. Put a different value in the AWS realization.

### `STR-013`

- Severity: error
- Message: The model drops or renames a table or a column, compared with the schema snapshot, with no #Destructive metadata.
- Correction: For a rename, add @Destructive { renamedFrom = "<old name>"; } to the entity or the field. For a dropped column, add #Destructive to the entity. For a dropped table, add #Destructive to the application.

### `STR-014`

- Severity: warning
- Message: A waiver is after its expires date.
- Correction: Correct the model, then remove the waiver. If the waiver must stay, give a new expires date.

### `STR-015`

- Severity: error
- Message: A waiver has no reason or no owner, or names a rule that does not exist.
- Correction: Give the waiver a rule ID of the catalog, a reason and an owner, for example @Waiver { rule = "COV-003"; reason = "..."; owner = "..."; }.

### `STR-016`

- Severity: error
- Message: A logical infrastructure element has an AWS attribute.
- Correction: Move the attribute to the AWS realization of the logical element.

### `STR-017`

- Severity: error
- Message: An imported OpenAPI file does not exist, or it contains an item that the toolchain cannot read.
- Correction: Correct the path in openApiFile. Use only the OpenAPI subset of docs/notes/openapi-import.md in the file.

## SYN

### `SYN-001`

- Severity: error
- Message: OpenSysML reports a syntax error or a name that it cannot resolve.
- Correction: Correct the SysML v2 text or the name at the location of the finding.

### `SYN-002`

- Severity: warning
- Message: OpenSysML reports a warning.
- Correction: Correct the model at the location of the finding. Then OpenSysML gives no warning.

## TXT

### `TXT-001`

- Severity: warning
- Message: A sentence in the text of a need or requirement has more than 25 words.
- Correction: Divide the sentence into sentences of 25 words or fewer.
- Rule set: TXT. This rule set is off by default. Turn it on with `optional = ["TXT"]` in the table `[rules]`.

### `TXT-002`

- Severity: warning
- Message: A requirement text uses "shall", "should", "may" or "will" in place of "must".
- Correction: Use "must" for an obligation. Use "can" for a possibility.
- Rule set: TXT. This rule set is off by default. Turn it on with `optional = ["TXT"]` in the table `[rules]`.

### `TXT-003`

- Severity: warning
- Message: A requirement text has more than one "must", so it can contain more than one requirement.
- Correction: Divide the text into requirements that each have one "must".
- Rule set: TXT. This rule set is off by default. Turn it on with `optional = ["TXT"]` in the table `[rules]`.

## XLY

### `XLY-001`

- Severity: error
- Message: An application is not allocated to a logical element.
- Correction: Allocate the application to one logical element with `allocate`.

### `XLY-002`

- Severity: error
- Message: An application is allocated to a logical element of the wrong kind.
- Correction: Allocate a `fastapi` or `nextjs` application to a `#ContainerService`. Allocate a `react` application to a `#StaticSite`.

### `XLY-003`

- Severity: error
- Message: A logical element has no AWS realization, or more than one.
- Correction: Add one part usage with the correct AWS kind and a `#Realizes` dependency from it to the logical element. Remove the other realizations.

### `XLY-004`

- Severity: error
- Message: A `react` application uses a database.
- Correction: Remove the `#Uses` dependency to the database. Let the `react` application call an API application with `#Calls`.

### `XLY-005`

- Severity: error
- Message: A `react` application has no `#Calls` dependency and no imported OpenAPI file.
- Correction: Add a `#Calls` dependency from the `react` application to the application or the `#ExternalApi` that it calls.

### `XLY-006`

- Severity: error
- Message: An application exposes entities, but its container service uses no database.
- Correction: Add a `#Uses` dependency from the container service to a `#RelationalDatabase`.

### `XLY-007`

- Severity: error
- Message: An application has protected operations or views, but its service or site uses no user directory.
- Correction: Add a `#Uses` dependency from the service or site to a `#UserDirectory`, or set `public = true` on each exposed element.
