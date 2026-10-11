// Test model of story #64: AWS-001 rejects this model.
// dev uses the tooling account, the account ID of staging has 5 digits,
// and prod and qa use one account.
package Aws001Reject {
    private import DSML::*;

    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part dev { :>> accountId = "111111111111"; :>> region = "eu-west-1"; :>> domain = "dev.example.com"; }
    #Environment part staging { :>> accountId = "12345"; :>> region = "eu-west-1"; :>> domain = "staging.example.com"; }
    #Environment part prod { :>> accountId = "444444444444"; :>> region = "eu-west-1"; :>> domain = "example.com"; }
    #Environment part qa { :>> accountId = "444444444444"; :>> region = "eu-west-1"; :>> domain = "qa.example.com"; }
}
