// Test model of story #66: IDN-003 accepts this model.
// The entity keeps its qualified name. The model adds a new entity.
package IdnNoShortNames {
    private import DSML::*;
    private import ScalarValues::*;

    #Entity part def Order {
        #Key attribute id : String [1];
    }

    #Entity part def Customer {
        #Key attribute email : String [1];
    }
}
