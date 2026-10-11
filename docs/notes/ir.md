# IR 1.0.0: structure and version rules

Story #28 added the IR models, the JSON Schema of the IR and the canonical JSON writer. This document gives the structure of the IR, the order of its lists and the rules for its version.

- Models: `src/dsml/ir/model.py`.
- JSON Schema: `src/dsml/ir/ir.schema.json` (package data, PRD-CORE-022).
- Writer: `src/dsml/ir/writer.py`.
- Tests: `tests/test_ir.py`.

The conversion of a model into the IR and the command `dsml ir` are not in this story. The next M2 stories add them.

## Summary

- The IR is JSON. Each IR model is a frozen Python data class. The JSON Schema uses JSON Schema draft 2020-12.
- The field `irVersion` gives the semantic version of the IR. The first version is `1.0.0` (PRD-CORE-023).
- The writer gives the same bytes for the same IR on each platform (PRD-CORE-028). The order of the input lists does not change the output (PRD-CORE-031, PRD-CORE-032).
- The `dsml.ir` package does not import OpenSysML. The writer accepts only IR models, texts, numbers, Boolean values and null. Thus the IR holds no OpenSysML type, object or internal ID (PRD-CORE-025).
- A test makes sure that the schema and the models agree: the keys, the required keys and the values of each enumeration.

## Structure

The root object has six keys.

| Key | Content |
| --- | --- |
| `irVersion` | The semantic version of the IR, for example `"1.0.0"`. |
| `files` | The model files, relative to the repository root. |
| `elements` | The elements of the five layers (PRD-CORE-024). |
| `links` | The trace links (PRD-TRACE-003). |
| `constraintResults` | The results of the formal constraints for each environment (PRD-CORE-054). |
| `findings` | The findings of the adapter, for example the SYN findings (PRD-CORE-021). |

Each object has all the keys of its schema definition. A key with no value has the value `null` or an empty list. The schema does not permit other keys.

### Element

| Key | Content |
| --- | --- |
| `identity` | The short name of the element, or its qualified name if it has no short name (PRD-DSML-053). Other objects refer to an element with its identity. |
| `kind` | The kind of the element. See "Element kinds". |
| `name`, `qualifiedName`, `shortName` | The declared name, the qualified name and the short name (or `null`). |
| `owner` | The identity of the element that contains this element, or `null`. |
| `doc` | The text of the `doc` comment, or `null`. Needs and requirements keep their text here. |
| `multiplicity` | `{"lower": 0, "upper": null}` for `[*]`, or `null`. |
| `direction` | `in`, `out` or `inout` for a parameter, else `null`. |
| `types` | The identities of the definitions that type the element, or that it specializes or subsets. |
| `attributes` | The values of the DSML attributes, for example `priority`. |
| `annotations` | The metadata usages on the element, for example `Key`, `Waiver` or `FieldRules`, each with its attributes. |
| `location` | The file, the line and the column of the element. Lines and columns start at 1. |

### Element kinds

Most kinds are the DSML keywords of element kinds, for example `Need`, `Entity` and `ContainerService`. These kinds are not keywords:

| Kind | Element |
| --- | --- |
| `Package` | A package of the model. |
| `Enumeration` | An enumeration definition that does not have the keyword `#Roles`. |
| `Field` | An attribute usage of an entity. |
| `Relation` | A reference usage of an entity, typed by an entity. |
| `Parameter` | An `in` or `out` parameter of an operation. |

### Values

An attribute value has the key `type`, which gives its form.

| `type` | Other keys | Example in the model |
| --- | --- | --- |
| `string` | `value` | `"Track orders"` |
| `integer` | `value` | `512` |
| `real` | `value` | `0.5` |
| `boolean` | `value` | `true` |
| `enum` | `enumeration` (qualified name), `literal` | `Priority::must` |
| `reference` | `target` (identity) | a feature that refers to an element |
| `list` | `items` (values) | `(CrudKind::create, CrudKind::read)` |

### Links

A link has a `type`, a `source`, a `target` and a `location`. The source and the target are element identities. The types are the link types of PRD-TRACE-001 (`stakeholder`, `frame`, `derivation`, `refinement`, `satisfy`, `allocate`, `realizes`, `verify`) and the dependencies `uses` (PRD-DSML-040) and `calls` (PRD-DSML-030).

### Constraint results

A constraint result gives the `requirement`, the `index` of the constraint in the requirement (from 1, in the order of the model), the `environment`, the `value` (`true`, `false` or `unknown`) and the `location` of the constraint. For an `unknown` value, `missingFeatures` gives the features that have no value.

### Findings

A finding gives the `rule` (for example `SYN-001`), the `severity`, the `message`, the `location` (or `null`) and the identity of its `element` (or `null`).

## Canonical JSON

The writer obeys these rules:

1. The keys of each object are in sorted order.
2. The writer sorts the lists of the IR. The table gives the sort key of each list. If two items have the same sort key, the writer sorts them by their canonical JSON text. Thus the order is always fully defined.
3. A list value of an attribute (`type` = `list`) keeps the order of the model, because the order is data. An example is the order of the views in a navigation list (PRD-DSML-032).
4. The text is UTF-8 with no byte order mark. The writer does not escape characters that are not ASCII.
5. The writer indents with two spaces and uses LF line ends. The text ends with one LF (PRD-CORE-034).
6. The writer does not accept NaN or an infinite real value.

| List | Sort key |
| --- | --- |
| `files`, `types`, `missingFeatures` | The text |
| `elements` | `identity`, then `name` |
| `attributes`, `annotations` | `name` |
| `links` | `source`, `type`, `target` |
| `constraintResults` | `requirement`, `index`, `environment` |
| `findings` | file, line, column, `rule`, `message` (PRD-VAL-007). A finding with no location comes first. |

The IR contains no timestamp, no random value, no user name and no host name. Each path is relative to the repository root and uses "/". The models and the schema refuse an absolute path, a drive letter, a backslash and a `..` segment (PRD-CORE-033).

## Version rules

The field `irVersion` has the form `<major>.<minor>.<patch>` (PRD-CORE-023). The schema has the same version in its `$id` (`urn:dsml:ir:<version>`) and in its `title`. A test makes sure that the three agree.

| Change | New version |
| --- | --- |
| Remove a key, rename a key, or change the meaning or the type of a key. | Major |
| Remove a value of an enumeration, for example an element kind. | Major |
| Change a sort key. | Major |
| Add a key, an element kind, a link type or a value form. | Minor |
| Correct a description in the schema, with no change to the data. | Patch |

A change of the IR version also changes the golden IR files (PRD-CORE-027). A minor or patch release of the toolchain must not change the IR of an unchanged model, except to fix a defect that its release notes name (PRD-CORE-037).
