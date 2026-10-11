// A test model for the conversion of the application, infrastructure and
// verification layers (story #31). It uses the forms that the example model
// does not use.
package Shop {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Requirement requirement <'R-010'> listProducts {
        doc /* The API must list the products. */
        :>> title = "List products";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
    }

    #Roles enum def ShopRoles { buyer; }

    #Entity part def Category {
        #Key attribute code : String [1];
    }

    #Entity part def Product {
        doc /* A product that the shop sells. */
        #Key attribute id : Uuid [1];
        attribute name : String [1] { @FieldRules { minLength = 1; maxLength = 80; pattern = "^[A-Z]"; } }
        attribute price : Decimal [1] { @FieldRules { precision = 10; scale = 2; } }
        attribute label : String [0..1] { @Destructive { renamedFrom = "title"; } }
        ref category : Category [0..1];
        ref related : Product [*];
    }

    #Operation action def Restock {
        in productId : Uuid;
        inout amount : Integer;
        out product : Product;
        :>> method = HttpMethod::put;
        :>> path = "/products/{productId}/stock";
    }

    #Application part shopApi {
        :>> target = Target::fastapi;
        #Exposed part products : Product [*] {
            :>> crud = (CrudKind::update, CrudKind::delete);
            :>> 'public' = true;
        }
        #Exposed action restock : Restock {
            :>> allowedRoles = (ShopRoles::buyer);
        }
    }
    #Application part shopWeb {
        :>> target = Target::react;
    }
    #Calls dependency from shopWeb to shopApi;
    satisfy listProducts by shopApi;

    #Network part net;
    #ContainerService part api;
    #SecretStore part secrets;
    #Uses dependency from api to secrets;
    allocate shopApi to api;

    #AwsVpc part netAws { :>> natGatewayCount default = 1; }
    #AwsEcsService part apiAws { :>> cpu default = 256; :>> memory default = 512; :>> desiredCount default = 2; }
    #AwsSecrets part secretsAws;
    #Realizes dependency from netAws to net;
    #Realizes dependency from apiAws to api;
    #Realizes dependency from secretsAws to secrets;
    satisfy listProducts by apiAws;

    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "us-east-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "us-east-1"; :>> domain = "dev.shop.example.com"; }
    #Environment part prod {
        :>> accountId = "333333333333";
        :>> region = "us-east-1";
        :>> domain = "shop.example.com";
        #Override part netProd :> netAws { :>> natGatewayCount = 2; }
        #Override part apiProd :> apiAws { :>> cpu = 1024; :>> memory = 2048; }
    }

    #Verification verification <'V-010'> listProductsTest {
        :>> title = "List products test";
        :>> method = VerificationMethod::test;
        :>> testFiles = ("tests/test_products.py", "tests/test_catalog.py");
        :>> testCases = ("tests/test_products.py::test_list");
        objective { verify listProducts; }
    }
}
