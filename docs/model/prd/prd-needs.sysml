package PrdNeeds {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def SystemsEngineer;
    #Stakeholder part def SoftwareDeveloper;
    #Stakeholder part def PlatformEngineer;

    #Need concern <'N-001'> oneModel {
        doc /* One model holds the needs, requirements, application structure, infrastructure and verifications of a product, with links between them. */
        :>> title = "One model"; :>> priority = Priority::must; :>> status = Status::approved;
        subject; stakeholder se : SystemsEngineer; stakeholder dev : SoftwareDeveloper; stakeholder pe : PlatformEngineer;
    }
    #Need concern <'N-002'> deterministicGeneration {
        doc /* Code generation is deterministic. */
        :>> title = "Deterministic generation"; :>> priority = Priority::must; :>> status = Status::approved;
        subject; stakeholder dev : SoftwareDeveloper; stakeholder pe : PlatformEngineer;
    }
    #Need concern <'N-003'> correctModel {
        doc /* The model is correct before code generation starts. */
        :>> title = "Correct model"; :>> priority = Priority::must; :>> status = Status::approved;
        subject; stakeholder se : SystemsEngineer; stakeholder dev : SoftwareDeveloper; stakeholder pe : PlatformEngineer;
    }
    #Need concern <'N-004'> traceability {
        doc /* Each requirement traces to the code, infrastructure and tests that cover it. */
        :>> title = "Traceability"; :>> priority = Priority::must; :>> status = Status::approved;
        subject; stakeholder se : SystemsEngineer;
    }
    #Need concern <'N-005'> cloudIndependence {
        doc /* The model does not depend on one cloud provider. */
        :>> title = "No dependency on one cloud"; :>> priority = Priority::should; :>> status = Status::approved;
        subject; stakeholder pe : PlatformEngineer;
    }
}
