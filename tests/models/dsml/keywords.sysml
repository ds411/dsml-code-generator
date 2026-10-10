// Test model of story #13: one use of each keyword of the DSML library.
// OpenSysML must parse and resolve it with the library and give no
// diagnostic. The tests also check that each keyword of an element kind
// gives its base type.
package Keywords {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }

    // Needs and requirements layers
    #Stakeholder part def Owner;
    part owner : Owner;

    #Need concern <'N-001'> trackOrders {
        doc /* The owner must see the status of each order. */
        :>> title = "Track orders";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        stakeholder s : Owner;
    }

    #Requirement requirement <'R-001'> getOrder {
        doc /* The API must return an order. */
        :>> title = "Get order";
        :>> kind = RequirementKind::constraint;
        :>> priority = Priority::should;
        :>> status = Status::draft;
        :>> rationale = "The owner reads orders.";
        frame trackOrders;
    }

    // Application layer
    #Roles enum def AppRoles { clerk; admin; }

    #Entity #Destructive part def Order {
        #Key attribute id : Uuid [1];
        attribute total : Decimal [1] { @FieldRules { minValue = 0; precision = 10; scale = 2; } }
        attribute placed : Date [1];
        attribute changed : DateTime [0..1];
        attribute note : String [0..1] {
            @FieldRules { maxLength = 500; pattern = "^[a-z]*$"; unique = false; }
            @Destructive { renamedFrom = "comment"; }
        }
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
            :>> allowedRoles = AppRoles::admin;
        }
    }
    #Application part orderWeb { :>> target = Target::react; }
    #Calls dependency from orderWeb to orderApi;

    // Infrastructure layer: logical part
    #Network part network;
    #ContainerService part apiService;
    #RelationalDatabase part orderDb;
    #UserDirectory part users;
    #SecretStore part secrets;
    #Uses dependency from apiService to orderDb;

    // Infrastructure layer: AWS part
    #AwsVpc part networkAws { :>> natGatewayCount default = 1; }
    #AwsEcsService part apiServiceAws {
        :>> cpu = 512;
        :>> memory = 1024;
        :>> desiredCount default = 1;
        :>> minCount = 1;
        :>> maxCount = 4;
    }
    #AwsRdsPostgres part orderDbAws { :>> instanceClass = "db.t4g.micro"; :>> multiAz default = false; }
    #AwsCognito part usersAws;
    #AwsSecrets part secretsAws;
    #Realizes dependency from orderDbAws to orderDb;

    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "orders.example.com";
        #Override part orderDbProd :> orderDbAws { :>> multiAz = true; }
    }

    // Verification layer
    #Verification verification <'V-001'> orderTest {
        :>> title = "Order API test";
        :>> method = VerificationMethod::test;
        :>> testFiles = "app/features/order/read_order/test_endpoint.py";
        :>> testCases = "test_endpoint.py::test_read";
        objective { verify getOrder; }
    }

    part legacy { @Waiver { rule = "COV-003"; reason = "Old part."; owner = "ops"; expires = "2027-01-31"; } }
}
