// Test model of story #66: the baseline of the IDN-001 tests.
// The short name 'R-001' is the short name of a requirement.
package IdnShortNames {
    private import DSML::*;

    #Need concern <'N-001'> trackOrders {
        subject;
    }

    #Requirement requirement <'R-001'> getOrderStatus {
        frame trackOrders;
    }
}
