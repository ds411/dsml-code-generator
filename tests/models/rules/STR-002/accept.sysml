// Test model of story #59: STR-002 accepts this model.
// The need, the requirement and the verification have all their mandatory attributes.
package Str002Accept {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def ShopOwner;

    #Need concern <'N-001'> trackOrders {
        doc /* The shop owner must see the status of each order. */
        :>> title = "Track orders";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder owner : ShopOwner;
    }

    #Requirement requirement <'R-001'> getOrderStatus {
        doc /* The API must return the status of an order. */
        :>> title = "Get order status";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame trackOrders;
    }

    #Verification verification <'V-001'> orderStatusTest {
        :>> title = "Order status API test";
        :>> method = VerificationMethod::inspection;
        objective { verify getOrderStatus; }
    }
}
