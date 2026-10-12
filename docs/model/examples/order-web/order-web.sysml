// The phase 3 reference model "order web" (story #178). It contains the five
// layers and one Next.js application. The application holds the API and the
// pages, and it uses a database, a user directory and a secret store.
package OrderWeb {
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

    #Need concern <'N-002'> manageOrdersOnWeb {
        doc /* A clerk must see, change and cancel orders in a web application. */
        :>> title = "Manage orders on the web";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder clerk : Clerk;
    }

    // Requirements layer
    #Requirement requirement <'R-001'> manageOrderData {
        doc /* The web application must create, read, update, delete and list orders through its API. */
        :>> title = "Manage order data";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame manageOrdersOnWeb;
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

    #Requirement requirement <'R-003'> showOrdersOnWeb {
        doc /* The web application must show the list of the orders and the details of one order. */
        :>> title = "Show orders on the web";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame trackOrders;
    }

    #Requirement requirement <'R-004'> cancelOrderOnWeb {
        doc /* The web application must have a form that cancels an order. Only an admin can cancel an order. */
        :>> title = "Cancel an order on the web";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame manageOrdersOnWeb;
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

    #Application part orderWeb {
        :>> target = Target::nextjs;
        #Exposed part orders : Order [*] {
            :>> crud = (CrudKind::create, CrudKind::read, CrudKind::update, CrudKind::delete, CrudKind::list);
            :>> allowedRoles = (AppRoles::clerk, AppRoles::admin);
        }
        #Exposed action cancelOrder : CancelOrder {
            :>> allowedRoles = (AppRoles::admin);
        }
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
        #View part cancelOrderForm {
            doc /* The form that cancels an order. */
            :>> kind = ViewKind::form;
            ref :>> operation : CancelOrder;
            :>> allowedRoles = (AppRoles::admin);
        }
        :>> navigation = (orderList);
    }
    satisfy manageOrderData by orderWeb;
    satisfy showOrdersOnWeb by orderWeb;
    satisfy cancelOrderOnWeb by orderWeb;

    // Infrastructure layer: logical part
    #Network part network;
    #ContainerService part webService;
    #RelationalDatabase part orderDb;
    #UserDirectory part users;
    #SecretStore part secrets;
    #Uses dependency from webService to orderDb;
    #Uses dependency from webService to users;
    #Uses dependency from webService to secrets;
    allocate orderWeb to webService;

    // Infrastructure layer: AWS part
    #AwsVpc part networkAws;
    #AwsEcsService part webServiceAws { :>> cpu default = 512; :>> memory default = 1024; :>> desiredCount default = 1; }
    #AwsRdsPostgres part orderDbAws { :>> instanceClass default = "db.t4g.micro"; :>> multiAz default = false; }
    #AwsCognito part usersAws;
    #AwsSecrets part secretsAws;
    #Realizes dependency from networkAws to network;
    #Realizes dependency from webServiceAws to webService;
    #Realizes dependency from orderDbAws to orderDb;
    #Realizes dependency from usersAws to users;
    #Realizes dependency from secretsAws to secrets;

    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "web.dev.example.com"; }
    #Environment part staging { :>> accountId = "333333333333"; :>> region = "eu-west-1"; :>> domain = "web.staging.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "web.example.com";
        #Override part webServiceProd :> webServiceAws { :>> desiredCount = 3; }
        #Override part orderDbProd :> orderDbAws { :>> multiAz = true; }
    }
    satisfy orderDataSafe by prod.orderDbProd;

    // Verification layer. The tests of milestone M11 do not exist yet. Thus
    // the requirements stay "approved" until these test files exist.
    #Verification verification <'V-001'> orderDataTest {
        :>> title = "Order API test";
        :>> method = VerificationMethod::test;
        :>> testFiles = ("apps/order-web/tests/api/orders.test.ts");
        objective { verify manageOrderData; }
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
        :>> testFiles = ("apps/order-web/tests/pages/pages.test.tsx");
        objective { verify showOrdersOnWeb; }
    }
    #Verification verification <'V-004'> cancelOrderTest {
        :>> title = "Cancel order form and API test";
        :>> method = VerificationMethod::test;
        :>> testFiles = ("apps/order-web/tests/features/features.test.tsx", "apps/order-web/tests/api/cancel-order.test.ts");
        objective { verify cancelOrderOnWeb; }
    }
}
