// Test model of story #60: STR-012 accepts this model.
// The overrides change only attributes on the list of PRD-DSML-042.
package Str012Accept {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 0; }
    #AwsEcsService part apiAws { :>> cpu default = 512; :>> memory default = 1024; :>> desiredCount default = 1; }
    #AwsRdsPostgres part dbAws { :>> instanceClass default = "db.t4g.micro"; :>> multiAz default = false; }
    #Environment part prod {
        #Override part apiProd :> apiAws { :>> cpu = 1024; :>> memory = 2048; :>> desiredCount = 3; }
        #Override part dbProd :> dbAws { :>> instanceClass = "db.m7g.large"; :>> multiAz = true; }
    }
}
