// The needs and requirements layers with all their link types (story #30).
//
// trace: PRD-DSML-011, PRD-DSML-012, PRD-DSML-014, PRD-DSML-015, PRD-DSML-017, PRD-DSML-055, PRD-TRACE-001
package NeedsLinks {
    private import DSML::*;
    private import RequirementDerivation::*;
    private import ModelingMetadata::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def Owner;
    #Stakeholder part def Auditor;

    #Need concern <'N-001'> recordOrders {
        doc /* The owner must see each order. */
        :>> title = "Record orders"; :>> priority = Priority::must; :>> status = Status::approved;
        subject;
        stakeholder owner : Owner;
        stakeholder auditor : Auditor;
    }

    #Requirement requirement <'R-001'> storeOrders {
        doc /* The system must store each order. */
        :>> title = "Store orders";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
        :>> rationale = "The owner needs the history.";
        :>> source = "Workshop 3";
        :>> owner = "Order team";
        frame recordOrders;
        @Waiver { rule = "COV-003"; reason = "The test comes in the next release."; owner = "Order team"; expires = "2027-01-31"; }
    }

    #Requirement requirement <'R-002'> keepOrders {
        doc /* The system must keep each order for ten years. */
        :>> title = "Keep orders";
        :>> kind = RequirementKind::'constraint';
        :>> priority = Priority::should;
        :>> status = Status::draft;
    }

    #Requirement requirement <'R-003'> exportOrders {
        doc /* The system must export the orders as CSV. */
        :>> title = "Export orders";
        :>> kind = RequirementKind::'interface';
        :>> priority = Priority::could;
        :>> status = Status::draft;
    }

    #derivation connection {
        end #original ::> storeOrders;
        end #derive ::> keepOrders;
        end #derive ::> exportOrders;
    }

    #refinement dependency exportOrders to storeOrders;

    #Requirement requirement noShortName {
        doc /* A requirement with no short name uses its qualified name as its identity. */
        :>> title = "No short name";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::wont;
        :>> status = Status::retired;
    }
}
