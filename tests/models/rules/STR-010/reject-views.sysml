// Test model of story #161: STR-010 rejects this model.
// The list view has no allowedRoles and is not public.
package Str010Reject {
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
        }
        #View part orderDetail {
            :>> kind = ViewKind::detail;
            ref :>> entity : Order;
            :>> allowedRoles = (AppRoles::clerk);
        }
    }
}
