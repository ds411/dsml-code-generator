// Test model of story #64: AWS-003 rejects this model.
// The default pair of "small" is not valid. The pair of "large" in prod is
// not valid, because the override changes the memory to 512.
package Aws003Reject {
    private import DSML::*;

    #AwsEcsService part small { :>> cpu default = 256; :>> memory default = 4096; }
    #AwsEcsService part large { :>> cpu default = 512; :>> memory default = 1024; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "dev.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "example.com";
        #Override part largeProd :> large { :>> memory = 512; }
    }
}
