# DSML library 1.1.0: design and results

Story #13 added the DSML library 1.0.0. Story #157 added the phase 2 keywords in version 1.1.0 (see "Version 1.1.0"). This document gives the design of the library, the results of the parse with OpenSysML 0.9.2 and the limits that the story found.

- Library source: `src/dsml/library/DSML.sysml`.
- Python access: `dsml.library.library_text()` and `dsml.library.library_document()`.
- Tests: `tests/test_dsml_library.py`. Test models: `tests/models/dsml/`.

## Summary

- OpenSysML 0.9.2 parses and resolves the library with no error and no warning (PRD-DSML-004).
- The library has 33 keywords, 8 enumerations and 4 attribute types. A test compares them with the lists of the stories #13 and #157.
- The wheel contains the library. A test builds the wheel and compares the packaged file with the source (PRD-DSML-006, PRD-CORE-048).
- The library has the version 1.1.0. `@DsmlVersion { major = 1; minor = 1; patch = 0; }` on the package `DSML` gives it, and `dsml.library.LIBRARY_VERSION` must agree (PRD-DSML-056).
- The Jupyter kernel of the OMG pilot implementation, release 2026-08 (`jupyter-sysml-kernel` 0.62.0), accepts the library with no error and no warning (PRD-DSML-005). The CI job "Pilot" of story #23 does this check (Q60). See "Results with the OMG pilot implementation".
- 7 keywords cannot specialize `SemanticMetadata`. Q59 changed PRD-DSML-009 for these keywords.

## Structure of the library

The package `DSML` is a `library package`. It contains:

1. The attribute types `Decimal` (specializes `Real`), `Date`, `DateTime` and `Uuid` (each specializes `String`).
2. The enumerations `Priority`, `Status`, `RequirementKind`, `Target`, `CrudKind`, `HttpMethod`, `VerificationMethod` and `ViewKind`.
3. The default HTTP method and path of each CRUD operation: the attribute `crudDefaults`, typed by `CrudDefault` (PRD-DSML-029). The values agree with the table in `docs/prd/03-application-generation/01-fastapi.md`. In a path, `{entities}` is the collection name and `{id}` is the key value.
4. The package `DSML::BaseTypes`. It holds the base types of the keywords: one definition and one abstract usage for each element kind, for example `concern def Need` and `abstract concern needs : Need [*]`. A project library can specialize these definitions (PRD-DSML-019).
5. The 33 metadata definitions (the keywords).

The definition in `BaseTypes` has the same name as its keyword, for example `DSML::BaseTypes::Need` and `DSML::Need`. A model does not refer to `BaseTypes` by name, except when it needs a feature chain (see "Limits").

## Two forms of keyword

| Form | Keywords | Reason |
| --- | --- | --- |
| Specializes `Metaobjects::SemanticMetadata`. The base type is an abstract usage in `BaseTypes`. | `Stakeholder`, `Need`, `Requirement`, `Application`, `Entity`, `Key`, `Exposed`, `Operation`, `Roles`, `View`, `Network`, `ContainerService`, `RelationalDatabase`, `UserDirectory`, `SecretStore`, `StaticSite`, `AwsVpc`, `AwsEcsService`, `AwsRdsPostgres`, `AwsCognito`, `AwsSecrets`, `AwsStaticSite`, `Environment`, `Override`, `ToolingAccount`, `Verification` | Element kinds. The base type gives the attributes to the element (PRD-DSML-009). |
| Plain metadata definition. | `Calls`, `Realizes`, `Uses` | These go on a dependency. OpenSysML 0.9.2 refuses semantic metadata on a dependency ("Cannot annotate Dependency", code `metadata-annotated-element`). |
| Plain metadata definition with attributes. | `Waiver`, `DsmlVersion`, `FieldRules`, `Destructive` | The attributes belong to the metadata usage, not to the annotated element. |

PRD-DSML-009 (changed by Q59) tells that only the keywords of element kinds specialize `SemanticMetadata`.

## Selected forms

The issue of story #13 tells the story to select the form of `#Override` and `@FieldRules`. Story #14 must put these forms in its change list (`docs/model/syntax-changes.md`).

| Item | Selected form | Reason |
| --- | --- | --- |
| `#Override` | Semantic metadata. The base type is `BaseTypes::overrides : AwsRealization [*]`. Use it on a part usage in an environment that subsets an AWS realization, for example `#Override part orderDbProd :> orderDbAws { :>> multiAz = true; }`. | This is the form of the example model. All AWS kinds specialize `AwsRealization`, so the base type agrees with each realization. |
| `@FieldRules` | Plain metadata with the optional attributes `minLength`, `maxLength`, `minValue`, `maxValue`, `pattern`, `unique`, `precision` and `scale` (PRD-DSML-025). Use it as a metadata usage in the body of the field, for example `attribute total : Decimal [1] { @FieldRules { minValue = 0; } }`. | This is the form of the example model. The rules belong to the metadata usage, not to the field value. |
| `#Exposed` | The base type is the occurrence usage `BaseTypes::exposures`, with no definition, because an exposed element is a part (an entity) or an action (an operation). It has `crud`, `allowedRoles` and `'public'` (default `false`). Story #27 removed the occurrence definition `BaseTypes::Exposed`: the pilot implementation does not accept an action usage with a type that is not an action definition. | One keyword for both element kinds, as in the example model. |
| `#Roles` | The base type is the attribute definition `BaseTypes::Roles`. The roles enumeration of the model specializes it. `allowedRoles` has the type `Roles`. | `allowedRoles` gets a type, although the roles enumeration is in the model. |
| `#Destructive` | Plain metadata with the optional attribute `renamedFrom`. Use `#Destructive` on the entity or field, or `@Destructive { renamedFrom = "old"; }` in its body. | PRD-DSML-034. |
| `#Waiver` | Plain metadata with `rule`, `reason`, `owner` and the optional `expires` (a `Date`). Use `@Waiver { ... }` in the body of the element. | PRD-DSML-055. |
| `@DsmlVersion` | Plain metadata with `major`, `minor` and the optional `patch`. | PRD-DSML-056. The library gives the patch version. A model gives only `major` and `minor`. |
| AWS attributes | Only the attributes of PRD-DSML-042: `natGatewayCount` (`AwsVpc`); `cpu`, `memory`, `desiredCount`, `minCount`, `maxCount` (`AwsEcsService`); `instanceClass`, `multiAz` (`AwsRdsPostgres`). Each attribute has the multiplicity `[0..1]` and no value in the library. | The generators give the default values. A later minor version can add attributes. |

## Version 1.1.0

Story #157 added the phase 2 keywords. Version 1.1.0 is a minor version: it only adds definitions and one optional reference, so a valid model of version 1.0 stays valid (PRD-DSML-057). Rule STR-001 accepts the minor versions 0 and 1, because it takes the highest minor version from `LIBRARY_VERSION`.

| Item | Definition in the library | Requirements |
| --- | --- | --- |
| `ViewKind` | `enum def ViewKind { list; detail; form; }` | PRD-DSML-031 |
| `#View` | Semantic metadata. The base type is `BaseTypes::views : View [*]`. `View` has `kind : ViewKind`, the reference `entity : Entity [0..1]`, the reference `operation : Operation [0..1]`, `allowedRoles : Roles [0..*]` and `'public' : Boolean` (default `false`). | PRD-DSML-031, PRD-DSML-033 |
| Navigation | `Application` has the reference `navigation : View [0..*] ordered`. A phase 1 model does not give it. | PRD-DSML-032 |
| `#StaticSite` | Semantic metadata. The base type is `BaseTypes::staticSites : StaticSite [*]`. `StaticSite` specializes `LogicalElement`. | PRD-DSML-035, PRD-DSML-039, PRD-DSML-040 |
| `#AwsStaticSite` | Semantic metadata. The base type is `BaseTypes::awsStaticSites : AwsStaticSite [*]`, which subsets `awsRealizations`. `AwsStaticSite` specializes `AwsRealization` and has no attribute. | PRD-DSML-037, PRD-DSML-038 |

`#Uses` already permits a static site as its client (PRD-DSML-040). A model gives the entity of a view and the operation of a form view as the type of the reference, for example `ref :>> entity : Order;`. `docs/model/syntax-changes.md` ("Forms of the phase 2 keywords") gives each form and its reason.

PRD-IAC-021 gives the resources of the static site module: an S3 bucket, a CloudFront distribution, an ACM certificate and a Route 53 alias. The domain comes from the environment. No resource needs an attribute in the model, and PRD-DSML-042 gives no environment attribute for a static site. Thus `#AwsStaticSite` has no attribute.

Results:

- OpenSysML 0.9.2 parses and resolves the library 1.1.0 with no diagnostic.
- The test model `tests/models/dsml/phase-2.sysml` has a list view, a detail view, a form view, a navigation list and a static site. OpenSysML parses and resolves it with no diagnostic. The tests evaluate the kind, the entity, the operation, `'public'` and the order of the navigation.
- The pilot kernel accepts the library 1.1.0, `phase-2.sysml`, the example model and the PRD model. The CI job "Pilot" now also checks `phase-2.sysml`.
- The IR adapter does not read the new keywords yet. Story #159 adds them to the IR.

## SysML keywords as names

Some names of the PRD are SysML keywords. The library writes them as unrestricted names, with single quotes:

| Name | Where | Form in a model |
| --- | --- | --- |
| `interface`, `constraint` | Literals of `RequirementKind` | `RequirementKind::'constraint'` and `RequirementKind::'interface'`. The quotes are necessary after `::` (story #27). |
| `analysis` | Literal of `VerificationMethod` | `VerificationMethod::'analysis'`. The quotes are necessary after `::` (story #27). |
| `public` | Attribute of `#Exposed` and `#View` (PRD-DSML-033) | `:>> 'public' = true;` needs the quotes. |

## Results with the example model and the PRD model

These results are input for the stories #14 and #15. The files did not change in story #13.

- The PRD model (`docs/model/prd/*.sysml`) parses and resolves together with the library with no diagnostic.
- The example model (`docs/model/examples/order-service.sysml`) gives 1 error with the library: `String` does not resolve, because the model does not import `ScalarValues`. With `private import ScalarValues::*;`, it gives 2 errors with the code `feature-value-overriding`: `desiredCount` and `multiAz` use `=` on the AWS realization, and the `prod` environment changes them. These lines must use `default =` (see `docs/notes/opensysml-0.9.2.md`). Story #14 made these changes. Now the example model parses and resolves with no diagnostic. See `docs/model/syntax-changes.md`.
- The test model `tests/models/dsml/keywords.sysml` uses each keyword. It parses and resolves with no diagnostic.

## Results with the OMG pilot implementation

Story #23 added this check (Q60). The pilot implementation has no command-line parser, thus the check uses its Jupyter kernel with no graphical interface.

- Script: `scripts/check_pilot.py`. Workflow: `.github/workflows/pilot.yml`. Tests of the script: `tests/test_check_pilot.py`.
- Pin: the items `pilot-kernel`, `pilot-kernel-release` and `pilot-kernel-sha256` in `src/dsml/versions.toml`. The script downloads `jupyter-sysml-kernel-0.62.0.zip` from the release 2026-08 of `SysML-v2-Pilot-Implementation` on GitHub. It stops if the SHA-256 hash is not the pinned hash.
- The hash is the hash in the conda-forge recipe of `jupyter-sysml-kernel` 0.62.0. The conda-forge build checks the same release archive.
- The script sends each file to a new kernel as one cell. The kernel writes each diagnostic to stderr as a line that starts with `ERROR:` or `WARNING:`. An error line, an error message or a reply status that is not `ok` rejects the file.
- The script does not set the API base path of the kernel. Thus the kernel does not connect to a model repository.

Results:

1. The kernel accepts `src/dsml/library/DSML.sysml` with no diagnostic. The library did not change.
2. The kernel rejects the test model `tests/models/pilot/rejected.sysml` (an unresolved type). The CI job makes sure that the check fails for this file.

A result for the stories #14 and #15: the pilot kernel does not accept a SysML keyword after `::`, for example `RequirementKind::constraint`. OpenSysML 0.9.2 accepts it. Both tools accept the form with quotes, `RequirementKind::'constraint'`.

Story #27 changed the models to the form with quotes and added a pilot check of the models to the CI job. The script option `--one-model` sends the library and the model files to the kernel as one cell. The pilot kernel found two more items:

1. **A concern with a stakeholder must declare its subject first.** The pilot kernel gives "Subject must be first parameter" for a concern with a `stakeholder` and no `subject`. A stakeholder is a parameter, thus the subject must come before it. The kernel also gives the error on each requirement that frames the concern. A `subject` in the library definition `Need` does not remove the error. Thus each need with a stakeholder declares `subject;` before its first stakeholder.
2. **An action usage must be typed only by action definitions.** The base type of `#Exposed` was typed by the occurrence definition `BaseTypes::Exposed`. Thus `#Exposed action cancelOrder : CancelOrder` had a type that is not an action definition. Story #27 removed the definition. Now the base type `exposures` is an occurrence usage that holds the attributes itself.

Now the pilot kernel accepts the example model, the PRD model, `tests/models/dsml/keywords.sysml`, `tests/models/dsml/typed-usage.sysml` and `tests/models/dsml/phase-2.sysml` (story #157), each with the library.

## Limits of OpenSysML 0.9.2

1. **No semantic metadata on a dependency.** See "Two forms of keyword".
2. **`istype` does not see the base type of a typed usage.** A usage with a declared type and a keyword, for example `#Application part shop : Store`, gets the features of the base type: `shop.target` resolves. But `shop istype DSML::BaseTypes::Application` gives `false` (test model `typed-usage.sysml`). A usage with only a keyword, for example `#RelationalDatabase part orderDb`, gives `true`. Thus the IR adapter must find the kind of an element with `@` (the metadata), not with `istype`. A test examines this limit. If a new OpenSysML version removes the limit, the test fails.
3. **No type check of attribute values.** OpenSysML accepts `:>> priority = Status::draft;` and `:>> target = "fastapi";` with no diagnostic. The validator must check the types of the attribute values from the IR. An attribute name that the base type does not have gives the error `unresolved reference` (test model `unknown-attribute.sysml`).
4. **No check of the element kind.** OpenSysML accepts a keyword on the wrong kind of element, for example `#Entity attribute x;`. The validator must check the element kind of each keyword.
5. **No check of the metadata attributes.** OpenSysML accepts `@Waiver { rule = "COV-003"; }` with no `reason` and no `owner`. The validator must check them.
6. **A verification usage cannot be evaluated.** `orderTest istype DSML::BaseTypes::Verification` gives an evaluation error ("calc usage orderTest computes output features"). The keyword and its attributes resolve.
