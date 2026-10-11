// Test model of story #62: COV-007 rejects this model.
// The stakeholder Auditor on line 8 has no need.
package CovReject {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def Owner;
    #Stakeholder part def Auditor;

    #Need concern <'N-001'> seeOrders {
        doc /* The owner must see each order. */
        :>> title = "See orders"; :>> priority = Priority::must; :>> status = Status::approved;
        subject;
        stakeholder owner : Owner;
    }
}
