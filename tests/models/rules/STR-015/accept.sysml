// Test model of story #67: STR-015 accepts this model.
// The waiver on R-001 names the rule COV-003, and it has a reason, an owner
// and an expires date. The waiver on R-002 has no expires date.
package Str015Accept {
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
        @Waiver { rule = "COV-003"; reason = "The API comes in the next release."; owner = "Order team"; expires = "2027-01-31"; }
    }

    #Requirement requirement <'R-002'> pageOrders {
        doc /* The API must do the work of pageOrders. */
        :>> title = "pageOrders"; :>> kind = RequirementKind::functional;
        :>> priority = Priority::must; :>> status = Status::approved;
        frame seeOrders;
        @Waiver { rule = "COV-004"; reason = "The test comes later."; owner = "Order team"; }
    }
}
