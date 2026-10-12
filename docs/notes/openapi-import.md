# Import of an external OpenAPI file

Story #163 added the import of an external OpenAPI file into the IR. Decision Q65 (#151) selected the form. A `react` application can call an external API in place of an application of the model (PRD-APP-006).

- Keyword: `#ExternalApi` in the DSML library 1.1.0 (PRD-DSML-058).
- Adapter module: `src/dsml/adapter/openapi.py` (PRD-CORE-055).
- Rule: STR-017 (error) in `src/dsml/validate/rules/str_application.py` (PRD-VAL-016).
- Helper for the rules: `src/dsml/ir/external.py`.
- Tests: `tests/test_openapi_import.py`. Test models and files: `tests/models/openapi/`, `tests/models/rules/STR-017/` and `tests/models/rules/XLY-005/accept-external-api.sysml`.
- Golden IR file: `tests/golden/ir/openapi.ir.json`. The script `scripts/write_golden_ir.py` writes it again.

## Model

An external API is a part usage with the keyword `#ExternalApi`. The attribute `openApiFile` gives the path of an OpenAPI 3.1 JSON file, relative to the repository root. A `react` application calls the external API with a `#Calls` dependency.

```sysml
#Application part orderPortal { :>> target = Target::react; }

#ExternalApi part orderApi {
    :>> openApiFile = "services/order-api/openapi.gen.json";
}

#Calls dependency from orderPortal to orderApi;
```

The file can be the `openapi.gen.json` file of a FastAPI application of a different repository. The test model `tests/models/openapi/order-portal.sysml` uses the golden `openapi.gen.json` file of the order service.

Rule XLY-005 accepts a `#Calls` dependency from a `react` application to an application or to an external API.

## How the adapter reads the file

The IR adapter reads the file after it converts the model. The path is relative to the repository root, which is the current folder of `dsml`. The adapter does not use the network (PRD-TOP-005). Validators and generators read only the IR (PRD-CORE-026).

The adapter starts at the operations. It reads each schema that a request body or a success response refers to, and each schema that such a schema refers to. Thus it does not read these items:

- The error responses, for example `401` or `422` with `application/problem+json`. The schema `Problem` of a FastAPI target is only in these responses.
- A schema that no operation refers to.

## Subset

The subset is the subset of decision Q65: object schemas with scalar and enumeration properties, and operations with an `operationId`, a JSON request body and a JSON response. The table gives the items of the subset in full.

| Item | The adapter reads |
| --- | --- |
| Root | `openapi` with a version `3.1.x`, `paths` and `components`. It ignores `info`, `servers`, `tags` and `security`. |
| `components` | `schemas`. It ignores `securitySchemes`. |
| Path item | The methods `get`, `post`, `put`, `patch` and `delete` of `DSML::HttpMethod`. |
| Operation | `operationId` (must be unique), `parameters`, `requestBody` and `responses`. It ignores `tags` and `security`. |
| Parameter | `name`, `in` (`path` or `query`), `required` and a scalar `schema`. |
| Request body | `content` with only `application/json`, and `required`. The schema must refer to an object schema. |
| Success response | The `2xx` response with the lowest code. `content` with only `application/json`, or no `content` (for example `204`). The schema must refer to an object schema, or be an array of references to an object schema. |
| Object schema | `type: object`, `properties`, `required` and `additionalProperties` with `true` or `false`. |
| Property | A scalar type, an enumeration of strings, a reference to an object schema, or an array of one of these. `anyOf` with `{"type": "null"}` gives an optional property. The form `"type": ["string", "null"]` also gives an optional property. |

The adapter ignores the keys `title`, `description`, `summary`, `externalDocs` and `deprecated` on each object. On a property and on the schema of a parameter, it also ignores the checks of a value, for example `pattern`, `maxLength`, `minimum` and `default`.

Each other item gives one STR-017 finding (error). Examples are `allOf`, `oneOf`, an inline object, a header parameter, a `text/plain` content and an OpenAPI 3.0 file.

### Difference from the text of PRD-CORE-055

PRD-CORE-055 gives "scalar and enumeration properties". The list operation of a FastAPI target gives a page schema, for example `ListOrderPage`. Its property `items` is an array of references to the output schema. Thus the subset also accepts a reference to an object schema and an array. Without them, the `openapi.gen.json` file of the order service gives a STR-017 finding, and the acceptance criterion of story #163 is not true.

### Types

| OpenAPI | IR type |
| --- | --- |
| `string` | `ScalarValues::String` |
| `string` with `format: uuid` | `DSML::Uuid` |
| `string` with `format: date` | `DSML::Date` |
| `string` with `format: date-time` | `DSML::DateTime` |
| `integer` | `ScalarValues::Integer` |
| `number` | `ScalarValues::Real` |
| `boolean` | `ScalarValues::Boolean` |
| `anyOf` with `number` and `string` | `DSML::Decimal`. FastAPI gives a decimal input in this form. |
| `string` with `enum` | `ScalarValues::String`, with the attribute `literals` |

## IR

The IR kind `ExternalApi` is new in IR 1.1.0 (`docs/notes/ir.md`). The attribute `openApiFile` is a `string` value. The adapter adds these elements for each external API. The identity of each element starts with the identity of the external API.

| IR kind | OpenAPI item | Identity | Content |
| --- | --- | --- | --- |
| `Entity` | An object schema | `<api>::<schema>` | The `doc` is the `description`. The owner is the external API. |
| `Field` | A scalar or enumeration property | `<api>::<schema>::<property>` | `types` gives the type. An enumeration has the attribute `literals`: a `list` of `string` values. |
| `Relation` | A property that refers to an object schema | `<api>::<schema>::<property>` | `types` gives the identity of the entity. |
| `Operation` | An operation | `<api>::<operationId>` | The attributes `method` (`DSML::HttpMethod`) and `path`. The owner is the external API. |
| `Parameter` | A parameter, the request body, the success response | `<api>::<operationId>::<name>` | The direction is `in`, or `out` for the response. The attribute `in` gives `path`, `query`, `body` or `response`. The name of the request body is `body`. The name of the response is `response`. |

The multiplicity is `[1..1]` for a required property that is not optional, `[0..1]` for an optional property, and `[0..*]` for an array. A query parameter that is not required, and a request body that is not required, have the multiplicity `[0..1]`.

The location of each imported element is the location of the external API in the model. The location of a STR-017 finding is the location of `openApiFile`, or of the external API if it has no `openApiFile`.

If a file gives a STR-017 finding, the IR holds no element of that file. The adapter stops at the first item outside the subset, thus one file gives one finding.

## Rules and reports

The imported elements are not elements of the model. Thus these rules and reports do not examine them:

- STR-005 to STR-008. For example, an OpenAPI schema has no `#Key` field (STR-006).
- The orphans report. The report examines the external API itself.

The function `imported(ir)` in `dsml.ir.external` gives the identities of the imported elements.

## Items for later stories

- Story #175 added the React client of an external API (`docs/notes/react-generator.md`, section "External API").
- The IR has no hash of the OpenAPI file. Thus the suspect report does not find a change of the file.
