package LoanApplication {
    private import DSML::*;
    private import ScalarValues::*;
    private import LoanRequirements::*;

    #Roles enum def LibraryRoles { member; librarian; }

    #Entity part def Loan {
        #Key attribute id : Uuid [1];
        attribute bookTitle : String [1] { @FieldRules { maxLength = 200; } }
        attribute memberName : String [1] { @FieldRules { maxLength = 100; } }
        attribute dueDate : Date [1];
        attribute returned : Boolean [1];
    }

    #Operation action def ReturnBook {
        in loanId : Uuid;
        out loan : Loan;
        :>> method = HttpMethod::post;
        :>> path = "/loans/{loanId}/return";
    }

    #Application part loanApi {
        :>> target = Target::fastapi;
        #Exposed part loans : Loan [*] {
            :>> crud = (CrudKind::create, CrudKind::read, CrudKind::list);
            :>> allowedRoles = (LibraryRoles::member, LibraryRoles::librarian);
        }
        #Exposed action returnBook : ReturnBook {
            :>> allowedRoles = (LibraryRoles::librarian);
        }
    }
    satisfy createLoan by loanApi;
    satisfy recordReturn by loanApi;
    satisfy listLoans by loanApi;
}
