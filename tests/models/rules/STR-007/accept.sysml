// Test model of story #60: STR-007 accepts this model.
// Each field has a supported type.
package Str007Accept {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    enum def Colour { red; green; }
    #Entity part def Item {
        #Key attribute id : Uuid [1];
        attribute name : String [1];
        attribute count : Integer [1];
        attribute active : Boolean [1];
        attribute weight : Real [0..1];
        attribute price : Decimal [1];
        attribute madeOn : Date [0..1];
        attribute changedAt : DateTime [0..1];
        attribute colour : Colour [1];
    }
}
