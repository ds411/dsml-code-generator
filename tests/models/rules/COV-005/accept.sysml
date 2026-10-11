// Test model of story #62: COV-005 accepts this model.
// The verification V-001 verifies the requirement R-001 with the status
// "verified". R-002 has the status "approved", thus COV-005 does not
// examine it.
package CovAccept {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def Owner;

    #Need concern <'N-001'> seeOrders {
        doc /* The owner must see each order. */
        :>> title = "See orders"; :>> priority = Priority::must; :>> status = Status::approved;
        subject;
        stakeholder owner : Owner;
    }

    #Requirement requirement <'R-001'> listOrders {
        doc /* The API must do the work of listOrders. */
        :>> title = "listOrders"; :>> kind = RequirementKind::functional;
        :>> priority = Priority::must; :>> status = Status::verified;
        frame seeOrders;
    }

    #Requirement requirement <'R-002'> pageOrders {
        doc /* The API must do the work of pageOrders. */
        :>> title = "pageOrders"; :>> kind = RequirementKind::functional;
        :>> priority = Priority::must; :>> status = Status::approved;
        frame seeOrders;
    }

    #Verification verification <'V-001'> listCheck {
        :>> title = "listCheck"; :>> method = VerificationMethod::inspection;
        objective { verify listOrders; }
    }
}
