// Test model of story #60: STR-010 accepts this model.
// The exposed entity has allowedRoles. The exposed operation is public.
package Str010Accept {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Roles enum def AppRoles { clerk; }
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
            :>> allowedRoles = (AppRoles::clerk);
        }
        #Exposed action ping : Ping { :>> 'public' = true; }
    }
}
