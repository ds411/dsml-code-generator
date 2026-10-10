// Test model of story #13: an attribute that the base type of the keyword
// does not have. "colour" on line 6 does not resolve.
package UnknownAttribute {
    private import DSML::*;

    #Application part orderApi { :>> colour = 1; }
}
