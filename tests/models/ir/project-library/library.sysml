// A project library that adds attributes to needs and requirements (PRD-DSML-019).
//
// trace: PRD-DSML-019
library package ProjectLibrary {
    private import ScalarValues::*;
    private import DSML::*;

    concern def ProjectNeed :> BaseTypes::Need {
        attribute businessValue : Integer [0..1];
    }

    requirement def ProjectRequirement :> BaseTypes::Requirement {
        attribute costCenter : String [0..1];
        attribute safetyRelated : Boolean [0..1];
    }

    // A project keyword that specializes the DSML keyword #Requirement. The
    // base type of #Requirement is fixed, so the keyword cannot change it.
    metadata def SafetyRequirement :> DSML::Requirement;
}
