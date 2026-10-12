# IR 1.1.0: structure and version rules

Story #28 added the IR models, the JSON Schema of the IR and the canonical JSON writer. Story #159 added the version 1.1.0 (see "Versions"). This document gives the structure of the IR, the order of its lists and the rules for its version.

- Models: `src/dsml/ir/model.py`.
- JSON Schema: `src/dsml/ir/ir.schema.json` (package data, PRD-CORE-022).
- Writer: `src/dsml/ir/writer.py`.
- Tests: `tests/test_ir.py`.

The conversion of a model into the IR and the command `dsml ir` are not in this story. Stories #30, #31 and #32 add the conversion. Story #33 adds `dsml ir` and the golden IR files (`tests/golden/ir/`). `docs/notes/ir-performance.md` gives the time to make the IR.

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
| `irVersion` | The semantic version of the IR, for example `"1.1.0"`. |
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

A constraint result gives the `requirement`, the `index` of the constraint in the requirement (from 1, in the order of the model), the `environment`, the `value` (`true`, `false` or `unknown`) and the `location` of the constraint. For an `unknown` value, `missingFeatures` gives the features that have no value. Story #32 added the evaluation. See `docs/notes/ir-constraints.md`.

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

A change of the IR version also changes the golden IR files (PRD-CORE-027).

### Versions

| Version | Story | Change |
| --- | --- | --- |
| 1.0.0 | #28 | The first version. |
| 1.1.0 | #159 | The element kinds `View`, `StaticSite` and `AwsStaticSite`. A view has the attributes `entity` or `operation`, and an application has the attribute `navigation` (`docs/notes/ir-solution-layers.md`). | A minor or patch release of the toolchain must not change the IR of an unchanged model, except to fix a defect that its release notes name (PRD-CORE-037).

## Conversion of the needs and requirements layers (story #30)

Story #30 added the conversion of the packages, the stakeholders, the needs, the requirements and their links into the IR.

- Entry point: `dsml.adapter.convert.build_ir(model, files)`. It gives an `Ir` with the elements, the links and the SYN findings.
- Reader of the model: `src/dsml/adapter/source.py`.
- Converter of the needs and requirements layers: `src/dsml/adapter/needs.py`.
- Tests: `tests/test_ir_needs.py`. Test models: `tests/models/ir/`.

### Source of the data

The adapter reads the model from the SysML v2 API JSON form (`Model.to_api_json()`). `Model.query()` and `Model.get_symbol()` of OpenSysML 0.9.2 do not give the source location of an element, and `Model.query()` does not give the metadata usages. The API JSON form gives:

- The line and the column of each element (`sysx:sourceLine`, `sysx:sourceColumn`). Only a root package gives its file (`sysx:sourceDocument`). The adapter finds the file of an element through its owners.
- The metadata usages of each element, with the qualified name of the metadata definition. This includes the definitions of the standard library, for example `RequirementDerivation::DerivationMetadata`.
- The values of the features, as literal expressions, references and the sequence operator ",".

The JSON form refers to elements with internal IDs of OpenSysML. Only `dsml.adapter.source` uses these IDs. The IR uses identities and qualified names (PRD-CORE-025).

OpenSysML marks the API JSON form as experimental. If a new OpenSysML version changes the form, the tests of story #30 fail.

### Elements

| Model element | IR kind | Content |
| --- | --- | --- |
| A package or a library package in a model file | `Package` | The annotation `DsmlVersion` of the root package (PRD-DSML-056). |
| A part definition with `#Stakeholder` | `Stakeholder` | PRD-DSML-011. |
| A concern usage with `#Need` | `Need` | `title`, `priority` and `status` in `attributes`, the `doc` text in `doc` (PRD-DSML-013). |
| A requirement usage with `#Requirement` | `Requirement` | `title`, `kind`, `priority`, `status`, and `rationale`, `source` and `owner` if the model gives them (PRD-DSML-015). |

- The identity is the short name. An element with no short name uses its qualified name (PRD-DSML-053).
- An attribute is an owned feature with a value, for example `:>> priority = Priority::must;`. The attribute name is the name of the feature that it redefines. Thus the IR also holds the attributes that a project library adds (PRD-DSML-019).
- An enumeration literal gives an `enum` value with the qualified name of the enumeration. A literal that is a SysML keyword has no quotes in the IR, for example `constraint`.
- The `annotations` of an element hold its plain metadata usages, for example `Waiver` (PRD-DSML-055), with their attributes. The keyword of the element kind is not an annotation.
- A metadata definition of a project that specializes a DSML keyword, for example `metadata def SafetyRequirement :> DSML::Requirement;`, gives the kind of that keyword.
- `types` gives the definitions that type the element, for example the definition of a project library.
- The adapter converts only the elements of the model files. The DSML library and the standard library are not model files.

### Links

The source of a link is the element that declares it.

| Link | Model form | Source | Target |
| --- | --- | --- | --- |
| `stakeholder` | `stakeholder s : Owner;` in a need | The need | The stakeholder that types the member |
| `frame` | `frame n;` in a requirement | The requirement | The framed need |
| `derivation` | `#derivation connection { end #original ::> r1; end #derive ::> r2; }` | Each `#derive` requirement | The `#original` requirement |
| `refinement` | `#refinement dependency r2 to r1;` | Each client of the dependency | Each supplier of the dependency |

The location of a `stakeholder` or `frame` link is the location of its member. The location of a `derivation` or `refinement` link is the location of the connection or of the dependency.

### Model with an error

If the parse gives a SYN-001 finding, the IR holds only the files and the SYN findings. The elements of such a model are not complete.

### Size of the API JSON form

The API JSON form of the PRD model (10 files, 311 requirements) is approximately 12 MB. The gRPC client of OpenSysML refuses a message larger than 4 MiB. The engine adds the channel option `grpc.max_receive_message_length = -1` before it connects. The conversion of the PRD model takes approximately 3 s to 6 s in the development container. Story #33 records the time for a model with 1,000 elements (Q50).
