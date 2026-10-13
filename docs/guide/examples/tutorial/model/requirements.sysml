package LoanRequirements {
    private import DSML::*;
    private import LoanNeeds::*;

    #Requirement requirement <'R-001'> createLoan {
        doc /* The API must record a new loan of a book to a member. */
        :>> title = "Record a loan";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame borrowBooks;
    }

    #Requirement requirement <'R-002'> recordReturn {
        doc /* The API must record the return of a borrowed book. */
        :>> title = "Record a return";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame borrowBooks;
    }

    #Requirement requirement <'R-003'> listLoans {
        doc /* The API must give the list of the loans to the librarian. */
        :>> title = "List the loans";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::should;
        :>> status = Status::approved;
        frame seeLoans;
    }
}
