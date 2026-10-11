// Test model of story #64: AWS-004 rejects this model.
// The override in prod sets multiAz = false.
package Aws004Reject {
    private import DSML::*;

    #AwsRdsPostgres part orderDb { :>> multiAz default = true; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "dev.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "example.com";
        #Override part orderDbProd :> orderDb { :>> multiAz = false; }
    }
}
