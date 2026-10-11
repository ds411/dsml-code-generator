package StarterModel {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

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
}
