// Test model of story #59: STR-003 rejects this model.
// The need ID has two digits. The requirement ID has the prefix of a need.
// The verification ID is in lower case.
package Str003Reject {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def ShopOwner;

    #Need concern <'N-01'> trackOrders {
        subject;
        stakeholder owner : ShopOwner;
    }

    #Requirement requirement <'N-002'> getOrderStatus {
        frame trackOrders;
    }

    #Verification verification <'v-001'> orderStatusTest {
        objective { verify getOrderStatus; }
    }
}
