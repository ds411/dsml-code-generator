package LoanNeeds {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 1; }

    #Stakeholder part def Member;
    #Stakeholder part def Librarian;

    #Need concern <'N-001'> borrowBooks {
        doc /* A member of the library must borrow a book for a period of time. */
        :>> title = "Borrow books";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder member : Member;
    }

    #Need concern <'N-002'> seeLoans {
        doc /* The librarian must see all loans of the library. */
        :>> title = "See all loans";
        :>> priority = Priority::should;
        :>> status = Status::approved;
        subject;
        stakeholder librarian : Librarian;
    }
}
