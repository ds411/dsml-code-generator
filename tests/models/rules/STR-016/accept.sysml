// Test model of story #59: STR-016 accepts this model.
// The logical database has no AWS attribute. Its AWS realization holds the
// AWS attributes.
package Str016Accept {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }

    #RelationalDatabase part orderDb {
        attribute purpose : String = "orders";
    }
    #AwsRdsPostgres part orderDbAws {
        :>> instanceClass = "db.t4g.micro";
    }
    #Realizes dependency from orderDbAws to orderDb;
}
