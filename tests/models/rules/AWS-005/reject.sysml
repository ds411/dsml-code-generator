// Test model of story #64: AWS-005 rejects this model.
// prod has no override, thus the service has the default minCount = 1 in prod.
package Aws005Reject {
    private import DSML::*;

    #AwsEcsService part api { :>> minCount default = 1; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "dev.example.com"; }
    #Environment part prod { :>> accountId = "444444444444"; :>> region = "eu-west-1"; :>> domain = "example.com"; }
}
