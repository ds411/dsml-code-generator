// Test model of story #60: STR-008 rejects this model.
// The operation Ping has no method and no path. Pong has an empty path.
package Str008Reject {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Operation action def Ping {
        in text : String;
    }
    #Operation action def Pong {
        in text : String;
        :>> method = HttpMethod::get;
        :>> path = "";
    }
}
