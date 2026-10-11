// Test model of story #64: AWS-002 accepts this model.
// The tests permit the Regions eu-central-1 and eu-west-1.
package Aws002Accept {
    private import DSML::*;

    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-central-1"; :>> domain = "dev.example.com"; }
    #Environment part prod { :>> accountId = "444444444444"; :>> region = "eu-west-1"; :>> domain = "example.com"; }
}
