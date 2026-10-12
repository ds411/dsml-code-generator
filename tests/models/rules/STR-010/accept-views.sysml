// Test model of story #161: STR-010 accepts this model.
// The list view has allowedRoles. The detail view is public.
package Str010Accept {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 1; }
    #Roles enum def AppRoles { clerk; }
    #Entity part def Order { #Key attribute id : Uuid [1]; }
    #Application part portal {
        :>> target = Target::react;
        #View part orderList {
            :>> kind = ViewKind::list;
            ref :>> entity : Order;
            :>> allowedRoles = (AppRoles::clerk);
        }
        #View part orderDetail {
            :>> kind = ViewKind::detail;
            ref :>> entity : Order;
            :>> 'public' = true;
        }
    }
}
