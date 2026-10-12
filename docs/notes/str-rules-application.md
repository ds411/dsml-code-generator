# STR rules of the applications and the environments

Story #60 added the rules STR-005 to STR-012 (PRD-VAL-015). All of them have the default severity `error`. Story #161 added the views to STR-010. Story #163 added STR-017 (error) for the imported OpenAPI files (PRD-VAL-016, `docs/notes/openapi-import.md`).

- Rules STR-005 to STR-010 and STR-017: `src/dsml/validate/rules/str_application.py`. STR-005 to STR-008 do not examine the elements of an imported OpenAPI file. The IR adapter writes the STR-017 findings into the IR, and STR-017 reads them.
- Rules STR-011 and STR-012: `src/dsml/validate/rules/str_environment.py`.
- Operations, methods and paths of an application: `src/dsml/ir/operations.py`.
- Test models: `tests/models/rules/STR-005/` to `tests/models/rules/STR-012/`. The models `accept-views.sysml` and `reject-views.sysml` of STR-010 have views.
- Tests: `tests/test_str_rules_application.py`.

## Rules

| Rule | The rule examines | Location of the finding |
| --- | --- | --- |
| STR-005 | The attribute `target` of each application. The known targets are `fastapi`, `react` and `nextjs`. | The application. |
| STR-006 | The fields with `#Key` of each entity. | The entity. |
| STR-007 | The types of each field. The supported types are in PRD-DSML-023. An enumeration definition of the model, also a `#Roles` enumeration, is a supported type. A field with no type gets a finding. | The field. |
| STR-008 | The attributes `method` and `path` of each `#Operation` definition. An empty path is the same as no path. | The operation. |
| STR-009 | The method and the path of each operation of one application. | The second operation. |
| STR-010 | The attributes `allowedRoles` and `public` of each exposed entity, exposed operation and view. | The exposed element or the view. |
| STR-011 | The environments `dev`, `staging` and `prod`, and their attributes `accountId`, `region` and `domain`. | The root package for a missing environment. Else the environment. |
| STR-012 | The attributes that each override changes. | The changed attribute. |

## Operations and routes

The module `dsml.ir.operations` gives the operations of an application from the IR (PRD-APP-110). The FastAPI generator must use the same module. Thus the generator and STR-009 use the same methods and paths.

- An exposed entity gives one operation for each item of its attribute `crud`. The IR adapter writes the default method and path of each CRUD operation from the DSML library into the IR attribute `crudDefaults`. The name of the exposed entity usage replaces `{entities}`, for example `/orders/{id}`.
- An exposed custom operation gives the method and the path of its `#Operation` definition.

STR-009 compares routes. A route is the method and the path with no names of path parameters. Thus `GET /orders/{id}` and `GET /orders/{orderId}` have the same route, because an HTTP server cannot tell them apart. The first operation of a route, in the order of the model, gets no finding.

## Models with no solution

PRD-DSML-041 tells that the model must contain the environments `dev`, `staging` and `prod`. STR-011 reports a missing environment only if the model has an application or an infrastructure element. Thus a model of the needs and requirements only, for example the PRD model, gets no finding for a missing environment.

## Changes of attributes in an override

The DSML library gives the AWS kinds only the attributes of PRD-DSML-042. Thus a redefinition of a different library attribute in an override is a SYN-001 error, because OpenSysML cannot resolve the name. A model can add an attribute to a realization, for example `attribute engine : String default = "postgres";`. An override can then redefine it. The IR adapter keeps this change in the IR, and STR-012 reports it.

## Views and static sites

Story #161 changed STR-010 and the XLY rules for the views and the static sites of phase 2 (PRD-DSML-031, PRD-DSML-033, PRD-DSML-039, PRD-DSML-040). The XLY rules are in `src/dsml/validate/rules/xly.py`. Their tests are in `tests/test_xly_rules.py`.

| Rule | Change |
| --- | --- |
| STR-010 | The rule also examines each view. The message names the view. |
| XLY-001 | An allocation to a `#StaticSite` is an allocation to a logical element. Thus a `react` application on a static site gets no finding. |
| XLY-002 | A `react` application must be allocated to a `#StaticSite`. An allocation to a `#ContainerService` gets a finding. |
| XLY-003 | A static site must have one `#AwsStaticSite` realization. |
| XLY-004 | The rule examines the `#Uses` links of the application and of its static site. |
| XLY-005 | No change of the check. The rule accepts only a `#Calls` dependency to an application. The import story of milestone M9 adds the imported OpenAPI file. |
| XLY-007 | A view that is not public is protected, as an exposed entity or operation is. The service or the static site of the application must use a `#UserDirectory`. |

Each changed XLY rule has the models `accept-static-site.sysml` and `reject-static-site.sysml`, or `accept-views.sysml` and `reject-views.sysml`, in `tests/models/rules/<rule>/`. XLY-004 has the static site in `accept.sysml`. The order portal model (`docs/model/examples/order-portal/`) gives no finding of these rules.
