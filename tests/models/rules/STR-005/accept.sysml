// Test model of story #60: STR-005 accepts this model.
// Each application has a target that the toolchain knows.
package Str005Accept {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Application part api { :>> target = Target::fastapi; }
    #Application part web { :>> target = Target::react; }
}
