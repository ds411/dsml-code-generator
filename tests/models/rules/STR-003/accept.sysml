// Test model of story #59: STR-003 accepts this model.
// Each short name agrees with the default ID pattern of its kind.
package Str003Accept {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def <'S1'> ShopOwner;

    #Need concern <'N-001'> trackOrders {
        subject;
        stakeholder owner : ShopOwner;
    }

    #Requirement requirement <'R-1000'> getOrderStatus {
        frame trackOrders;
    }

    #Verification verification <'V-012'> orderStatusTest {
        objective { verify getOrderStatus; }
    }
}
