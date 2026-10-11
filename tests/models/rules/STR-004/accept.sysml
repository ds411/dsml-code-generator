// Test model of story #59: STR-004 accepts this model.
// Each short name is unique in the model.
package Str004Accept {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    package Sales {
        #Stakeholder part def <'S-001'> ShopOwner;
    }
    package Support {
        #Stakeholder part def <'S-002'> Clerk;
    }
}
