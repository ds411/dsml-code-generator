// Test model of story #64: AWS-001 accepts this model.
// Each environment has its own account with 12 digits.
package Aws001Accept {
    private import DSML::*;

    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "dev.example.com"; }
    #Environment part staging { :>> accountId = "333333333333"; :>> region = "eu-west-1"; :>> domain = "staging.example.com"; }
    #Environment part prod { :>> accountId = "444444444444"; :>> region = "eu-west-1"; :>> domain = "example.com"; }
}
