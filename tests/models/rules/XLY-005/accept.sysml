// Test model of story #63: XLY-005 accepts this model.
// The react application calls the API application with #Calls.
package XlyAccept {
    private import DSML::*;
    private import ScalarValues::*;

    #Roles enum def AppRoles { clerk; }
    #Entity part def Order { #Key attribute id : Uuid [1]; }

    #Application part orderApi {
        :>> target = Target::fastapi;
        #Exposed part orders : Order [*] {
            :>> crud = (CrudKind::read);
            :>> allowedRoles = (AppRoles::clerk);
        }
    }

    #Application part orderWeb { :>> target = Target::react; }
    #Calls dependency from orderWeb to orderApi;
}
