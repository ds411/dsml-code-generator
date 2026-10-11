// Test model: a usage with a declared type and a keyword. OpenSysML 0.9.2
// gives the features of the keyword base type to the usage, but "istype"
// does not give true for the base type. See docs/notes/dsml-library.md.
package TypedUsage {
    private import DSML::*;

    part def Store;

    #Application part shop : Store {
        :>> target = Target::fastapi;
    }
}
