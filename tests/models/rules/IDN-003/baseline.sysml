// Test model of story #66: the baseline of the IDN-003 tests.
// The entity has no short name. Its qualified name is its identity.
package IdnNoShortNames {
    private import DSML::*;
    private import ScalarValues::*;

    #Entity part def Order {
        #Key attribute id : String [1];
    }
}
