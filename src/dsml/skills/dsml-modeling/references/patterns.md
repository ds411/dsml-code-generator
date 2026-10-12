# DSML model patterns

This file gives one short model pattern for each layer of a DSML model. The patterns come from the example models of the toolchain: the order service, the order portal and the order web application.

Each pattern is a full model file. Thus each pattern parses and validates with no error finding. The other layers of a pattern are as small as possible. Copy the part of a pattern that you need, then change the names, the IDs and the text.

All patterns use the same model header:

- `private import DSML::*;` imports the DSML keywords.
- `private import ScalarValues::*;` imports `String`, `Integer`, `Boolean` and `Real`.
- `@DsmlVersion { major = 1; minor = 1; }` gives the version of the DSML library.

## Needs layer

A stakeholder is a part definition with `#Stakeholder`. A need is a concern usage with `#Need`. Give each need a short name, a `doc` text, a title, a priority and a status. The `stakeholder` member links the need to its stakeholder. Each stakeholder must have one or more needs (COV-007).

```sysml
package NeedsPattern {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 1; }

    #Stakeholder part def ShopOwner;
    #Stakeholder part def Clerk;

    #Need concern <'N-001'> trackOrders {
        doc /* The shop owner must see the status of each order. */
        :>> title = "Track orders";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder owner : ShopOwner;
    }

    #Need concern <'N-002'> placeOrders {
        doc /* A clerk must place an order for a customer. */
        :>> title = "Place orders";
        :>> priority = Priority::should;
        :>> status = Status::draft;
        subject;
        stakeholder clerk : Clerk;
    }

    #Requirement requirement <'R-001'> getOrderStatus {
        doc /* The API must return the status of an order. */
        :>> title = "Get order status";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::draft;
        frame trackOrders;
    }

    #Requirement requirement <'R-002'> placeOrder {
        doc /* The API must accept a new order. */
        :>> title = "Place an order";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::should;
        :>> status = Status::draft;
        frame placeOrders;
    }
}
```

## Requirements layer

A requirement is a requirement usage with `#Requirement`. Give each requirement a short name, a `doc` text, a title, a kind, a priority and a status. Write one "must" in each requirement text (TXT-003).

- `frame <need>;` links the requirement to a need (COV-002).
- A `#derivation` connection links derived requirements to an original requirement. A derived requirement does not need a `frame` link. The connection needs `private import RequirementDerivation::*;`.
- `rationale`, `source` and `owner` are optional.

```sysml
package RequirementsPattern {
    private import DSML::*;
    private import RequirementDerivation::*;
    @DsmlVersion { major = 1; minor = 1; }

    #Stakeholder part def ShopOwner;

    #Need concern <'N-001'> trackOrders {
        doc /* The shop owner must see the status of each order. */
        :>> title = "Track orders";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder owner : ShopOwner;
    }

    #Requirement requirement <'R-001'> listOrders {
        doc /* The API must return the list of the orders. */
        :>> title = "List orders";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::draft;
        :>> rationale = "The shop owner examines all open orders each day.";
        frame trackOrders;
    }

    #Requirement requirement <'R-002'> pageOrders {
        doc /* The API must return the list of the orders in pages of 50 orders or fewer. */
        :>> title = "Page the order list";
        :>> kind = RequirementKind::performance;
        :>> priority = Priority::should;
        :>> status = Status::draft;
    }

    #derivation connection {
        end #original ::> listOrders;
        end #derive ::> pageOrders;
    }
}
```

## Application layer

The application layer has these elements:

- One enumeration definition with `#Roles` gives the roles of the users.
- An entity is a part definition with `#Entity`. Each attribute usage is a field. One field has `#Key` (STR-005). `@FieldRules` gives the constraints of a field.
- A custom operation is an action definition with `#Operation`. It has an HTTP method and a path (STR-007).
- An application is a part usage with `#Application` and a target (STR-004). An `#Exposed` part exposes an entity, and an `#Exposed` action exposes an operation. Each exposed element has `allowedRoles` or `public = true` (STR-009).
- `satisfy <requirement> by <application>;` links a requirement to the application (COV-003).

An application must also have its infrastructure (XLY-001, XLY-003, XLY-006, XLY-007). The next pattern tells about the infrastructure.

```sysml
package ApplicationPattern {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 1; }

    #Stakeholder part def ShopOwner;

    #Need concern <'N-001'> trackOrders {
        doc /* The shop owner must see the status of each order. */
        :>> title = "Track orders";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder owner : ShopOwner;
    }

    #Requirement requirement <'R-001'> getOrderStatus {
        doc /* The API must return the status of an order. */
        :>> title = "Get order status";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::draft;
        frame trackOrders;
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

    // The infrastructure of the application. The next pattern tells about it.
    #Network part network;
    #ContainerService part apiService;
    #RelationalDatabase part orderDb;
    #UserDirectory part users;
    #Uses dependency from apiService to orderDb;
    #Uses dependency from apiService to users;
    allocate orderApi to apiService;

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
        #Override part orderDbProd :> orderDbAws { :>> multiAz = true; }
    }
}
```

## Infrastructure layer

The infrastructure layer has a logical part and an AWS part:

- The logical part has the kinds `#Network`, `#ContainerService`, `#RelationalDatabase`, `#UserDirectory` and `#SecretStore`. A logical element has no AWS attribute (STR-016).
- `allocate <application> to <service>;` allocates a `fastapi` or `nextjs` application to a `#ContainerService` (XLY-001, XLY-002).
- A `#Uses` dependency links a service to a database, a user directory or a secret store.
- Each logical element has one AWS realization and one `#Realizes` dependency from the realization to the logical element (XLY-003).
- Give the AWS attributes as defaults in the realization, for example `:>> cpu default = 512;`.
- The model has one `#ToolingAccount` and the environments `dev`, `staging` and `prod` (STR-015). Each account has its own 12-digit ID (AWS-001).
- An `#Override` part in an environment changes an AWS attribute for that environment (STR-016). It subsets the AWS realization with `:>`.
- `require constraint { ... }` in a requirement gives a formal constraint. The adapter evaluates it for each environment (FCN-001).

```sysml
package InfrastructurePattern {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 1; }

    #Stakeholder part def ShopOwner;

    #Need concern <'N-001'> trackOrders {
        doc /* The shop owner must see the status of each order. */
        :>> title = "Track orders";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder owner : ShopOwner;
    }

    #Requirement requirement <'R-001'> getOrderStatus {
        doc /* The API must return the status of an order. */
        :>> title = "Get order status";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::draft;
        frame trackOrders;
    }

    #Requirement requirement <'R-002'> orderDataSafe {
        doc /* In prod, the order database must continue to operate after the loss of one availability zone. */
        :>> title = "Order data in two zones";
        :>> kind = RequirementKind::'constraint';
        :>> priority = Priority::must;
        :>> status = Status::draft;
        frame trackOrders;
        require constraint { prod.orderDbProd.multiAz == true }
    }

    #Roles enum def AppRoles { clerk; }

    #Entity part def Order {
        #Key attribute id : Uuid [1];
        attribute total : Decimal [1];
    }

    #Application part orderApi {
        :>> target = Target::fastapi;
        #Exposed part orders : Order [*] {
            :>> crud = (CrudKind::read, CrudKind::list);
            :>> allowedRoles = (AppRoles::clerk);
        }
    }
    satisfy getOrderStatus by orderApi;

    // Infrastructure layer: logical part
    #Network part network;
    #ContainerService part apiService;
    #RelationalDatabase part orderDb;
    #UserDirectory part users;
    #SecretStore part secrets;
    #Uses dependency from apiService to orderDb;
    #Uses dependency from apiService to users;
    #Uses dependency from apiService to secrets;
    allocate orderApi to apiService;

    // Infrastructure layer: AWS part
    #AwsVpc part networkAws { :>> natGatewayCount default = 1; }
    #AwsEcsService part apiServiceAws { :>> cpu default = 512; :>> memory default = 1024; :>> desiredCount default = 1; }
    #AwsRdsPostgres part orderDbAws { :>> instanceClass default = "db.t4g.micro"; :>> multiAz default = false; }
    #AwsCognito part usersAws;
    #AwsSecrets part secretsAws;
    #Realizes dependency from networkAws to network;
    #Realizes dependency from apiServiceAws to apiService;
    #Realizes dependency from orderDbAws to orderDb;
    #Realizes dependency from usersAws to users;
    #Realizes dependency from secretsAws to secrets;

    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "orders.dev.example.com"; }
    #Environment part staging { :>> accountId = "333333333333"; :>> region = "eu-west-1"; :>> domain = "orders.staging.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "orders.example.com";
        #Override part apiServiceProd :> apiServiceAws { :>> desiredCount = 3; :>> minCount = 2; }
        #Override part orderDbProd :> orderDbAws { :>> multiAz = true; }
    }
    satisfy orderDataSafe by prod.orderDbProd;
}
```

## Verification layer

A verification is a verification usage with `#Verification`. Give each verification a short name, a title and a method. `objective { verify <requirement>; }` links the verification to the requirement (COV-004).

- For the method `test`, give the test files in `testFiles`. Each path is relative to the folder of the configuration file (COV-006).
- For the methods `'analysis'`, `inspection` and `demonstration`, give the evidence in the `doc` text.
- A requirement with the status `approved` or later must have a satisfying element and a verification (COV-003, COV-004).

```sysml
package VerificationPattern {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 1; }

    #Stakeholder part def ShopOwner;

    #Need concern <'N-001'> trackOrders {
        doc /* The shop owner must see the status of each order. */
        :>> title = "Track orders";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder owner : ShopOwner;
    }

    #Requirement requirement <'R-001'> orderStatusText {
        doc /* The status text of an order must have 20 characters or fewer. */
        :>> title = "Short order status text";
        :>> kind = RequirementKind::'interface';
        :>> priority = Priority::could;
        :>> status = Status::draft;
        frame trackOrders;
    }

    // Verification layer
    #Verification verification <'V-001'> orderStatusTextInspection {
        doc /* Evidence: a person examines the status values of the order entity. */
        :>> title = "Order status text inspection";
        :>> method = VerificationMethod::inspection;
        objective { verify orderStatusText; }
    }
}
```

## Views of a React application

Phase 2 adds the targets `react` and `nextjs`. A `#View` part in an application gives a page: a list, a detail page or a form. A list or a detail view refers to an entity. A form view refers to an operation.

- `:>> navigation = (...);` gives the views of the navigation, in their order.
- Allocate a `react` application to a `#StaticSite` (XLY-002). A `#AwsStaticSite` realizes the static site.
- A `#Calls` dependency links the `react` application to the API application that it calls (XLY-005).
- A `nextjs` application has views also, but it is allocated to a `#ContainerService` and uses its own database.

```sysml
package ViewsPattern {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 1; }

    #Stakeholder part def Clerk;

    #Need concern <'N-001'> manageOrdersInBrowser {
        doc /* A clerk must see and place orders in a web browser. */
        :>> title = "Manage orders in a browser";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder clerk : Clerk;
    }

    #Requirement requirement <'R-001'> showOrdersInPortal {
        doc /* The portal must show the list of the orders. */
        :>> title = "Show orders in the portal";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::draft;
        frame manageOrdersInBrowser;
    }

    #Roles enum def AppRoles { clerk; }

    #Entity part def Order {
        #Key attribute id : Uuid [1];
        attribute total : Decimal [1] { @FieldRules { minValue = 0; } }
    }

    #Operation action def PlaceOrder {
        in total : Decimal;
        out order : Order;
        :>> method = HttpMethod::post;
        :>> path = "/orders/place";
    }

    #Application part orderApi {
        :>> target = Target::fastapi;
        #Exposed part orders : Order [*] {
            :>> crud = (CrudKind::read, CrudKind::list);
            :>> allowedRoles = (AppRoles::clerk);
        }
        #Exposed action placeOrder : PlaceOrder {
            :>> allowedRoles = (AppRoles::clerk);
        }
    }

    #Application part orderPortal {
        :>> target = Target::react;
        #View part orderList {
            doc /* The list of the orders. */
            :>> kind = ViewKind::list;
            ref :>> entity : Order;
            :>> allowedRoles = (AppRoles::clerk);
        }
        #View part orderDetail {
            doc /* The details of one order. */
            :>> kind = ViewKind::detail;
            ref :>> entity : Order;
            :>> allowedRoles = (AppRoles::clerk);
        }
        #View part placeOrderForm {
            doc /* The form that places an order. */
            :>> kind = ViewKind::form;
            ref :>> operation : PlaceOrder;
            :>> allowedRoles = (AppRoles::clerk);
        }
        :>> navigation = (orderList, placeOrderForm);
    }
    #Calls dependency from orderPortal to orderApi;
    satisfy showOrdersInPortal by orderPortal;

    #Network part network;
    #ContainerService part apiService;
    #RelationalDatabase part orderDb;
    #UserDirectory part users;
    #StaticSite part portalSite;
    #Uses dependency from apiService to orderDb;
    #Uses dependency from apiService to users;
    #Uses dependency from portalSite to users;
    allocate orderApi to apiService;
    allocate orderPortal to portalSite;

    #AwsVpc part networkAws;
    #AwsEcsService part apiServiceAws { :>> cpu default = 512; :>> memory default = 1024; :>> desiredCount default = 1; }
    #AwsRdsPostgres part orderDbAws { :>> instanceClass default = "db.t4g.micro"; :>> multiAz default = false; }
    #AwsCognito part usersAws;
    #AwsStaticSite part portalSiteAws;
    #Realizes dependency from networkAws to network;
    #Realizes dependency from apiServiceAws to apiService;
    #Realizes dependency from orderDbAws to orderDb;
    #Realizes dependency from usersAws to users;
    #Realizes dependency from portalSiteAws to portalSite;

    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "portal.dev.example.com"; }
    #Environment part staging { :>> accountId = "333333333333"; :>> region = "eu-west-1"; :>> domain = "portal.staging.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "portal.example.com";
        #Override part orderDbProd :> orderDbAws { :>> multiAz = true; }
    }
}
```
