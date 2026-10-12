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
    satisfy orderDataSafe by prod::orderDbProd;

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
