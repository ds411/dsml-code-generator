// Test model of story #62: COV-006 accepts this model.
// The test file of V-001 exists in the folder of the configuration file of the
// test, tests/models/rules/COV-006. V-002 has the method "inspection", thus
// COV-006 does not examine its path.
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
        doc /* The API must give a list of the orders. */
        :>> title = "List orders"; :>> kind = RequirementKind::functional;
        :>> priority = Priority::must; :>> status = Status::draft;
        frame seeOrders;
    }

    #Verification verification <'V-001'> listCheck {
        :>> title = "List check"; :>> method = VerificationMethod::test;
        :>> testFiles = ("features/order_check.py");
        objective { verify listOrders; }
    }

    #Verification verification <'V-002'> listReview {
        :>> title = "List review"; :>> method = VerificationMethod::inspection;
        :>> testFiles = ("features/missing_check.py");
        objective { verify listOrders; }
    }
}
