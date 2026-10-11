// Test model of story #66: IDN-001 rejects this model.
// The model removes the requirement 'R-001'. Line 11 uses its short name
// again for a need.
package IdnShortNames {
    private import DSML::*;

    #Need concern <'N-001'> trackOrders {
        subject;
    }

    #Need concern <'R-001'> cancelOrders {
        subject;
    }
}
