// Test model of story #62: COV-001 accepts this model.
// The requirement R-001 frames the need N-001.
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
}
