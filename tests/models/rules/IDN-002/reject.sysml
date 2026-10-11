// Test model of story #66: IDN-002 rejects this model.
// Line 10 gives the requirement 'R-001' a new name, thus a new qualified name.
package IdnQualifiedNames {
    private import DSML::*;

    #Need concern <'N-001'> trackOrders {
        subject;
    }

    #Requirement requirement <'R-001'> getStatus {
        frame trackOrders;
    }
}
