// Test model of story #66: IDN-003 rejects this model.
// Line 8 gives the entity a new name. Thus the qualified names of the
// entity and of its attribute change.
package IdnNoShortNames {
    private import DSML::*;
    private import ScalarValues::*;

    #Entity part def Purchase {
        #Key attribute id : String [1];
    }
}
