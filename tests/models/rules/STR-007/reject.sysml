// Test model of story #60: STR-007 rejects this model.
// The field count has the type Natural. The field other has no type.
package Str007Reject {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Entity part def Item {
        #Key attribute id : Uuid [1];
        attribute count : Natural [1];
        attribute other;
    }
}
