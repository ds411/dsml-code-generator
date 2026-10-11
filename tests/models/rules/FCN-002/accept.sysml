// Test model of story #65: FCN-002 accepts this model.
// Each feature of the formal constraint of R-001 has a value in each
// environment.
package FcnAccept {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #RelationalDatabase part db;
    #ContainerService part api;
    #AwsRdsPostgres part dbAws { :>> instanceClass default = "db.r6g.large"; }
    #AwsEcsService part apiAws { :>> memory default = 2048; }
    #Realizes dependency from dbAws to db;
    #Realizes dependency from apiAws to api;

    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "dev.store.example.com"; }
    #Environment part prod { :>> accountId = "444444444444"; :>> region = "eu-west-1"; :>> domain = "store.example.com"; }

    #Requirement requirement <'R-001'> capacity {
        doc /* The database and the API must have sufficient capacity. */
        require constraint { dbAws.instanceClass == "db.r6g.large" and apiAws.memory >= 1024 }
    }
}
