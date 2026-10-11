// Test model of story #60: STR-005 rejects this model.
// The application web has no target.
package Str005Reject {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Application part api { :>> target = Target::fastapi; }
    #Application part web;
}
