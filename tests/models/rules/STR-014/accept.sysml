// Test model of story #67: STR-014 accepts this model on 2026-06-01.
// The requirements R-001 and R-002 have no satisfying element, thus COV-003
// reports both. The waiver on R-001 stops COV-003 on R-001 until 2027-01-31.
// The waiver does not stop COV-003 on R-002.
package Str014Accept {
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
    }
}
