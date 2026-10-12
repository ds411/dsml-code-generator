package StarterModel {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 1; }

    // Needs layer
    #Stakeholder part def Owner;

    #Need concern <'N-001'> firstNeed {
        doc /* The owner must have a first need. Replace this need with a real need. */
        :>> title = "First need";
        :>> priority = Priority::must;
        :>> status = Status::draft;
        subject;
        stakeholder owner : Owner;
    }

    // Requirements layer
    #Requirement requirement <'R-001'> firstRequirement {
        doc /* The system must satisfy the first need. Replace this requirement with a real requirement. */
        :>> title = "First requirement";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::draft;
        frame firstNeed;
    }

    // Application layer
    #Roles enum def AppRoles { user; }

    #Entity part def Item {
        #Key attribute id : Uuid [1];
        attribute name : String [1] { @FieldRules { maxLength = 100; } }
    }

    #Application part itemWeb {
        :>> target = Target::nextjs;
        #Exposed part items : Item [*] {
            :>> crud = (CrudKind::create, CrudKind::read, CrudKind::list);
            :>> allowedRoles = (AppRoles::user);
        }
        #View part itemList {
            doc /* The list of the items. */
            :>> kind = ViewKind::list;
            ref :>> entity : Item;
            :>> allowedRoles = (AppRoles::user);
        }
        #View part itemDetail {
            doc /* The details of one item. */
            :>> kind = ViewKind::detail;
            ref :>> entity : Item;
            :>> allowedRoles = (AppRoles::user);
        }
        :>> navigation = (itemList);
    }
    satisfy firstRequirement by itemWeb;

    // Infrastructure layer: logical part
    #Network part network;
    #ContainerService part webService;
    #RelationalDatabase part itemDb;
    #UserDirectory part users;
    #Uses dependency from webService to itemDb;
    #Uses dependency from webService to users;
    allocate itemWeb to webService;

    // Infrastructure layer: AWS part
    #AwsVpc part networkAws;
    #AwsEcsService part webServiceAws { :>> cpu default = 512; :>> memory default = 1024; :>> desiredCount default = 1; }
    #AwsRdsPostgres part itemDbAws { :>> instanceClass default = "db.t4g.micro"; :>> multiAz default = false; }
    #AwsCognito part usersAws;
    #Realizes dependency from networkAws to network;
    #Realizes dependency from webServiceAws to webService;
    #Realizes dependency from itemDbAws to itemDb;
    #Realizes dependency from usersAws to users;

    // Replace the account IDs, the regions and the domains with real values.
    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "dev.example.com"; }
    #Environment part staging { :>> accountId = "333333333333"; :>> region = "eu-west-1"; :>> domain = "staging.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "example.com";
        #Override part itemDbProd :> itemDbAws { :>> multiAz = true; }
    }
}
