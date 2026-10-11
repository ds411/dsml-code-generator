// Test model of story #66: the baseline of the IDN-002 tests.
package IdnQualifiedNames {
    private import DSML::*;

    #Need concern <'N-001'> trackOrders {
        subject;
    }

    #Requirement requirement <'R-001'> getOrderStatus {
        frame trackOrders;
    }
}
