// A model that uses the attributes of a project library (PRD-DSML-019).
package ProjectModel {
    private import DSML::*;
    private import ProjectLibrary::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Need concern <'N-001'> safeShop : ProjectNeed {
        doc /* The shop must be safe. */
        :>> title = "Safe shop"; :>> priority = Priority::must; :>> status = Status::approved;
        :>> businessValue = 8;
    }

    #Requirement requirement <'R-001'> lockAccounts : ProjectRequirement {
        doc /* The system must lock an account after five failed logins. */
        :>> title = "Lock accounts"; :>> kind = RequirementKind::security; :>> priority = Priority::must; :>> status = Status::approved;
        :>> costCenter = "CC-100";
        frame safeShop;
    }

    #SafetyRequirement requirement <'R-002'> stopRobot : ProjectRequirement {
        doc /* The robot must stop in 100 ms. */
        :>> title = "Stop robot"; :>> kind = RequirementKind::performance; :>> priority = Priority::must; :>> status = Status::approved;
        :>> safetyRelated = true;
        frame safeShop;
    }
}
