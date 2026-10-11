// Test model of story #62: COV-002 rejects this model.
// The requirement R-002 on line 24 frames no need and is not derived from a
// different requirement.
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

    #Requirement requirement <'R-002'> pageOrders {
        doc /* The API must give the list of the orders in pages. */
        :>> title = "Page orders"; :>> kind = RequirementKind::functional;
        :>> priority = Priority::should; :>> status = Status::draft;
    }
}
