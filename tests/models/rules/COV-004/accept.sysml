// Test model of story #62: COV-004 accepts this model.
// The verification V-001 verifies the approved requirement R-001. The
// requirements R-002 (draft) and R-003 (retired) need no verification.
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
        :>> priority = Priority::must; :>> status = Status::approved;
        frame seeOrders;
    }

    #Requirement requirement <'R-002'> pageOrders {
        doc /* The API must do the work of pageOrders. */
        :>> title = "pageOrders"; :>> kind = RequirementKind::functional;
        :>> priority = Priority::must; :>> status = Status::draft;
        frame seeOrders;
    }

    #Requirement requirement <'R-003'> printOrders {
        doc /* The API must do the work of printOrders. */
        :>> title = "printOrders"; :>> kind = RequirementKind::functional;
        :>> priority = Priority::must; :>> status = Status::retired;
        frame seeOrders;
    }

    #Verification verification <'V-001'> listCheck {
        :>> title = "listCheck"; :>> method = VerificationMethod::inspection;
        objective { verify listOrders; }
    }
}
