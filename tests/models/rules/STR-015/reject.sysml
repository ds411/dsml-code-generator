// Test model of story #67: STR-015 rejects this model.
// The waiver on R-001 has no reason. The waiver on R-002 has no owner. The
// waiver on R-003 names the rule COV-999, which does not exist. The waiver on
// R-004 has an expires value that is not a date YYYY-MM-DD.
package Str015Reject {
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
        @Waiver { rule = "COV-003"; owner = "Order team"; }
    }

    #Requirement requirement <'R-002'> pageOrders {
        doc /* The API must do the work of pageOrders. */
        :>> title = "pageOrders"; :>> kind = RequirementKind::functional;
        :>> priority = Priority::must; :>> status = Status::approved;
        frame seeOrders;
        @Waiver { rule = "COV-003"; reason = "The API comes later."; }
    }

    #Requirement requirement <'R-003'> findOrders {
        doc /* The API must do the work of findOrders. */
        :>> title = "findOrders"; :>> kind = RequirementKind::functional;
        :>> priority = Priority::must; :>> status = Status::approved;
        frame seeOrders;
        @Waiver { rule = "COV-999"; reason = "The API comes later."; owner = "Order team"; }
    }

    #Requirement requirement <'R-004'> sortOrders {
        doc /* The API must do the work of sortOrders. */
        :>> title = "sortOrders"; :>> kind = RequirementKind::functional;
        :>> priority = Priority::must; :>> status = Status::approved;
        frame seeOrders;
        @Waiver { rule = "COV-003"; reason = "The API comes later."; owner = "Order team"; expires = "31.01.2027"; }
    }
}
