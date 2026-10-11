// Test model of story #60: STR-011 rejects this model.
// The environment staging is missing. The environment prod has no Region
// and no domain.
package Str011Reject {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "dev.example.com"; }
    #Environment part prod { :>> accountId = "444444444444"; }
}
