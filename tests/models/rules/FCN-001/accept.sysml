// Test model of story #65: FCN-001 accepts this model.
// The formal constraint of R-001 is true in each environment.
package FcnAccept {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #RelationalDatabase part db;
    #AwsRdsPostgres part dbAws { :>> multiAz default = true; }
    #Realizes dependency from dbAws to db;

    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "dev.store.example.com"; }
    #Environment part prod { :>> accountId = "444444444444"; :>> region = "eu-west-1"; :>> domain = "store.example.com"; }

    #Requirement requirement <'R-001'> dataSafe {
        doc /* The order data must stay available if one zone fails. */
        require constraint { dbAws.multiAz == true }
    }
}
