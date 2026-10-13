# AI demonstration: a model from the skills

Story #236 did this demonstration on 13 October 2026. It shows that an AI agent with the installed skills writes a model that validates with no error finding (PRD-AI-001 to PRD-AI-003, Q68). The demonstration is not an automatic test. CI does not use an AI model (PRD-TOP-004).

## Procedure

1. Make an empty folder.
2. Run `dsml skills install` in the folder. The command writes the skills `dsml-modeling` and `dsml-cli` into `.claude/skills/`.
3. Give the product description below to a Claude Code agent in the folder.
4. Tell the agent to use only the installed skills as its source of DSML knowledge. The agent must not read the repository, its documents or its example models.
5. Let the agent follow the procedures of the skills: `dsml init`, then the model, then `dsml validate` until it finds no error.
6. Run `dsml validate` again on the result, outside the agent.

The agent was a Claude Code agent that this story started. It read the skill files from `.claude/skills/` with its file tools. It ran the CLI with the toolchain of this repository at commit 657caec.

## Product description

> A small lending library needs a book loan service. Library members must be able to see the list of books and whether each book is available. A librarian must be able to record a loan and a return. The service is a FastAPI application that stores books and loans in a PostgreSQL database. Users sign in through a user directory.

## Result

- The agent ran `dsml init --target fastapi`, then wrote the model in `model/model.sysml` and added one application table to `dsml.toml`.
- The first `dsml validate` of the full model gave exit code 0, with 0 errors and 0 warnings. The agent did not have to correct a finding.
- A second run of `dsml validate` outside the agent gave the same result:

```text
Findings: 0 errors, 0 warnings, 0 info.
```

- `dsml ir` gave 56 elements, 28 links and no finding.
- `dsml generate --check` gave the list of the FastAPI files of `services/loanApi/` and wrote no file.

`dsml version`:

```text
toolchain: 0.1.0
DSML library: 1.1.0
OpenSysML: 0.9.2
IR schema: 1.1.0
```

The model has these parts:

- Needs layer: the stakeholders `LibraryMember` and `Librarian`, and the needs N-001 to N-003.
- Requirements layer: R-001 to R-004 (list the books, show the availability, record a loan, record a return), R-005 (sign in through the user directory) and R-006 (store the data in PostgreSQL).
- Application layer: the roles `member` and `librarian`, the entities `Book` and `Loan`, the operations `RecordLoan` and `RecordReturn`, and the FastAPI application `loanApi`.
- Infrastructure layer: network, container service, PostgreSQL database and user directory, with their AWS realizations, a tooling account and the environments dev, staging and prod.
- Verification layer: V-001 to V-006.

The account IDs, the Region and the domains are the example values of the skill patterns. They are not real values.

## Notes from the agent

The agent told where the skills did not give sufficient data. These items are not errors of the model. A later story can use them to make the skills better.

- The skills do not give the keys of `dsml.toml`. The starter `dsml.toml` refers to `docs/configuration.md` in the toolchain repository, and an agent with only the skills cannot read it. The agent used the commented example `[applications.<name>]` in the starter file.
- The modeling skill does not tell if one entity can have two `#Exposed` parts with different `crud` values and roles.
- The modeling skill tells the agent to give the status `draft` to a new need, but the patterns use `approved` with no explanation.
- No pattern shows a verification with the method `test` and no `testFiles`.
- The modeling skill does not tell when to add a formal constraint (`require constraint`).
- `references/parts.txt` refers to `scripts/write_skill_references.py`, which an agent cannot use.

## Configuration file

```toml
# The configuration file of the DSML toolchain.
# docs/configuration.md in the toolchain repository gives all keys.
schema = 1

[model]
paths = ["model"]

# Add one table for each application of the model. <name> is the name of
# the application in the model. The target of phase 1 is FastAPI.
#
# [applications.<name>]
# output = "services/<name>"

[applications.loanApi]
output = "services/loanApi"
```

## Model

```sysml
package BookLoanModel {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 1; }

    // Needs layer
    #Stakeholder part def LibraryMember;
    #Stakeholder part def Librarian;

    #Need concern <'N-001'> seeBooks {
        doc /* A library member must see the list of books and the availability of each book. */
        :>> title = "See books and availability";
        :>> priority = Priority::must;
        :>> status = Status::draft;
        subject;
        stakeholder member : LibraryMember;
    }

    #Need concern <'N-002'> recordLoans {
        doc /* A librarian must record each loan and each return of a book. */
        :>> title = "Record loans and returns";
        :>> priority = Priority::must;
        :>> status = Status::draft;
        subject;
        stakeholder librarian : Librarian;
    }

    #Need concern <'N-003'> signIn {
        doc /* A librarian must know that only known users can use the service. */
        :>> title = "Only known users";
        :>> priority = Priority::must;
        :>> status = Status::draft;
        subject;
        stakeholder librarian : Librarian;
    }

    // Requirements layer
    #Requirement requirement <'R-001'> listBooks {
        doc /* The API must return the list of the books. */
        :>> title = "List books";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::draft;
        frame seeBooks;
    }

    #Requirement requirement <'R-002'> showAvailability {
        doc /* The API must show for each book if the book is available. */
        :>> title = "Show book availability";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::draft;
        frame seeBooks;
    }

    #Requirement requirement <'R-003'> recordLoan {
        doc /* The API must let a librarian record the loan of an available book to a member. */
        :>> title = "Record a loan";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::draft;
        frame recordLoans;
    }

    #Requirement requirement <'R-004'> recordReturn {
        doc /* The API must let a librarian record the return of a book on loan. */
        :>> title = "Record a return";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::draft;
        frame recordLoans;
    }

    #Requirement requirement <'R-005'> signInThroughDirectory {
        doc /* Each user must sign in through the user directory before the user uses the API. */
        :>> title = "Sign in through the user directory";
        :>> kind = RequirementKind::security;
        :>> priority = Priority::must;
        :>> status = Status::draft;
        frame signIn;
    }

    #Requirement requirement <'R-006'> storeInPostgres {
        doc /* The service must keep the books and the loans in a PostgreSQL database. */
        :>> title = "Store data in PostgreSQL";
        :>> kind = RequirementKind::'constraint';
        :>> priority = Priority::must;
        :>> status = Status::draft;
        frame recordLoans;
    }

    // Application layer
    #Roles enum def LibraryRoles { member; librarian; }

    #Entity part def Book {
        #Key attribute id : Uuid [1];
        attribute title : String [1] { @FieldRules { minLength = 1; maxLength = 200; } }
        attribute author : String [1] { @FieldRules { minLength = 1; maxLength = 200; } }
        attribute isbn : String [0..1] { @FieldRules { maxLength = 17; } }
        attribute available : Boolean [1];
    }

    #Entity part def Loan {
        #Key attribute id : Uuid [1];
        attribute bookId : Uuid [1];
        attribute memberName : String [1] { @FieldRules { minLength = 1; maxLength = 200; } }
        attribute loanDate : Date [1];
        attribute returnDate : Date [0..1];
    }

    #Operation action def RecordLoan {
        in bookId : Uuid;
        in memberName : String;
        out loan : Loan;
        :>> method = HttpMethod::post;
        :>> path = "/books/{bookId}/loan";
    }

    #Operation action def RecordReturn {
        in loanId : Uuid;
        out loan : Loan;
        :>> method = HttpMethod::post;
        :>> path = "/loans/{loanId}/return";
    }

    #Application part loanApi {
        :>> target = Target::fastapi;
        #Exposed part books : Book [*] {
            :>> crud = (CrudKind::read, CrudKind::list);
            :>> allowedRoles = (LibraryRoles::member, LibraryRoles::librarian);
        }
        #Exposed part loans : Loan [*] {
            :>> crud = (CrudKind::read, CrudKind::list);
            :>> allowedRoles = (LibraryRoles::librarian);
        }
        #Exposed action recordLoan : RecordLoan {
            :>> allowedRoles = (LibraryRoles::librarian);
        }
        #Exposed action recordReturn : RecordReturn {
            :>> allowedRoles = (LibraryRoles::librarian);
        }
    }
    satisfy listBooks by loanApi;
    satisfy showAvailability by loanApi;
    satisfy recordLoan by loanApi;
    satisfy recordReturn by loanApi;
    satisfy signInThroughDirectory by loanApi;
    satisfy storeInPostgres by loanApi;

    // Infrastructure layer: logical part
    #Network part network;
    #ContainerService part apiService;
    #RelationalDatabase part libraryDb;
    #UserDirectory part users;
    #Uses dependency from apiService to libraryDb;
    #Uses dependency from apiService to users;
    allocate loanApi to apiService;

    // Infrastructure layer: AWS part
    #AwsVpc part networkAws { :>> natGatewayCount default = 1; }
    #AwsEcsService part apiServiceAws { :>> cpu default = 256; :>> memory default = 512; :>> desiredCount default = 1; }
    #AwsRdsPostgres part libraryDbAws { :>> instanceClass default = "db.t4g.micro"; :>> multiAz default = false; }
    #AwsCognito part usersAws;
    #Realizes dependency from networkAws to network;
    #Realizes dependency from apiServiceAws to apiService;
    #Realizes dependency from libraryDbAws to libraryDb;
    #Realizes dependency from usersAws to users;

    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "loans.dev.example.com"; }
    #Environment part staging { :>> accountId = "333333333333"; :>> region = "eu-west-1"; :>> domain = "loans.staging.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "loans.example.com";
        #Override part libraryDbProd :> libraryDbAws { :>> multiAz = true; }
    }

    // Verification layer
    #Verification verification <'V-001'> listBooksTest {
        doc /* A test calls the book list endpoint and examines the returned books. */
        :>> title = "List books test";
        :>> method = VerificationMethod::test;
        objective { verify listBooks; }
    }

    #Verification verification <'V-002'> showAvailabilityTest {
        doc /* A test records a loan and makes sure that the book list shows the book as not available. */
        :>> title = "Book availability test";
        :>> method = VerificationMethod::test;
        objective { verify showAvailability; }
    }

    #Verification verification <'V-003'> recordLoanTest {
        doc /* A test records the loan of an available book and examines the new loan. */
        :>> title = "Record loan test";
        :>> method = VerificationMethod::test;
        objective { verify recordLoan; }
    }

    #Verification verification <'V-004'> recordReturnTest {
        doc /* A test records the return of a book on loan and examines the return date. */
        :>> title = "Record return test";
        :>> method = VerificationMethod::test;
        objective { verify recordReturn; }
    }

    #Verification verification <'V-005'> signInTest {
        doc /* A test calls the API with no sign-in and makes sure that the API refuses the request. */
        :>> title = "Sign-in test";
        :>> method = VerificationMethod::test;
        objective { verify signInThroughDirectory; }
    }

    #Verification verification <'V-006'> storeInPostgresInspection {
        doc /* Evidence: a person examines the infrastructure model and finds a PostgreSQL database for the service. */
        :>> title = "PostgreSQL storage inspection";
        :>> method = VerificationMethod::inspection;
        objective { verify storeInPostgres; }
    }
}
```
