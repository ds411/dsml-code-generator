# IR of the application, infrastructure and verification layers

Story #31 added the conversion of the application layer, the infrastructure layer and the verification layer into the IR. Story #159 added the views, the navigation and the static sites (IR 1.1.0). This document tells how the adapter reads these layers and what the IR holds for them. `docs/notes/ir.md` gives the structure of the IR.

- Entry point: `dsml.adapter.convert.build_ir(model, files)` (story #30). It calls the converter of each layer.
- Converter: `src/dsml/adapter/solution.py`. It uses the model reader `src/dsml/adapter/source.py` of story #30.
- Values of each environment: `src/dsml/ir/environments.py`.
- Tests: `tests/test_solution_layers.py`. Test models: `tests/models/ir/solution-layers.sysml`, `tests/models/ir/views.sysml` and `tests/models/ir/view-references.sysml`. The golden IR file of `views.sysml` is `tests/golden/ir/views.ir.json`. The script `scripts/write_golden_ir.py` writes it again.

## How the adapter reads the model

The adapter reads two outputs of OpenSysML:

1. The API JSON form (`docs/notes/ir.md`, story #30). The adapter reads the structure, the metadata usages, the links and the source locations from it. The query interface of OpenSysML 0.9.2 does not give the ends of a dependency or of an allocation, but the API JSON form gives them.
2. Expressions. The adapter reads the value of each DSML attribute with an expression in the namespace of the element (`ParsedModel.evaluate_value()`). Thus a default value of the DSML library is also in the IR, for example `public = false`. An override also gets its values in its environment this way.

The IR holds identities and qualified names only, not the internal IDs of OpenSysML (PRD-CORE-025). A test makes sure of this.

## Element kinds

| IR kind | Model element |
| --- | --- |
| `Application`, `Entity`, `Exposed`, `Operation`, `Roles`, `View`, `ExternalApi` | An element with the keyword of the same name. |
| `Network`, `ContainerService`, `RelationalDatabase`, `UserDirectory`, `SecretStore`, `StaticSite` | A logical element with the keyword of the same name. |
| `AwsVpc`, `AwsEcsService`, `AwsRdsPostgres`, `AwsCognito`, `AwsSecrets`, `AwsStaticSite` | An AWS realization with the keyword of the same name. |
| `Environment`, `Override`, `ToolingAccount`, `Verification` | An element with the keyword of the same name. |
| `Enumeration` | An enumeration definition with no keyword. |
| `Field` | A named attribute usage of an entity. |
| `Relation` | A named reference usage or part usage of an entity that an entity types. |
| `Parameter` | A named `in`, `out` or `inout` parameter of an operation. |

An external API also gives the `Entity`, `Field`, `Relation`, `Operation` and `Parameter` elements of its OpenAPI file (story #163). `docs/notes/openapi-import.md` gives these elements.

The location of an element is the first character of its declaration. If the declaration starts with a keyword, for example `#Entity`, the location is the `#` character.

The field `types` gives the identities of the definitions that type the element and of the features that it subsets. For an override, `types` gives the AWS realization that it changes.

## Attributes

The adapter reads the DSML attributes of each kind from the base types of the DSML library, for example `BaseTypes::AwsEcsService`. An attribute with no value is not in the IR. A logical kind has no DSML attributes. For a logical element, the IR holds each attribute with a value that the model declares on it, thus rule STR-016 can find an AWS attribute (story #59). An attribute with the multiplicity `[*]` or `[0..*]` is always a `list` value, also if it has one item.

The adapter adds these attributes, which are not DSML attributes:

| Kind | Attribute | Value |
| --- | --- | --- |
| `Enumeration`, `Roles` | `literals` | A `list` of `enum` values, in the order of the model. |
| `Application` | `navigation` | A `list` of `reference` values to the views in the navigation, in the order of the model (PRD-DSML-032). One view gives a list with one item. An application with no navigation has no `navigation` attribute. |
| `View` (list or detail) | `entity` | A `reference` value to the entity that the view shows (PRD-DSML-031). |
| `View` (form) | `operation` | A `reference` value to the operation that the view calls (PRD-DSML-031). |
| `Exposed` (entity only) | `crudDefaults` | A `list` with one item for each item of `crud`, in the same order. Each item is a `list` of three values: the CRUD kind (`enum`), the HTTP method (`enum`) and the path (`string`). The values come from `DSML::crudDefaults` in the library (PRD-DSML-029). |

An attribute has a location if the element declares it. An attribute that has its value from the library has no location.

### Views and navigation

A view is a part usage with the keyword `#View` in an application. The owner of the view is the application. The IR holds its DSML attributes `kind`, `allowedRoles` and `public`, as for an exposed element. The model gives the entity or the operation of a view as the type of a redefined reference, for example `ref :>> entity : Order;`. The IR gives the identity of that type in the attribute `entity` or `operation`.

The navigation is the attribute `navigation` of the application, for example `:>> navigation = (orderList, orderDetail);`. The writer does not sort the items of a `list` value. Thus the IR keeps the order of the model, because the order is the order of the views in the navigation (PRD-CORE-031).

A list or detail view must refer to an entity, and a form view must refer to an operation (PRD-DSML-031). OpenSysML gives SYN-001 for a reference that it cannot resolve. It gives no error for a missing reference, and only a warning for a reference to an element of the wrong kind. Thus the adapter adds a SYN-001 finding for each view with a reference that is missing or that does not refer to an element of the correct kind. The finding has the location of the reference, or the location of the view if it has no reference. The IR keeps its elements, because the parse gave no error. A view with no `kind` gets no finding.

### Annotations

A metadata usage that does not give the kind of the element is an annotation. Examples are `#Key`, `@FieldRules` and `@Destructive`. Each annotation has the attributes that its body gives, with the value form of the literal in the model. For example, `minValue = 0` gives an `integer` value, and `minValue = 0.5` gives a `real` value.

## Links

The links of a static site use the same statements as the links of a container service: `allocate` from a `react` application to the static site, `#Realizes` from the `#AwsStaticSite` to the static site, and `#Uses` from the static site to a user directory (PRD-DSML-037, PRD-DSML-039, PRD-DSML-040).

| Link type | Model statement | Source | Target |
| --- | --- | --- | --- |
| `satisfy` | `satisfy R by E;` | `E` | `R` |
| `allocate` | `allocate A to S;` | `A` | `S` |
| `realizes` | `#Realizes dependency from W to L;` | `W` | `L` |
| `uses` | `#Uses dependency from S to D;` | `S` | `D` |
| `calls` | `#Calls dependency from C to A;` | `C` | `A` |
| `verify` | `verify R;` in the objective of a verification `V` | `V` | `R` |

The location of a link is the first character of its statement. For `verify`, it is the first character of `verify`.

`E` in a `satisfy` link can be a feature chain, for example `satisfy orderDataSafe by prod.orderDbProd;` (story #136). OpenSysML 0.9.2 gives the chain as text, not as a reference. The adapter finds the element of the chain in the namespace of the link, or in a namespace that contains it. Each name after the first name must be an owned member of the element before it. The pilot kernel does not accept the qualified name `prod::orderDbProd` for a feature in a part, so a model must use the chain.

## Environments

An override holds only the attributes that it changes, with their locations. It also holds a change of an attribute that the model adds to the realization, for example `:>> engine = "postgres-16";`. Rule STR-012 uses this to find a change of an attribute that PRD-DSML-042 does not permit.

The function `realization_attributes(ir, environment)` in `dsml.ir.environments` gives the attributes of each AWS realization in one environment. It starts with the values of the realization and replaces each value that an override in the environment changes. For the example model:

| Environment | `apiServiceAws.desiredCount` | `orderDbAws.multiAz` |
| --- | --- | --- |
| `dev` | 1 | `false` |
| `staging` | 1 | `false` |
| `prod` | 3 | `true` |

Generators must get the values of an environment through this function, not from OpenSysML (PRD-CORE-026).
