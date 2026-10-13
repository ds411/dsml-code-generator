package LoanVerification {
    private import DSML::*;
    private import LoanRequirements::*;

    #Verification verification <'V-001'> createLoanTest {
        :>> title = "Loan API test";
        :>> method = VerificationMethod::test;
        :>> testFiles = ("services/loan-api/tests/test_loans_http_gen.py");
        objective { verify createLoan; }
    }

    #Verification verification <'V-002'> recordReturnDemo {
        doc /* Evidence: in the dev environment, a librarian records a loan and then its return. The list of the loans then shows the loan as returned. */
        :>> title = "Return demonstration";
        :>> method = VerificationMethod::demonstration;
        objective { verify recordReturn; }
    }

    #Verification verification <'V-003'> listLoansReview {
        doc /* Evidence: a person examines the roles of the loan list in the model. */
        :>> title = "Review of the loan list roles";
        :>> method = VerificationMethod::inspection;
        objective { verify listLoans; }
    }
}
