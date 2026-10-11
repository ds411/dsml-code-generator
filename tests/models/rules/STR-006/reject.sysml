// Test model of story #60: STR-006 rejects this model.
// The entity Order has no #Key field. The entity Item has two.
package Str006Reject {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Entity part def Order {
        attribute id : Uuid [1];
    }
    #Entity part def Item {
        #Key attribute id : Uuid [1];
        #Key attribute code : String [1];
    }
}
