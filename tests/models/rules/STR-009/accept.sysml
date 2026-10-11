// Test model of story #60: STR-009 accepts this model.
// Each operation of an application has a different method or path.
// The application admin has the same paths, but it is a different application.
package Str009Accept {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Roles enum def AppRoles { clerk; }
    #Entity part def Order { #Key attribute id : Uuid [1]; }
    #Operation action def CancelOrder {
        in orderId : Uuid;
        :>> method = HttpMethod::post;
        :>> path = "/orders/{orderId}/cancel";
    }
    #Application part api {
        :>> target = Target::fastapi;
        #Exposed part orders : Order [*] {
            :>> crud = (CrudKind::create, CrudKind::read, CrudKind::update, CrudKind::delete, CrudKind::list);
            :>> allowedRoles = (AppRoles::clerk);
        }
        #Exposed action cancelOrder : CancelOrder { :>> allowedRoles = (AppRoles::clerk); }
    }
    #Application part admin {
        :>> target = Target::fastapi;
        #Exposed part orders : Order [*] {
            :>> crud = (CrudKind::read);
            :>> allowedRoles = (AppRoles::clerk);
        }
    }
}
