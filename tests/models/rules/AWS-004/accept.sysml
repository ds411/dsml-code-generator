// Test model of story #64: AWS-004 accepts this model.
// The database has multiAz = false in dev, but multiAz = true in prod.
package Aws004Accept {
    private import DSML::*;

    #AwsRdsPostgres part orderDb { :>> multiAz default = false; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "dev.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "example.com";
        #Override part orderDbProd :> orderDb { :>> multiAz = true; }
    }
}
