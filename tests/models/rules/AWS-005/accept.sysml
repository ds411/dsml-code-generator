// Test model of story #64: AWS-005 accepts this model.
// The service has minCount = 1 in dev, but minCount = 2 in prod.
package Aws005Accept {
    private import DSML::*;

    #AwsEcsService part api { :>> minCount default = 1; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "dev.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "example.com";
        #Override part apiProd :> api { :>> minCount = 2; }
    }
}
