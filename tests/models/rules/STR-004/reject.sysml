// Test model of story #59: STR-004 rejects this model.
// Two stakeholders in different packages have the short name S-001.
package Str004Reject {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    package Sales {
        #Stakeholder part def <'S-001'> ShopOwner;
    }
    package Support {
        #Stakeholder part def <'S-001'> Clerk;
    }
}
