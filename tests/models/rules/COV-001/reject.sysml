// Test model of story #62: COV-001 rejects this model.
// No requirement frames the need N-002 on line 23.
package CovReject {
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

    #Need concern <'N-002'> cancelOrders {
        doc /* The owner must cancel an order. */
        :>> title = "Cancel orders"; :>> priority = Priority::should; :>> status = Status::draft;
        subject;
        stakeholder owner : Owner;
    }
}
