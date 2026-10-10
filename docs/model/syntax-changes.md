# Changes to the sketch syntax

The SysML syntax in the PRDs was a sketch. Nobody had parsed it with OpenSysML. This list gives each change to the sketch that makes a model parse and resolve with OpenSysML 0.9.2 and the DSML library 1.0.0. No change in this list changes a PRD requirement.

- Example model: `docs/model/examples/order-service.sysml`. The DSML PRD (`docs/prd/01-dsml-prd.md`, "Example model") contains a copy. A test makes sure that the two agree.
- Test: `tests/test_example_model.py`.
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

## Items for later stories

- The PRD model (`docs/model/prd/*.sysml`) parses and resolves with the library with no diagnostic. Story #15 adds its test. If story #15 changes the sketch syntax, it must add the changes to this list.
- A feature chain does not use the type that a keyword gives (`docs/notes/opensysml-0.9.2.md`, limit 1). The chain `prod.orderDbProd.multiAz` of the example model resolves, because `orderDbProd` redefines `multiAz` in its body. A chain to an attribute that the part does not redefine needs an explicit type or subset on the part, for example `:> databases`.
