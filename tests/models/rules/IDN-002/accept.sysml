// Test model of story #66: IDN-002 accepts this model.
// The requirement 'R-001' has a new doc comment, but the same qualified name.
package IdnQualifiedNames {
    private import DSML::*;

    #Need concern <'N-001'> trackOrders {
        subject;
    }

    #Requirement requirement <'R-001'> getOrderStatus {
        doc /* The API must return the status of an order. */
        frame trackOrders;
    }
}
