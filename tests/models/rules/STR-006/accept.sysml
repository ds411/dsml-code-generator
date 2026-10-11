// Test model of story #60: STR-006 accepts this model.
// The entity has one #Key field.
package Str006Accept {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Entity part def Order {
        #Key attribute id : Uuid [1];
        attribute note : String [0..1];
    }
}
