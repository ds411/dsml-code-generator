// Test model of story #60: STR-008 accepts this model.
// The custom operation has a method and a path.
package Str008Accept {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Operation action def CancelOrder {
        in orderId : Uuid;
        :>> method = HttpMethod::post;
        :>> path = "/orders/{orderId}/cancel";
    }
}
