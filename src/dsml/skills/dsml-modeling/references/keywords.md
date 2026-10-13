<!-- The module dsml.assist.reference writes this file from the installed toolchain. Do not change it. -->

# DSML keywords

This part gives the keywords of the DSML library, version 1.1.0.
A model imports the library with `private import DSML::*;`.

An element kind gives the kind of the element that it annotates, for example `#Need concern <'N-001'> firstNeed { ... }`. Give the attribute values of an element kind with redefinitions, for example `:>> priority = Priority::must;`.
An annotation adds data to an element, for example `@FieldRules { maxLength = 40; }` in the body of a field.
The multiplicity 1 tells that the attribute must have one value.

## Needs layer

### `Need`

A stakeholder need. Use it on a concern usage.

Form: element kind. Write `#Need` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `title` | `String` | 1 |  |
| `priority` | `Priority` | 1 |  |
| `status` | `Status` | 1 |  |

### `Stakeholder`

A stakeholder. Use it on a part definition.

Form: element kind. Write `#Stakeholder` before the declaration.

The keyword has no attributes.

## Requirements layer

### `Requirement`

A requirement. Use it on a requirement usage.

Form: element kind. Write `#Requirement` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `title` | `String` | 1 |  |
| `kind` | `RequirementKind` | 1 |  |
| `priority` | `Priority` | 1 |  |
| `status` | `Status` | 1 |  |
| `rationale` | `String` | 0..1 |  |
| `source` | `String` | 0..1 |  |
| `owner` | `String` | 0..1 |  |

## Application layer

### `Application`

An application. Use it on a part usage.

Form: element kind. Write `#Application` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `target` | `Target` | 1 |  |
| `navigation` | reference to `View` | 0..*, ordered |  |

### `Calls`

The application that the client of the dependency calls. Use it on a dependency.

Form: annotation. Write `#Calls` before the declaration.

The keyword has no attributes.

### `Destructive`

A destructive database change. Use it on an entity or on a field. For a rename, give the old name in renamedFrom.

Form: annotation. Write `#Destructive` before the declaration, or write `@Destructive { ... }` in the body of the element to give the attribute values.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `renamedFrom` | `String` | 0..1 |  |

### `Entity`

An entity. Use it on a part definition. Each attribute usage is a field.

Form: element kind. Write `#Entity` before the declaration.

The keyword has no attributes.

### `Exposed`

An entity or an operation that an application exposes. Use it on a part usage of an entity or on an action usage of an operation.

Form: element kind. Write `#Exposed` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `crud` | `CrudKind` | 0..* |  |
| `allowedRoles` | `Roles` | 0..* |  |
| `'public'` | `Boolean` | 1 | `false` |

### `ExternalApi`

Phase 2: an external API that an imported OpenAPI file gives. Use it on a part usage. Give the path of the file in openApiFile.

Form: element kind. Write `#ExternalApi` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `openApiFile` | `String` | 1 |  |

### `FieldRules`

The constraints of a field. Use it as a metadata usage in the body of the field. Give only the constraints that apply.

Form: annotation. Write `#FieldRules` before the declaration, or write `@FieldRules { ... }` in the body of the element to give the attribute values.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `minLength` | `Natural` | 0..1 |  |
| `maxLength` | `Natural` | 0..1 |  |
| `minValue` | `Real` | 0..1 |  |
| `maxValue` | `Real` | 0..1 |  |
| `pattern` | `String` | 0..1 |  |
| `unique` | `Boolean` | 0..1 |  |
| `precision` | `Positive` | 0..1 |  |
| `scale` | `Natural` | 0..1 |  |

### `Key`

The primary key field of an entity. Use it on an attribute usage.

Form: element kind. Write `#Key` before the declaration.

The keyword has no attributes.

### `Operation`

A custom operation. Use it on an action definition.

Form: element kind. Write `#Operation` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `method` | `HttpMethod` | 1 |  |
| `path` | `String` | 1 |  |

### `Roles`

The roles of the model. Use it on one enumeration definition.

Form: element kind. Write `#Roles` before the declaration.

The keyword has no attributes.

### `View`

Phase 2: a view of an application. Use it on a part usage in an application. Give the kind, and the entity or the operation.

Form: element kind. Write `#View` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `kind` | `ViewKind` | 1 |  |
| `entity` | reference to `Entity` | 0..1 |  |
| `operation` | reference to `Operation` | 0..1 |  |
| `allowedRoles` | `Roles` | 0..* |  |
| `'public'` | `Boolean` | 1 | `false` |

## Infrastructure layer

### `AwsCognito`

The AWS realization of a user directory. Use it on a part usage.

Form: element kind. Write `#AwsCognito` before the declaration.

The keyword has no attributes.

### `AwsEcsService`

The AWS realization of a container service. Use it on a part usage.

Form: element kind. Write `#AwsEcsService` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `cpu` | `Positive` | 0..1 |  |
| `memory` | `Positive` | 0..1 |  |
| `desiredCount` | `Natural` | 0..1 |  |
| `minCount` | `Natural` | 0..1 |  |
| `maxCount` | `Natural` | 0..1 |  |

### `AwsRdsPostgres`

The AWS realization of a relational database. Use it on a part usage.

Form: element kind. Write `#AwsRdsPostgres` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `instanceClass` | `String` | 0..1 |  |
| `multiAz` | `Boolean` | 0..1 |  |

### `AwsSecrets`

The AWS realization of a secret store. Use it on a part usage.

Form: element kind. Write `#AwsSecrets` before the declaration.

The keyword has no attributes.

### `AwsStaticSite`

Phase 2: the AWS realization of a static site. Use it on a part usage.

Form: element kind. Write `#AwsStaticSite` before the declaration.

The keyword has no attributes.

### `AwsVpc`

The AWS realization of a network. Use it on a part usage.

Form: element kind. Write `#AwsVpc` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `natGatewayCount` | `Natural` | 0..1 |  |

### `ContainerService`

A logical container service. Use it on a part usage.

Form: element kind. Write `#ContainerService` before the declaration.

The keyword has no attributes.

### `Environment`

A deployment environment. Use it on a part usage.

Form: element kind. Write `#Environment` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `accountId` | `String` | 1 |  |
| `region` | `String` | 1 |  |
| `domain` | `String` | 1 |  |

### `Network`

A logical network. Use it on a part usage.

Form: element kind. Write `#Network` before the declaration.

The keyword has no attributes.

### `Override`

A change of an AWS realization in one environment. Use it on a part usage in the environment that subsets the AWS realization.

Form: element kind. Write `#Override` before the declaration.

The keyword has no attributes.

### `Realizes`

The AWS realization of a logical element. Use it on a dependency from the AWS realization to the logical element.

Form: annotation. Write `#Realizes` before the declaration.

The keyword has no attributes.

### `RelationalDatabase`

A logical relational database. Use it on a part usage.

Form: element kind. Write `#RelationalDatabase` before the declaration.

The keyword has no attributes.

### `SecretStore`

A logical secret store. Use it on a part usage.

Form: element kind. Write `#SecretStore` before the declaration.

The keyword has no attributes.

### `StaticSite`

Phase 2: a logical static site. Use it on a part usage.

Form: element kind. Write `#StaticSite` before the declaration.

The keyword has no attributes.

### `ToolingAccount`

The AWS account and Region of the ECR repositories. Use it on a part usage.

Form: element kind. Write `#ToolingAccount` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `accountId` | `String` | 1 |  |
| `region` | `String` | 1 |  |

### `UserDirectory`

A logical user directory. Use it on a part usage.

Form: element kind. Write `#UserDirectory` before the declaration.

The keyword has no attributes.

### `Uses`

A database, user directory or secret store that a container service or a static site uses. Use it on a dependency.

Form: annotation. Write `#Uses` before the declaration.

The keyword has no attributes.

## Verification layer

### `Verification`

A verification. Use it on a verification usage.

Form: element kind. Write `#Verification` before the declaration.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `title` | `String` | 1 |  |
| `method` | `VerificationMethod` | 1 |  |
| `testFiles` | `String` | 0..* |  |
| `testCases` | `String` | 0..* |  |

## All layers

### `DsmlVersion`

The version of the DSML library. A model gives the major and the minor version on its root package. The library also gives the patch version.

Form: annotation. Write `#DsmlVersion` before the declaration, or write `@DsmlVersion { ... }` in the body of the element to give the attribute values.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `major` | `Natural` | 1 |  |
| `minor` | `Natural` | 1 |  |
| `patch` | `Natural` | 0..1 |  |

### `Waiver`

A waiver of one validation rule for the annotated element. The attribute expires is optional.

Form: annotation. Write `#Waiver` before the declaration, or write `@Waiver { ... }` in the body of the element to give the attribute values.

| Attribute | Type | Multiplicity | Default |
| --- | --- | --- | --- |
| `rule` | `String` | 1 |  |
| `reason` | `String` | 1 |  |
| `owner` | `String` | 1 |  |
| `expires` | `Date` | 0..1 |  |

## Enumerations

| Enumeration | Values |
| --- | --- |
| `CrudKind` | `create`, `read`, `update`, `delete`, `list` |
| `HttpMethod` | `get`, `post`, `put`, `patch`, `delete` |
| `Priority` | `must`, `should`, `could`, `wont` |
| `RequirementKind` | `functional`, `performance`, `security`, `'interface'`, `'constraint'` |
| `Status` | `draft`, `approved`, `implemented`, `verified`, `retired` |
| `Target` | `fastapi`, `react`, `nextjs` |
| `VerificationMethod` | `test`, `'analysis'`, `inspection`, `demonstration` |
| `ViewKind` | `list`, `detail`, `form` |

## Attribute types

| Type | Specializes | Description |
| --- | --- | --- |
| `Date` | `String` | A calendar date in the ISO 8601 form YYYY-MM-DD. |
| `DateTime` | `String` | A date and a time of day in the ISO 8601 form, with a time zone offset. |
| `Decimal` | `Real` | A decimal number. The FieldRules attributes precision and scale give its digits. |
| `Uuid` | `String` | A universally unique identifier (RFC 9562) in its text form. |
