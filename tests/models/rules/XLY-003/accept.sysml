// Test model of story #63: XLY-003 accepts this model.
// Each logical element has one AWS realization of the correct kind.
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
    #Realizes dependency from orderDbAws to orderDb;
    #Realizes dependency from usersAws to users;
}
