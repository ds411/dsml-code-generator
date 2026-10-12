# DSML PRD: modeling language

Status date: 10 October 2026

## Summary

The DSML is a SysML v2 model library with the name `DSML`. With it, one model holds five layers: needs, requirements, application, infrastructure and verification. The model is standard SysML v2 textual notation with user-defined keywords, so each compliant tool can read it.

- **Phase:** 1, except the UI views (phase 2) and the static site (phase 2).
- **Goals covered:** N-001 (one model), N-003 (correct model) and N-005 (no dependency on one cloud).
- **Prefix:** PRD-DSML.
- **Related PRDs:** the toolchain core PRD reads the model, and the validation PRD checks it. The top-level PRD has the conventions and the project dictionary.

The syntax in this PRD is a sketch. The DSML library source sets the final syntax, and OpenSysML must accept it.

## Scope

The DSML covers the structure of a product, not its behavior.

| In scope | Out of scope |
| --- | --- |
| The `DSML` library package: metadata definitions, attribute types and enumerations | A new concrete syntax or a graphical notation |
| Stakeholders, needs and requirements, with links | Behavior: business logic, SysML v2 actions and state machines as code (later phase) |
| Application layer: applications, entities, operations, views, roles, permissions | Models of external systems, except an imported OpenAPI file (phase 2) |
| Infrastructure layer: logical elements, AWS realizations, environments, accounts | Cloud providers other than AWS (later phase) |
| Verification layer: verification elements with links to tests | Generated tests (later phase) |
| Element identity, waivers and library versions | Model storage in a Systems Modeling API server (later phase) |

## Library and model files

The DSML adds metadata to standard SysML v2. It adds no new syntax.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-DSML-001 | The DSML must be a SysML v2 model library package with the name `DSML`. | Inspection | Q7, AD1 |
| PRD-DSML-002 | The DSML must extend SysML v2 only with metadata definitions, attribute definitions and enumeration definitions. It must not add a concrete syntax. | Inspection | Q7 |
| PRD-DSML-003 | Each DSML element kind must be available as a user-defined keyword, for example `#Need`, `#Entity` and `#ContainerService`. | Test | Q7 |
| PRD-DSML-004 | OpenSysML must parse and resolve the DSML library with no error and no warning. | Test | Q8, Q38 |
| PRD-DSML-005 | The DSML library must use only SysML v2 constructs that the OMG pilot implementation also accepts. | Test | Q7, Q8 |
| PRD-DSML-006 | The toolchain package must include the DSML library, so a model needs no download. | Test | PRD-TOP-005 |
| PRD-DSML-007 | A model must be a set of `.sysml` files in one Git repository. The toolchain configuration file must give the files or folders of the model. | Test | Q9 |
| PRD-DSML-008 | A model must import the DSML library with `private import DSML::*;` or refer to its elements with qualified names. | Test | Q7 |

## Stakeholders, needs and requirements

Needs are SysML v2 concerns, and requirements frame them. Each DSML keyword gives its element a base type, and the base type holds the attributes.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-DSML-009 | Each DSML keyword of an element kind must be a metadata definition that specializes `Metaobjects::SemanticMetadata`. Its base type must hold the attributes of the element kind. A keyword on a dependency, and a metadata definition that holds its own attributes, must be a plain metadata definition. | Inspection | Q7, Q59 |
| PRD-DSML-010 | The model must give attribute values with redefinitions of the base type features, for example `:>> priority = Priority::must;`. | Test | Q7, Q11 |
| PRD-DSML-011 | A stakeholder must be a part definition with the keyword `#Stakeholder`. | Test | Q29 |
| PRD-DSML-012 | A need must be a concern usage with the keyword `#Need`. It must have one or more `stakeholder` members that refer to a stakeholder. | Test | Q29, Q46 |
| PRD-DSML-013 | A need must have these attributes: ID (the short name), `title`, text (the `doc` comment), `priority` and `status`. | Test | Q46 |
| PRD-DSML-014 | A requirement must be a requirement usage with the keyword `#Requirement`. It can frame one or more needs with `frame`. | Test | Q29 |
| PRD-DSML-015 | A requirement must have these attributes: ID (the short name), `title`, text (the `doc` comment), `kind`, `priority` and `status`. It can also have `rationale`, `source` and `owner`. | Test | Q11, Q46 |
| PRD-DSML-016 | The DSML must define these enumerations. `Priority`: `must`, `should`, `could`, `wont`. `Status`: `draft`, `approved`, `implemented`, `verified`, `retired`. `RequirementKind`: `functional`, `performance`, `security`, `interface`, `constraint`. | Inspection | Q11, Q46 |
| PRD-DSML-017 | A requirement derivation must use the `#derivation` connection of the SysML v2 `RequirementDerivation` library. A refinement must use a dependency with the `#refinement` metadata of the SysML v2 `ModelingMetadata` library. | Test | Q29 |
| PRD-DSML-018 | A requirement can contain formal constraints (`require constraint`) that refer to attributes of model elements. Quantities must use the SysML v2 quantity and unit libraries. | Test | Q12 |
| PRD-DSML-019 | A project can add attributes to needs and requirements with a project library that specializes the DSML base types. | Demonstration | Q11 |

## Application layer

The application layer holds structure, API operations, UI views and permissions. It does not hold business logic: the generator writes a hand-written stub for each custom operation.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-DSML-020 | An application must be a part usage with the keyword `#Application`. Its attribute `target` must have one of the values `fastapi`, `react` or `nextjs`. | Test | Q18 |
| PRD-DSML-021 | A model can contain more than one application. | Test | Q18 |
| PRD-DSML-022 | An entity must be a part definition with the keyword `#Entity`. Each attribute usage of an entity is a field. | Test | Q14 |
| PRD-DSML-023 | A field type must be one of: `String`, `Integer`, `Boolean`, `Real` from the SysML v2 libraries; `Decimal`, `Date`, `DateTime` and `Uuid` from the DSML library; or an enumeration definition in the model. | Test | Q14 |
| PRD-DSML-024 | An entity must have one primary key field with the keyword `#Key`. | Test | Q14 |
| PRD-DSML-025 | A field multiplicity of `[1]` must mean a required field, and `[0..1]` an optional field. A field can have these DSML constraints: `minLength`, `maxLength`, `minValue`, `maxValue`, `pattern`, `unique`, and `precision` and `scale` for a `Decimal` field. | Test | Q14 |
| PRD-DSML-026 | A relation between entities must be a reference usage typed by the related entity, with the multiplicity `[0..1]`, `[1]` or `[*]`. A relation with `[*]` at the two ends is a many-to-many relation. | Test | Q14 |
| PRD-DSML-027 | An application must expose an entity with an entity usage that has the keyword `#Exposed`. Its attribute `crud` must list the CRUD operations: `create`, `read`, `update`, `delete` and `list`. | Test | Q14 |
| PRD-DSML-028 | A custom operation must be an action definition with the keyword `#Operation` and typed `in` and `out` parameters. The toolchain must not read the body of the action. | Test | Q14, Q15 |
| PRD-DSML-029 | Each operation must have an HTTP method and a path. The DSML must give defaults for CRUD operations. A custom operation must state its method and path. | Test | Q14 |
| PRD-DSML-030 | A `react` application must refer to the application whose API it calls, with a dependency that has the `#Calls` metadata. The two applications then use one API model. | Test | Q18 |
| PRD-DSML-058 | Phase 2: an external API must be a part usage with the keyword `#ExternalApi`. Its attribute `openApiFile` must give the path of an OpenAPI 3.1 JSON file, relative to the repository root. A `react` application can call it with a `#Calls` dependency. | Test | Q18, Q65 |
| PRD-DSML-031 | Phase 2: a view must be a part usage in an application with the keyword `#View`. Its attribute `kind` must be `list`, `detail` or `form`. A list or detail view must refer to one entity. A form view must refer to one operation. | Test | Q14 |
| PRD-DSML-032 | Phase 2: an application can give its navigation as an ordered list of views. | Test | Q14 |
| PRD-DSML-033 | The roles of a model must be the values of one enumeration definition with the keyword `#Roles`. Each exposed operation, entity and view must list the roles that can use it in its attribute `allowedRoles`. The attribute value `public = true` must mean that no authentication is necessary. | Test | Q14, Q42 |
| PRD-DSML-034 | A destructive database change must have the `#Destructive` metadata on the changed entity or field. A rename must give the old name in the attribute `renamedFrom`. | Test | Q19 |

## Infrastructure layer

The infrastructure layer has a logical part with no AWS terms and an AWS part that realizes it. Environments change only a small set of attributes.

| Logical kind | AWS kind | AWS services that the IaC generator writes | Phase |
| --- | --- | --- | --- |
| `#Network` | `#AwsVpc` | VPC, public and private subnets, internet gateway, NAT gateways | 1 |
| `#ContainerService` | `#AwsEcsService` | ECS on Fargate, ALB, target group, CloudWatch Logs, IAM roles | 1 |
| `#RelationalDatabase` | `#AwsRdsPostgres` | RDS for PostgreSQL, KMS key | 1 |
| `#UserDirectory` | `#AwsCognito` | Cognito user pool, app clients, groups, managed login domain | 1 |
| `#SecretStore` | `#AwsSecrets` | Secrets Manager, KMS key | 1 |
| `#StaticSite` | `#AwsStaticSite` | S3, CloudFront, ACM, Route 53 | 2 |

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-DSML-035 | A logical infrastructure element must be a part usage with one of the logical kinds in the table of the section "Infrastructure layer". | Test | Q20, Q21, Q61 |
| PRD-DSML-036 | A logical element must not contain an AWS term, an AWS attribute or an AWS service name. | Inspection | Q20, N-005 |
| PRD-DSML-037 | Each logical element must have one AWS realization: a part usage with the matching AWS kind and a dependency with the `#Realizes` metadata to the logical element. | Test | Q20 |
| PRD-DSML-038 | An AWS realization must hold the AWS attributes, for example the RDS instance class or the Fargate CPU and memory. | Inspection | Q20 |
| PRD-DSML-039 | Each application must be allocated to one logical element with `allocate`. A `fastapi` or `nextjs` application must be allocated to a `#ContainerService`. A `react` application must be allocated to a `#StaticSite`. | Test | Q20, Q29 |
| PRD-DSML-040 | A container service or a static site must refer to each database, user directory and secret store that it uses, with a dependency that has the `#Uses` metadata. | Test | Q21 |
| PRD-DSML-041 | An environment must be a part usage with the keyword `#Environment`. It must have an AWS account ID, an AWS Region and a domain name. The model must contain the environments `dev`, `staging` and `prod`. | Test | Q24, Q44 |
| PRD-DSML-042 | An environment can change only these attributes of an AWS realization: `cpu`, `memory`, `instanceClass`, `desiredCount`, `minCount`, `maxCount`, `multiAz` and `natGatewayCount`. | Test | Q24 |
| PRD-DSML-043 | The model must have one part usage with the keyword `#ToolingAccount`. It must have the AWS account ID and the AWS Region of the ECR repositories. | Test | Q44 |
| PRD-DSML-044 | A project must not add a logical kind or an AWS kind. A new kind must come in a new version of the DSML library. | Inspection | Q21, Q23 |

## Verification layer

Verifications connect requirements to the tests and reviews that verify them. Phase 1 links to test files that developers write. The toolchain does not generate tests in phase 1.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-DSML-045 | A verification must be a verification usage with the keyword `#Verification`. It must have an ID (the short name), a `title` and a `method`. | Test | Q13, Q46 |
| PRD-DSML-046 | The attribute `method` must have one of the values `test`, `analysis`, `inspection` or `demonstration`. | Test | Q46 |
| PRD-DSML-047 | A verification must refer to each requirement that it verifies with `verify` in its objective. | Test | Q13, Q29 |
| PRD-DSML-048 | A verification with the method `test` must give one or more test file paths, relative to the repository root, in the attribute `testFiles`. | Test | Q13, Q30 |
| PRD-DSML-049 | A verification can give test case names in the attribute `testCases`, for example a pytest node ID. | Test | Q13 |

## Identity, waivers and library versions

Short names give stable IDs to needs, requirements and verifications. Other elements use their qualified names.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-DSML-050 | Each need, requirement and verification must have a short name with the pattern of its kind: `N-<NNN>`, `R-<NNN>` or `V-<NNN>`. `<NNN>` has three or more digits with leading zeros. | Test | Q45 |
| PRD-DSML-051 | A project can set different ID patterns in the toolchain configuration file. | Test | Q45 |
| PRD-DSML-052 | Each short name must be unique in the model. A deleted ID must not be used again. | Test | Q10, Q45 |
| PRD-DSML-053 | Each element without a short name must use its qualified name as its identity. | Test | Q10 |
| PRD-DSML-054 | An element can have an OpenSysML `IdentityMetadata::ElementId` annotation. The DSML must not require it. | Inspection | Q45 |
| PRD-DSML-055 | A waiver must be a `#Waiver` metadata usage on the element. It must have the attributes `rule` (the rule ID), `reason` and `owner`. It can have the attribute `expires` (a date). | Test | Q28 |
| PRD-DSML-056 | The DSML library must have a semantic version. Each model must state the major and minor version of the library that it uses, with the `#DsmlVersion` metadata on its root package. | Test | Q7 |
| PRD-DSML-057 | A minor version of the DSML library must not make a valid model invalid. A major version must come with migration notes. | Inspection | Q7 |

## Example model

The example shows the five layers for one FastAPI service. It is a copy of `docs/model/examples/order-service.sysml`. OpenSysML 0.9.2 parses and resolves it with the DSML library 1.0.0 with no error and no warning. `docs/model/syntax-changes.md` gives each change to the first sketch and its reason.

```sysml
package OrderService {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }

    // Needs layer
    #Stakeholder part def ShopOwner;

    #Need concern <'N-001'> trackOrders {
        doc /* The shop owner must see the status of each order. */
        :>> title = "Track orders";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder owner : ShopOwner;
    }

    // Requirements layer
    #Requirement requirement <'R-001'> getOrderStatus {
        doc /* The API must return the status of an order. */
        :>> title = "Get order status";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame trackOrders;
    }

    #Requirement requirement <'R-002'> orderDataSafe {
        doc /* In prod, the order database must continue to operate after the loss of one availability zone. */
        :>> title = "Order data in two zones";
        :>> kind = RequirementKind::'constraint';
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame trackOrders;
        require constraint { prod.orderDbProd.multiAz == true }
    }

    // Application layer
    #Roles enum def AppRoles { clerk; admin; }
    enum def OrderStatus { open; shipped; cancelled; }

    #Entity part def Order {
        #Key attribute id : Uuid [1];
        attribute status : OrderStatus [1];
        attribute total : Decimal [1] { @FieldRules { minValue = 0; } }
        attribute note : String [0..1] { @FieldRules { maxLength = 500; } }
    }

    #Operation action def CancelOrder {
        in orderId : Uuid;
        out order : Order;
        :>> method = HttpMethod::post;
        :>> path = "/orders/{orderId}/cancel";
    }

    #Application part orderApi {
        :>> target = Target::fastapi;
        #Exposed part orders : Order [*] {
            :>> crud = (CrudKind::create, CrudKind::read, CrudKind::list);
            :>> allowedRoles = (AppRoles::clerk, AppRoles::admin);
        }
        #Exposed action cancelOrder : CancelOrder {
            :>> allowedRoles = (AppRoles::admin);
        }
    }
    satisfy getOrderStatus by orderApi;

    // Infrastructure layer: logical part
    #Network part network;
    #ContainerService part apiService;
    #RelationalDatabase part orderDb;
    #UserDirectory part users;
    #Uses dependency from apiService to orderDb;
    #Uses dependency from apiService to users;
    allocate orderApi to apiService;

    // Infrastructure layer: AWS part
    #AwsVpc part networkAws;
    #AwsEcsService part apiServiceAws { :>> cpu default = 512; :>> memory default = 1024; :>> desiredCount default = 1; }
    #AwsRdsPostgres part orderDbAws { :>> instanceClass default = "db.t4g.micro"; :>> multiAz default = false; }
    #AwsCognito part usersAws;
    #Realizes dependency from networkAws to network;
    #Realizes dependency from apiServiceAws to apiService;
    #Realizes dependency from orderDbAws to orderDb;
    #Realizes dependency from usersAws to users;

    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "orders.dev.example.com"; }
    #Environment part staging { :>> accountId = "333333333333"; :>> region = "eu-west-1"; :>> domain = "orders.staging.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "orders.example.com";
        #Override part apiServiceProd :> apiServiceAws { :>> desiredCount = 3; }
        #Override part orderDbProd :> orderDbAws { :>> multiAz = true; }
    }
    satisfy orderDataSafe by prod.orderDbProd;

    // Verification layer
    #Verification verification <'V-001'> orderStatusTest {
        :>> title = "Order status API test";
        :>> method = VerificationMethod::test;
        :>> testFiles = ("app/features/order/read_order/test_endpoint.py");
        objective { verify getOrderStatus; }
    }
    #Verification verification <'V-002'> orderDataSafeAnalysis {
        doc /* Evidence: the IR adapter evaluates the formal constraint of R-002 on the prod override orderDbProd. The result is true. */
        :>> title = "Order database in two zones analysis";
        :>> method = VerificationMethod::'analysis';
        objective { verify orderDataSafe; }
    }
}
```
