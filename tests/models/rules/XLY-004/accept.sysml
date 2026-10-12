// Test model of stories #63 and #161: XLY-004 accepts this model.
// The static site of the react application uses no database.
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

    #Application part orderPortal {
        :>> target = Target::react;
        #View part orderList {
            :>> kind = ViewKind::list;
            ref :>> entity : Order;
            :>> allowedRoles = (AppRoles::clerk);
        }
    }

    #ContainerService part apiService;
    #StaticSite part portalSite;
    #RelationalDatabase part orderDb;
    #UserDirectory part users;
    #Uses dependency from apiService to orderDb;
    #Uses dependency from apiService to users;
    #Uses dependency from portalSite to users;
    #Calls dependency from orderPortal to orderApi;
    allocate orderApi to apiService;
    allocate orderPortal to portalSite;
    #AwsStaticSite part portalSiteAws;
    #Realizes dependency from portalSiteAws to portalSite;

    #AwsEcsService part apiServiceAws;
    #AwsRdsPostgres part orderDbAws;
    #AwsCognito part usersAws;
    #Realizes dependency from apiServiceAws to apiService;
    #Realizes dependency from orderDbAws to orderDb;
    #Realizes dependency from usersAws to users;
}
