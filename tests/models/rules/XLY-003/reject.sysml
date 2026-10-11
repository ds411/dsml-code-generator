// Test model of story #63: XLY-003 rejects this model.
// The database orderDb has no AWS realization, and the user directory has two.
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
    allocate orderApi to apiService;

    #AwsEcsService part apiServiceAws;
    #AwsRdsPostgres part orderDbAws;
    #AwsCognito part usersAws;
    #Realizes dependency from apiServiceAws to apiService;
    #Realizes dependency from usersAws to users;
    #AwsCognito part usersAws2;
    #Realizes dependency from usersAws2 to users;
}
