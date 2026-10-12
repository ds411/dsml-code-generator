// A test model for the conversion of the views, the navigation and the
// static site (story #159). The navigation does not use the order of the
// declarations, so a test can make sure that the IR keeps the order of the
// model.
package Portal {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 1; }

    #Roles enum def PortalRoles { clerk; admin; }

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
            :>> allowedRoles = PortalRoles::clerk;
        }
        #Exposed action placeOrder : PlaceOrder {
            :>> allowedRoles = PortalRoles::clerk;
        }
    }

    #Application part orderPortal {
        :>> target = Target::react;
        #View part orderList {
            doc /* The list of the orders. */
            :>> kind = ViewKind::list;
            ref :>> entity : Order;
            :>> 'public' = true;
        }
        #View part orderDetail {
            :>> kind = ViewKind::detail;
            ref :>> entity : Order;
            :>> allowedRoles = (PortalRoles::clerk, PortalRoles::admin);
        }
        #View part placeOrderForm {
            :>> kind = ViewKind::form;
            ref :>> operation : PlaceOrder;
            :>> allowedRoles = PortalRoles::clerk;
        }
        :>> navigation = (placeOrderForm, orderList, orderDetail);
    }
    #Calls dependency from orderPortal to orderApi;

    #Application part adminPortal {
        :>> target = Target::react;
        #View part orderAdmin {
            :>> kind = ViewKind::list;
            ref :>> entity : Order;
            :>> allowedRoles = PortalRoles::admin;
        }
        :>> navigation = orderAdmin;
    }
    #Calls dependency from adminPortal to orderApi;

    #ContainerService part apiService;
    #StaticSite part portalSite;
    #StaticSite part adminSite;
    #UserDirectory part users;
    #Uses dependency from portalSite to users;
    #Uses dependency from adminSite to users;
    allocate orderApi to apiService;
    allocate orderPortal to portalSite;
    allocate adminPortal to adminSite;

    #AwsEcsService part apiServiceAws;
    #AwsStaticSite part portalSiteAws;
    #AwsStaticSite part adminSiteAws;
    #AwsCognito part usersAws;
    #Realizes dependency from apiServiceAws to apiService;
    #Realizes dependency from portalSiteAws to portalSite;
    #Realizes dependency from adminSiteAws to adminSite;
    #Realizes dependency from usersAws to users;
}
