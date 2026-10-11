// Test model of story #60: STR-012 rejects this model.
// The realization dbAws has the model attribute engine. The override dbProd
// changes it, but engine is not on the list of PRD-DSML-042.
package Str012Reject {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #AwsRdsPostgres part dbAws {
        :>> multiAz default = false;
        attribute engine : String default = "postgres";
    }
    #Environment part prod {
        #Override part dbProd :> dbAws {
            :>> multiAz = true;
            :>> engine = "postgres-16";
        }
    }
}
