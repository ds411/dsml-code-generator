// A test model for the evaluation of the formal constraints (story #32).
// The constraints give "true", "false" and "unknown" results. The "prod"
// environment changes attributes of the AWS realizations, so some results
// are different in "dev" and in "prod".
package Store {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #RelationalDatabase part db;
    #ContainerService part api;
    // `instanceClass` and `memory` have no value in the realizations.
    #AwsRdsPostgres part dbAws { :>> instanceClass; :>> multiAz default = false; }
    #AwsEcsService part apiAws { :>> cpu default = 256; :>> memory; :>> desiredCount default = 1; }
    #Realizes dependency from dbAws to db;
    #Realizes dependency from apiAws to api;

    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "dev.store.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "store.example.com";
        #Override part dbProd :> dbAws { :>> multiAz = true; :>> instanceClass = "db.r6g.large"; }
    }

    #Requirement requirement <'R-020'> dataSafe {
        doc /* The order data must stay available if one zone fails. */
        :>> title = "Data safety";
        :>> kind = RequirementKind::'constraint';
        :>> priority = Priority::must;
        :>> status = Status::approved;
        // 1: "false" in dev and "true" in prod, because prod changes multiAz.
        require constraint { dbAws.multiAz == true }
        // 2: "unknown" in dev, with two features that have no value. In prod,
        // only apiAws.memory has no value.
        require constraint {
            dbAws.instanceClass == "db.r6g.large" and apiAws.memory >= 1024 // memory in MiB
        }
        // An assumption is not a formal constraint of the requirement.
        assume constraint { apiAws.desiredCount >= 1 }
        // 3: "true" in all environments. The chain names the environment.
        require constraint { prod.dbProd.multiAz == true }
    }

    #Requirement requirement <'R-021'> enoughCpu {
        doc /* The API must have at least 256 CPU units. */
        :>> title = "CPU units";
        :>> kind = RequirementKind::performance;
        :>> priority = Priority::should;
        :>> status = Status::draft;
        require constraint { Store::apiAws.cpu >= 256 and not (apiAws.cpu > 4096) }
    }
}
