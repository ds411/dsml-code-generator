// Test model of story #157: STR-001 rejects this model.
// The root package gives the DSML version 1.2. The library has 1.1.0.
package Str001RejectMinor2 {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 2; }

    #Stakeholder part def ShopOwner;
}
