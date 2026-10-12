// Test model of story #157: the phase 2 keywords of the DSML library 1.1.
// OpenSysML and the OMG pilot implementation must parse and resolve it with
// the library and give no diagnostic. It has a list view, a detail view, a
// form view, a navigation list and a static site.
package PhaseTwo {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 1; }

    // Application layer
    #Roles enum def AppRoles { clerk; admin; }

    #Entity part def Order {
        #Key attribute id : Uuid [1];
        attribute total : Decimal [1];
    }

    #Operation action def PlaceOrder {
        in total : Decimal;
        out order : Order;
        :>> method = HttpMethod::post;
        :>> path = "/orders/place";
    }

    #Application part orderApi {
        :>> target = Target::fastapi;
        #Exposed part orders : Order [*] {
            :>> crud = (CrudKind::read, CrudKind::list);
            :>> allowedRoles = AppRoles::clerk;
        }
        #Exposed action placeOrder : PlaceOrder {
            :>> allowedRoles = AppRoles::clerk;
        }
    }

    #Application part orderPortal {
        :>> target = Target::react;
        #View part orderList {
            :>> kind = ViewKind::list;
            ref :>> entity : Order;
            :>> 'public' = true;
        }
        #View part orderDetail {
            :>> kind = ViewKind::detail;
            ref :>> entity : Order;
            :>> allowedRoles = (AppRoles::clerk, AppRoles::admin);
        }
        #View part placeOrderForm {
            :>> kind = ViewKind::form;
            ref :>> operation : PlaceOrder;
            :>> allowedRoles = AppRoles::clerk;
        }
        :>> navigation = (orderList, orderDetail, placeOrderForm);
    }
    #Calls dependency from orderPortal to orderApi;

    // Infrastructure layer
    #ContainerService part apiService;
    #StaticSite part portalSite;
    #UserDirectory part users;
    #Uses dependency from portalSite to users;
    allocate orderPortal to portalSite;

    #AwsEcsService part apiServiceAws;
    #AwsStaticSite part portalSiteAws;
    #Realizes dependency from portalSiteAws to portalSite;
}
