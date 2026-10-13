package LoanInfrastructure {
    private import DSML::*;
    private import LoanApplication::*;

    // Logical part
    #Network part network;
    #ContainerService part apiService;
    #RelationalDatabase part loanDb;
    #UserDirectory part users;
    #Uses dependency from apiService to loanDb;
    #Uses dependency from apiService to users;
    allocate loanApi to apiService;

    // AWS part
    #AwsVpc part networkAws;
    #AwsEcsService part apiServiceAws { :>> cpu default = 256; :>> memory default = 512; :>> desiredCount default = 1; }
    #AwsRdsPostgres part loanDbAws { :>> instanceClass default = "db.t4g.micro"; :>> multiAz default = false; }
    #AwsCognito part usersAws;
    #Realizes dependency from networkAws to network;
    #Realizes dependency from apiServiceAws to apiService;
    #Realizes dependency from loanDbAws to loanDb;
    #Realizes dependency from usersAws to users;

    // Accounts and environments
    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "library.dev.example.com"; }
    #Environment part staging { :>> accountId = "333333333333"; :>> region = "eu-west-1"; :>> domain = "library.staging.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "library.example.com";
        #Override part apiServiceProd :> apiServiceAws { :>> desiredCount = 2; :>> minCount = 2; }
        #Override part loanDbProd :> loanDbAws { :>> multiAz = true; }
    }
}
