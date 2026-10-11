// Test model of story #64: AWS-003 accepts this model.
// Fargate accepts each pair of cpu and memory, also the pair of the override.
package Aws003Accept {
    private import DSML::*;

    #AwsEcsService part small { :>> cpu default = 256; :>> memory default = 512; }
    #AwsEcsService part large { :>> cpu default = 512; :>> memory default = 1024; }
    #AwsEcsService part noSize;
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "dev.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "example.com";
        #Override part largeProd :> large { :>> cpu = 4096; :>> memory = 30720; }
    }
}
