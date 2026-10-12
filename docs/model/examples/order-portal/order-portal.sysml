// The phase 2 reference model "order portal" (story #160). It contains the
// five layers of the order service, a React application that calls the
// FastAPI application, and a static site for the React application.
package OrderPortal {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 1; }

    // Needs layer
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

    #Need concern <'N-002'> manageOrdersInBrowser {
        doc /* A clerk must see and place orders in a web browser. */
        :>> title = "Manage orders in a browser";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder clerk : Clerk;
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

    #Requirement requirement <'R-003'> showOrdersInPortal {
        doc /* The portal must show the list of the orders and the details of one order. */
        :>> title = "Show orders in the portal";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame manageOrdersInBrowser;
    }

    #Requirement requirement <'R-004'> placeOrderInPortal {
        doc /* The portal must have a form that places an order. */
        :>> title = "Place an order in the portal";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame manageOrdersInBrowser;
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

    #Operation action def PlaceOrder {
        in total : Decimal;
        out order : Order;
        :>> method = HttpMethod::post;
        :>> path = "/orders/place";
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
        #Exposed action placeOrder : PlaceOrder {
            :>> allowedRoles = (AppRoles::clerk, AppRoles::admin);
        }
        #Exposed action cancelOrder : CancelOrder {
            :>> allowedRoles = (AppRoles::admin);
        }
    }
    satisfy getOrderStatus by orderApi;

    #Application part orderPortal {
        :>> target = Target::react;
        #View part orderList {
            doc /* The list of the orders. */
            :>> kind = ViewKind::list;
            ref :>> entity : Order;
            :>> allowedRoles = (AppRoles::clerk, AppRoles::admin);
        }
        #View part orderDetail {
            doc /* The details of one order. */
            :>> kind = ViewKind::detail;
            ref :>> entity : Order;
            :>> allowedRoles = (AppRoles::clerk, AppRoles::admin);
        }
        #View part placeOrderForm {
            doc /* The form that places an order. */
            :>> kind = ViewKind::form;
            ref :>> operation : PlaceOrder;
            :>> allowedRoles = (AppRoles::clerk, AppRoles::admin);
        }
        #View part cancelOrderForm {
            doc /* The form that cancels an order. */
            :>> kind = ViewKind::form;
            ref :>> operation : CancelOrder;
            :>> allowedRoles = (AppRoles::admin);
        }
        :>> navigation = (orderList, placeOrderForm);
    }
    #Calls dependency from orderPortal to orderApi;
    satisfy showOrdersInPortal by orderPortal;
    satisfy placeOrderInPortal by orderPortal;

    // Infrastructure layer: logical part
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

    // Infrastructure layer: AWS part
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
        #Override part apiServiceProd :> apiServiceAws { :>> desiredCount = 3; }
        #Override part orderDbProd :> orderDbAws { :>> multiAz = true; }
    }
    satisfy orderDataSafe by prod.orderDbProd;

    // Verification layer
    #Verification verification <'V-001'> orderStatusTest {
        :>> title = "Order status API test";
        :>> method = VerificationMethod::test;
        :>> testFiles = ("services/order-api/app/features/order/read_order/test_endpoint.py");
        objective { verify getOrderStatus; }
    }
    #Verification verification <'V-002'> orderDataSafeAnalysis {
        doc /* Evidence: the IR adapter evaluates the formal constraint of R-002 on the prod override orderDbProd. The result is true. */
        :>> title = "Order database in two zones analysis";
        :>> method = VerificationMethod::'analysis';
        objective { verify orderDataSafe; }
    }
    #Verification verification <'V-003'> showOrdersTest {
        :>> title = "Order list and order details test";
        :>> method = VerificationMethod::test;
        :>> testFiles = ("apps/order-portal/tests/app/app.test.tsx", "apps/order-portal/tests/shared/shared.test.ts", "apps/order-portal/tests/widgets/widgets.test.tsx");
        objective { verify showOrdersInPortal; }
    }
    #Verification verification <'V-004'> placeOrderTest {
        :>> title = "Place order form test";
        :>> method = VerificationMethod::test;
        :>> testFiles = ("apps/order-portal/tests/features/features.test.tsx", "apps/order-portal/tests/field-rules/field-rules.test.ts");
        objective { verify placeOrderInPortal; }
    }
}
