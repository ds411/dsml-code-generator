// Test model of story #63: XLY-004 rejects this model.
// The react application is allocated to a service that uses a database.
package XlyReject {
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

    #ContainerService part apiService;
    #RelationalDatabase part orderDb;
    #UserDirectory part users;
    #Uses dependency from apiService to orderDb;
    #Uses dependency from apiService to users;

    #AwsEcsService part apiServiceAws;
    #AwsRdsPostgres part orderDbAws;
    #AwsCognito part usersAws;
    #Realizes dependency from apiServiceAws to apiService;
    #Realizes dependency from orderDbAws to orderDb;
    #Realizes dependency from usersAws to users;

    #Application part orderWeb { :>> target = Target::react; }
    #Calls dependency from orderWeb to orderApi;
    allocate orderWeb to apiService;
}
