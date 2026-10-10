# DSML library 1.0.0: design and results

Story #13 added the DSML library. This document gives the design of the library, the results of the parse with OpenSysML 0.9.2 and the limits that the story found.

- Library source: `src/dsml/library/DSML.sysml`.
- Python access: `dsml.library.library_text()` and `dsml.library.library_document()`.
- Tests: `tests/test_dsml_library.py`. Test models: `tests/models/dsml/`.

## Summary

- OpenSysML 0.9.2 parses and resolves the library with no error and no warning (PRD-DSML-004).
- The library has 30 keywords, 7 enumerations and 4 attribute types. A test compares them with the list of story #13.
- The wheel contains the library. A test builds the wheel and compares the packaged file with the source (PRD-DSML-006, PRD-CORE-048).
- The library has the version 1.0.0. `@DsmlVersion { major = 1; minor = 0; patch = 0; }` on the package `DSML` gives it, and `dsml.library.LIBRARY_VERSION` must agree (PRD-DSML-056).
- PRD-DSML-005 (the OMG pilot implementation accepts the library) is not checked yet. Story #23 adds a CI job for this check (Q60).
- 7 keywords cannot specialize `SemanticMetadata`. Q59 changed PRD-DSML-009 for these keywords.

## Structure of the library

The package `DSML` is a `library package`. It contains:

1. The attribute types `Decimal` (specializes `Real`), `Date`, `DateTime` and `Uuid` (each specializes `String`).
2. The enumerations `Priority`, `Status`, `RequirementKind`, `Target`, `CrudKind`, `HttpMethod` and `VerificationMethod`.
3. The default HTTP method and path of each CRUD operation: the attribute `crudDefaults`, typed by `CrudDefault` (PRD-DSML-029). The values agree with the table in `docs/prd/03-application-generation/01-fastapi.md`. In a path, `{entities}` is the collection name and `{id}` is the key value.
4. The package `DSML::BaseTypes`. It holds the base types of the keywords: one definition and one abstract usage for each element kind, for example `concern def Need` and `abstract concern needs : Need [*]`. A project library can specialize these definitions (PRD-DSML-019).
5. The 30 metadata definitions (the keywords).

The definition in `BaseTypes` has the same name as its keyword, for example `DSML::BaseTypes::Need` and `DSML::Need`. A model does not refer to `BaseTypes` by name, except when it needs a feature chain (see "Limits").

## Two forms of keyword

| Form | Keywords | Reason |
| --- | --- | --- |
| Specializes `Metaobjects::SemanticMetadata`. The base type is an abstract usage in `BaseTypes`. | `Stakeholder`, `Need`, `Requirement`, `Application`, `Entity`, `Key`, `Exposed`, `Operation`, `Roles`, `Network`, `ContainerService`, `RelationalDatabase`, `UserDirectory`, `SecretStore`, `AwsVpc`, `AwsEcsService`, `AwsRdsPostgres`, `AwsCognito`, `AwsSecrets`, `Environment`, `Override`, `ToolingAccount`, `Verification` | Element kinds. The base type gives the attributes to the element (PRD-DSML-009). |
| Plain metadata definition. | `Calls`, `Realizes`, `Uses` | These go on a dependency. OpenSysML 0.9.2 refuses semantic metadata on a dependency ("Cannot annotate Dependency", code `metadata-annotated-element`). |
| Plain metadata definition with attributes. | `Waiver`, `DsmlVersion`, `FieldRules`, `Destructive` | The attributes belong to the metadata usage, not to the annotated element. |

PRD-DSML-009 (changed by Q59) tells that only the keywords of element kinds specialize `SemanticMetadata`.

## Selected forms

The issue of story #13 tells the story to select the form of `#Override` and `@FieldRules`. Story #14 must put these forms in its change list (`docs/model/syntax-changes.md`).

| Item | Selected form | Reason |
| --- | --- | --- |
| `#Override` | Semantic metadata. The base type is `BaseTypes::overrides : AwsRealization [*]`. Use it on a part usage in an environment that subsets an AWS realization, for example `#Override part orderDbProd :> orderDbAws { :>> multiAz = true; }`. | This is the form of the example model. All AWS kinds specialize `AwsRealization`, so the base type agrees with each realization. |
| `@FieldRules` | Plain metadata with the optional attributes `minLength`, `maxLength`, `minValue`, `maxValue`, `pattern`, `unique`, `precision` and `scale` (PRD-DSML-025). Use it as a metadata usage in the body of the field, for example `attribute total : Decimal [1] { @FieldRules { minValue = 0; } }`. | This is the form of the example model. The rules belong to the metadata usage, not to the field value. |
| `#Exposed` | The base type is an occurrence (`BaseTypes::Exposed`), because an exposed element is a part (an entity) or an action (an operation). It has `crud`, `allowedRoles` and `'public'` (default `false`). | One keyword for both element kinds, as in the example model. |
| `#Roles` | The base type is the attribute definition `BaseTypes::Roles`. The roles enumeration of the model specializes it. `allowedRoles` has the type `Roles`. | `allowedRoles` gets a type, although the roles enumeration is in the model. |
| `#Destructive` | Plain metadata with the optional attribute `renamedFrom`. Use `#Destructive` on the entity or field, or `@Destructive { renamedFrom = "old"; }` in its body. | PRD-DSML-034. |
| `#Waiver` | Plain metadata with `rule`, `reason`, `owner` and the optional `expires` (a `Date`). Use `@Waiver { ... }` in the body of the element. | PRD-DSML-055. |
| `@DsmlVersion` | Plain metadata with `major`, `minor` and the optional `patch`. | PRD-DSML-056. The library gives the patch version. A model gives only `major` and `minor`. |
| AWS attributes | Only the attributes of PRD-DSML-042: `natGatewayCount` (`AwsVpc`); `cpu`, `memory`, `desiredCount`, `minCount`, `maxCount` (`AwsEcsService`); `instanceClass`, `multiAz` (`AwsRdsPostgres`). Each attribute has the multiplicity `[0..1]` and no value in the library. | The generators give the default values. A later minor version can add attributes. |

## SysML keywords as names

Some names of the PRD are SysML keywords. The library writes them as unrestricted names, with single quotes:

| Name | Where | Form in a model |
| --- | --- | --- |
| `interface`, `constraint` | Literals of `RequirementKind` | `RequirementKind::constraint` resolves with no quotes after `::`. |
| `analysis` | Literal of `VerificationMethod` | `VerificationMethod::analysis` resolves with no quotes after `::`. |
| `public` | Attribute of `#Exposed` (PRD-DSML-033) | `:>> 'public' = true;` needs the quotes. |

## Results with the example model and the PRD model

These results are input for the stories #14 and #15. The files did not change in story #13.

- The PRD model (`docs/model/prd/*.sysml`) parses and resolves together with the library with no diagnostic.
- The example model (`docs/model/examples/order-service.sysml`) gives 1 error with the library: `String` does not resolve, because the model does not import `ScalarValues`. With `private import ScalarValues::*;`, it gives 2 errors with the code `feature-value-overriding`: `desiredCount` and `multiAz` use `=` on the AWS realization, and the `prod` environment changes them. These lines must use `default =` (see `docs/notes/opensysml-0.9.2.md`).
- The test model `tests/models/dsml/keywords.sysml` uses each keyword. It parses and resolves with no diagnostic.

## Limits of OpenSysML 0.9.2

1. **No semantic metadata on a dependency.** See "Two forms of keyword".
2. **`istype` does not see the base type of a typed usage.** A usage with a declared type and a keyword, for example `#Exposed action cancelOrder : CancelOrder`, gets the features of the base type: `cancelOrder.'public'` evaluates to `false`. But `cancelOrder istype DSML::BaseTypes::Exposed` gives `false`. A usage with only a keyword, for example `#RelationalDatabase part orderDb`, gives `true`. Thus the IR adapter must find the kind of an element with `@` (the metadata), not with `istype`. A test examines this limit. If a new OpenSysML version removes the limit, the test fails.
3. **No type check of attribute values.** OpenSysML accepts `:>> priority = Status::draft;` and `:>> target = "fastapi";` with no diagnostic. The validator must check the types of the attribute values from the IR. An attribute name that the base type does not have gives the error `unresolved reference` (test model `unknown-attribute.sysml`).
4. **No check of the element kind.** OpenSysML accepts a keyword on the wrong kind of element, for example `#Entity attribute x;`. The validator must check the element kind of each keyword.
5. **No check of the metadata attributes.** OpenSysML accepts `@Waiver { rule = "COV-003"; }` with no `reason` and no `owner`. The validator must check them.
6. **A verification usage cannot be evaluated.** `orderTest istype DSML::BaseTypes::Verification` gives an evaluation error ("calc usage orderTest computes output features"). The keyword and its attributes resolve.
