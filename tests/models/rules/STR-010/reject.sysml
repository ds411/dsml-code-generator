// Test model of story #60: STR-010 rejects this model.
// The exposed entity orders and the exposed operation ping have no
// allowedRoles and are not public.
package Str010Reject {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Entity part def Order { #Key attribute id : Uuid [1]; }
    #Operation action def Ping {
        out text : String;
        :>> method = HttpMethod::get;
        :>> path = "/ping";
    }
    #Application part api {
        :>> target = Target::fastapi;
        #Exposed part orders : Order [*] {
            :>> crud = (CrudKind::read);
        }
        #Exposed action ping : Ping;
    }
}
