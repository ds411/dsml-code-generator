// Test model of story #59: STR-016 rejects this model.
// The logical database has the AWS attribute instanceClass. The logical
// container service has the AWS attribute awsLogGroup.
package Str016Reject {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }

    #RelationalDatabase part orderDb {
        attribute instanceClass : String = "db.t4g.micro";
    }
    #ContainerService part apiService {
        attribute awsLogGroup : String = "api";
        attribute purpose : String = "orders";
    }
}
