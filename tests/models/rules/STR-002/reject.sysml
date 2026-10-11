// Test model of story #59: STR-002 rejects this model.
// The need has no short name and no priority. The requirement has no text
// and no kind. The verification has no method.
package Str002Reject {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def ShopOwner;

    #Need concern trackOrders {
        doc /* The shop owner must see the status of each order. */
        :>> title = "Track orders";
        :>> status = Status::approved;
        subject;
        stakeholder owner : ShopOwner;
    }

    #Requirement requirement <'R-001'> getOrderStatus {
        :>> title = "Get order status";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame trackOrders;
    }

    #Verification verification <'V-001'> orderStatusTest {
        :>> title = "Order status API test";
        objective { verify getOrderStatus; }
    }
}
