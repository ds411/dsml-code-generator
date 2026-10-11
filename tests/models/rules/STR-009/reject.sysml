// Test model of story #60: STR-009 rejects this model.
// The custom operation GetOrder has the default method and path of the CRUD
// operation read: GET /orders/{id}. Only the names of the parameters are different.
package Str009Reject {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #Roles enum def AppRoles { clerk; }
    #Entity part def Order { #Key attribute id : Uuid [1]; }
    #Operation action def GetOrder {
        in orderId : Uuid;
        :>> method = HttpMethod::get;
        :>> path = "/orders/{orderId}";
    }
    #Application part api {
        :>> target = Target::fastapi;
        #Exposed part orders : Order [*] {
            :>> crud = (CrudKind::read, CrudKind::list);
            :>> allowedRoles = (AppRoles::clerk);
        }
        #Exposed action getOrder : GetOrder { :>> allowedRoles = (AppRoles::clerk); }
    }
}
