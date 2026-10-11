// Test model of story #59: STR-001 rejects this model.
// The toolchain does not support the DSML version 2.0.
package Str001RejectVersion {
    private import DSML::*;
    @DsmlVersion { major = 2; minor = 0; }

    #Stakeholder part def ShopOwner;
}
