// Test model of story #64: AWS-002 rejects this model.
// The tests permit the Regions eu-central-1 and eu-west-1. The tooling
// account and prod use the Region us-east-1.
package Aws002Reject {
    private import DSML::*;

    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "us-east-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-central-1"; :>> domain = "dev.example.com"; }
    #Environment part prod { :>> accountId = "444444444444"; :>> region = "us-east-1"; :>> domain = "example.com"; }
}
