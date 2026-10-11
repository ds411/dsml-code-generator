# Changes to the sketch syntax

The SysML syntax in the PRDs was a sketch. Nobody had parsed it with OpenSysML. This list gives each change to the sketch that makes a model parse and resolve with OpenSysML 0.9.2 and the DSML library 1.0.0. No change in this list changes a PRD requirement.

- Example model: `docs/model/examples/order-service.sysml`. The DSML PRD (`docs/prd/01-dsml-prd.md`, "Example model") contains a copy. A test makes sure that the two agree.
- Test: `tests/test_example_model.py`.
- PRD model: `docs/model/prd/*.sysml`. Test: `tests/test_prd_model.py`.
- The limits of OpenSysML 0.9.2 that cause the changes: `docs/notes/opensysml-0.9.2.md` and `docs/notes/dsml-library.md`.

## Changes to the example model (story #14)

| No. | Before | After | Reason |
| --- | --- | --- | --- |
| 1 | The model imports only `DSML::*`. | The model also has `private import ScalarValues::*;`. | The field `note` has the type `String`. `String` is in the standard library package `ScalarValues`, not in `DSML`. Without the import, OpenSysML gives `unresolved reference: String` (code `unresolved`). PRD-DSML-008 tells how a model refers to the DSML library. It does not prevent other imports. |
| 2 | `:>> desiredCount = 1;` on `apiServiceAws`. | `:>> desiredCount default = 1;` | In OpenSysML 0.9.2, a value written with `=` is fixed. The `prod` environment changes `desiredCount` to 3. With `=`, OpenSysML gives the error code `feature-value-overriding`. |
| 3 | `:>> multiAz = false;` on `orderDbAws`. | `:>> multiAz default = false;` | The `prod` environment changes `multiAz` to `true`. The reason is the same as for change 2. |
| 4 | `:>> cpu = 512; :>> memory = 1024;` on `apiServiceAws`, and `:>> instanceClass = "db.t4g.micro";` on `orderDbAws`. | `default =` on each of these values. | The example model does not change these values in an environment, so OpenSysML accepts `=`. But PRD-DSML-042 lets an environment change them. With `default =`, an environment can change each attribute of PRD-DSML-042, and the example shows one rule for all of them. |

### Rule for models

On an AWS realization, write each attribute of PRD-DSML-042 with `default =`. Then an `#Override` in an environment can change it. Use `=` for a value that an environment must not change.

## Forms that the DSML library selected (story #13)

The sketch did not give the full form of these items. Story #13 selected each form in the library. The example model already used these forms, so the example model did not change. See "Selected forms" in `docs/notes/dsml-library.md`.

| Item | Form | Reason |
| --- | --- | --- |
| `#Override` | Semantic metadata on a part usage in an environment. The part subsets an AWS realization, for example `#Override part orderDbProd :> orderDbAws { :>> multiAz = true; }`. | This is the form of the sketch. The subset gives the type of the realization to the part, so the chain `prod.orderDbProd.multiAz` resolves. |
| `@FieldRules` | Plain metadata with attributes, as a metadata usage in the body of the field, for example `attribute total : Decimal [1] { @FieldRules { minValue = 0; } }`. | This is the form of the sketch. The rules belong to the metadata usage, not to the field. |
| `#Calls`, `#Realizes`, `#Uses` | Plain metadata, not semantic metadata. The sketch form `#Uses dependency from a to b;` does not change. | OpenSysML 0.9.2 does not accept semantic metadata on a dependency (Q59, PRD-DSML-009). |
| `@DsmlVersion`, `@Waiver`, `@FieldRules`, `#Destructive` | Plain metadata with attributes. Write the attributes in a metadata usage, for example `@DsmlVersion { major = 1; minor = 0; }`. | The attributes belong to the metadata usage, not to the annotated element (Q59). |
| `'public'` | The attribute `public` of `#Exposed` needs single quotes: `:>> 'public' = true;`. | `public` is a SysML keyword. |

## PRD model (story #15)

The PRD model needed no change to the sketch syntax. It parses and resolves with the library with no diagnostic.

Story #15 changed the `doc` text of 15 requirements: PRD-APP-110, PRD-APP-121, PRD-APP-210, PRD-APP-222, PRD-CICD-001, PRD-CORE-001, PRD-CORE-039, PRD-DSML-035, PRD-IAC-001, PRD-IAC-007, PRD-IAC-015, PRD-IAC-033, PRD-TRACE-009, PRD-TRACE-013 and PRD-VAL-015. Before the change, the model text was different from the text in `docs/index/requirements.csv`. The PRD text is correct, so the model now has the CSV text without code formatting. These changes are not syntax changes.

After this, Q61 (decision record 06) changed the text of 9 of these requirements in the PRDs, the CSV index and the model. A requirement now refers to a table by the name of its PRD section, not with the words "above" or "below".

## Changes for the OMG pilot implementation (story #27)

The CI job "Pilot" sends the example model and the PRD model, each with the library, to the pilot kernel (PRD-DSML-005, Q60). These changes make the pilot kernel accept the models. OpenSysML 0.9.2 accepts the models before and after each change. See "Results with the OMG pilot implementation" in `docs/notes/dsml-library.md`.

| No. | Before | After | Where | Reason |
| --- | --- | --- | --- | --- |
| 5 | `RequirementKind::constraint` | `RequirementKind::'constraint'` | Example model (1), PRD model (76), `tests/models/dsml/keywords.sysml` (1), example model in the DSML PRD (1) | `constraint` is a SysML keyword. The pilot kernel does not accept a keyword after `::`. |
| 6 | `RequirementKind::interface` | `RequirementKind::'interface'` | PRD model (29) | `interface` is a SysML keyword. The reason is the same as for change 5. |
| 7 | A need with a stakeholder has no subject, for example `#Need concern <'N-001'> trackOrders { ... stakeholder owner : ShopOwner; }`. | `subject;` before the first stakeholder. | Example model (1), PRD model (5), `tests/models/dsml/keywords.sysml` (1), example model in the DSML PRD (1) | A stakeholder is a parameter. The pilot kernel gives "Subject must be first parameter" if a concern has a stakeholder and no subject before it. |

The enumeration literals of the DSML library that are SysML keywords are `RequirementKind::'interface'`, `RequirementKind::'constraint'` and `VerificationMethod::'analysis'`. No model uses `VerificationMethod::'analysis'` at this time. The other literals of the library are not SysML keywords.

### Rule for models

Write an enumeration literal that is a SysML keyword with single quotes, also after `::`. In a need with a stakeholder, declare `subject;` before the first stakeholder.

### Change to the library

Story #27 also changed the base type of `#Exposed`. This is not a change to the sketch syntax. A model writes `#Exposed` as before. The pilot kernel does not accept an action usage with a type that is not an action definition. The base type `BaseTypes::exposures` was typed by the occurrence definition `BaseTypes::Exposed`, thus `#Exposed action cancelOrder : CancelOrder` had such a type. Now `exposures` is an occurrence usage with no definition, and it holds the attributes `crud`, `allowedRoles` and `'public'`.

## Items for later stories

- A feature chain does not use the type that a keyword gives (`docs/notes/opensysml-0.9.2.md`, limit 1). The chain `prod.orderDbProd.multiAz` of the example model resolves, because `orderDbProd` redefines `multiAz` in its body. A chain to an attribute that the part does not redefine needs an explicit type or subset on the part, for example `:> databases`.
