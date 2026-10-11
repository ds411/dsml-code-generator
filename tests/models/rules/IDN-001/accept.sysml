// Test model of story #66: IDN-001 accepts this model.
// The model removes the requirement 'R-001'. The new need uses the new
// short name 'N-002'.
package IdnShortNames {
    private import DSML::*;

    #Need concern <'N-001'> trackOrders {
        subject;
    }

    #Need concern <'N-002'> cancelOrders {
        subject;
    }
}
