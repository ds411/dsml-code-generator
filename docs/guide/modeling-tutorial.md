# Modeling tutorial

This tutorial tells you how to write a small DSML model, one layer at a time. You do not need to know SysML v2 before you start. At the end, `dsml validate` accepts your model, and `dsml generate` writes code from it.

Read the [concepts](concepts.md) page first. It tells what the five layers are. This page tells how to write them. The [reference](reference/README.md) gives each keyword and each attribute.

## The product of the tutorial

The product is a loan service for a small library. A member of the library borrows a book. A librarian records the loan and the return of the book, and sees all loans.

The model has five files, one file for each layer. Each file is one SysML v2 package:

| File | Package | Layer |
| --- | --- | --- |
| `model/needs.sysml` | `LoanNeeds` | Needs |
| `model/requirements.sysml` | `LoanRequirements` | Requirements |
| `model/application.sysml` | `LoanApplication` | Application |
| `model/infrastructure.sysml` | `LoanInfrastructure` | Infrastructure |
| `model/verification.sysml` | `LoanVerification` | Verification |

The full model is in [examples/tutorial/](examples/tutorial/). If you have a problem, compare your files with these files.

## Part 1: Start a project

Do these steps:

1. Make an empty folder for the project, and open a terminal in it.
2. Run `dsml init --target fastapi`. The command writes the starter files `dsml.toml` and `model/model.sysml`.
3. Delete the starter model `model/model.sysml`. This tutorial writes a new model in its place.
4. Open `dsml.toml` in a text editor. Replace its text with the text that follows.

```toml
# The configuration file of the DSML toolchain.
# docs/configuration.md in the toolchain repository gives all keys.
schema = 1

[model]
paths = ["model"]

[applications.loanApi]
output = "services/loan-api"

[infrastructure]
output = "infra"

[pipelines]
output = ".github/workflows"
```

The lines of `dsml.toml` have these meanings:

- `schema = 1` gives the version of the configuration file. This key is mandatory.
- `paths = ["model"]` tells the toolchain to read each `.sysml` file in the folder `model`.
- `[applications.loanApi]` gives the output folder of the application `loanApi`. Part 4 adds this application to the model.
- `[infrastructure]` and `[pipelines]` give the output folders of the OpenTofu code and of the GitHub Actions workflows.

Result: the folder has the file `dsml.toml` and an empty folder `model`.

## Part 2: Write the stakeholders and the needs

A stakeholder is a person or an organization with an interest in the product. A need tells what a stakeholder must get from the product. The product has two stakeholders, a member and a librarian, and one need for each stakeholder.

Make the file `model/needs.sysml` with this text:

```sysml
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
```

The lines have these meanings:

- `package LoanNeeds { ... }` makes a package with the name `LoanNeeds`. A package holds the items of the model. The braces contain its items.
- `private import DSML::*;` lets the package use the names of the DSML library, for example `Priority`, with no prefix.
- `@DsmlVersion { major = 1; minor = 1; }` gives the version of the DSML that the model uses. One package of the model must have it. Use the version that `dsml init` writes.
- `#Stakeholder part def Member;` makes a definition with the name `Member`. `part def` is the SysML v2 form for a type of thing. The DSML keyword `#Stakeholder` tells that the thing is a stakeholder.
- `#Need concern <'N-001'> borrowBooks { ... }` makes a need. `concern` is the SysML v2 form for an interest of a stakeholder. `<'N-001'>` gives the ID of the need. `borrowBooks` is its name in the model.
- `doc /* ... */` gives the text of the need. Write it in one sentence with "must".
- `:>> title = "Borrow books";` gives a value to the attribute `title`. The need gets this attribute from the DSML library. `:>>` tells that the line gives a value to an attribute that already exists.
- `Priority::must` and `Status::approved` are values of the lists `Priority` and `Status` of the DSML library. `::` separates the parts of a name.
- `subject;` is a SysML v2 statement that each concern has. Write it as it is.
- `stakeholder member : Member;` connects the need to the stakeholder `Member`. `member` is a local name. `: Member` gives its type.

Result: `dsml validate` gives the warning COV-001 for each need. No requirement comes from the needs yet. Part 3 adds the requirements.

## Part 3: Write the requirements and link them to the needs

A requirement tells what the product must do. Each requirement comes from a need. The product has three requirements: record a loan, record a return, and list the loans.

Make the file `model/requirements.sysml` with this text:

```sysml
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
```

The lines have these meanings:

- `private import LoanNeeds::*;` lets this package use the names of the package `LoanNeeds`, for example `borrowBooks`. Each file imports the packages that it refers to.
- `#Requirement requirement <'R-001'> createLoan { ... }` makes a requirement with the ID `R-001`. `requirement` is the SysML v2 form. `#Requirement` is the DSML keyword.
- `doc /* ... */` gives the text of the requirement. Write one "must" in each requirement text. If a text has two obligations, write two requirements.
- `:>> kind = RequirementKind::functional;` gives the kind of the requirement. The other kinds are `performance`, `security`, `'interface'` and `'constraint'`.
- `frame borrowBooks;` links the requirement to the need `borrowBooks`. This link is a trace link. The trace reports use it.

Result: `dsml validate` gives the warnings COV-003 and COV-004 for each requirement. An approved requirement must have a satisfying element and a verification. Parts 4 and 6 add them.

## Part 4: Write the application

The application layer tells what the software contains. The loan service has these items:

- Two roles: `member` and `librarian`.
- One entity: `Loan`. An entity is a type of data. The generator makes a database table and API data types from it.
- The operations create, read and list for the entity. The generator writes these operations from the entity.
- One custom operation: `ReturnBook`. A custom operation is an API action that is not create, read, update, delete or list.

Make the file `model/application.sysml` with this text:

```sysml
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
```

The lines have these meanings:

- `private import ScalarValues::*;` lets the package use the SysML v2 types `String`, `Integer`, `Boolean` and `Real`. The DSML library gives the types `Uuid`, `Date`, `DateTime` and `Decimal`.
- `#Roles enum def LibraryRoles { member; librarian; }` makes a list of values with the name `LibraryRoles`. `enum def` is the SysML v2 form for a list of values. `#Roles` tells that the values are the roles of the users.
- `#Entity part def Loan { ... }` makes the entity `Loan`. Each `attribute` line in it is one field.
- `#Key attribute id : Uuid [1];` makes the field `id`. `#Key` tells that this field identifies each loan. Each entity must have one key field.
- `attribute bookTitle : String [1]` makes a text field. `[1]` is the multiplicity: the field has exactly one value. `[0..1]` makes a field with no value or one value.
- `{ @FieldRules { maxLength = 200; } }` gives a constraint of the field. The text has 200 characters or fewer. `minValue` and `maxValue` give the limits of a number.
- `#Operation action def ReturnBook { ... }` makes the custom operation. `action def` is the SysML v2 form for a type of action.
- `in loanId : Uuid;` and `out loan : Loan;` give the input and the output of the operation.
- `:>> method = HttpMethod::post;` and `:>> path = "/loans/{loanId}/return";` give the HTTP method and the URL path. `{loanId}` in the path is the input `loanId`.
- `#Application part loanApi { ... }` makes the application `loanApi`. `part` without `def` makes one thing, not a type. The name agrees with the table `[applications.loanApi]` of `dsml.toml`.
- `:>> target = Target::fastapi;` tells the toolchain to generate a FastAPI application.
- `#Exposed part loans : Loan [*] { ... }` puts the entity `Loan` in the API. `[*]` means any number of loans. `crud` gives the operations that the API has for the entity.
- `:>> allowedRoles = (...);` gives the roles that can use the operations. The parentheses contain a list.
- `#Exposed action returnBook : ReturnBook { ... }` puts the custom operation in the API. Only a librarian can use it.
- `satisfy createLoan by loanApi;` tells that the application satisfies the requirement `createLoan`. This link is a trace link.

Result: `dsml validate` gives four errors. The errors are correct at this time, because the model has no infrastructure yet:

- STR-011 for each of the environments `dev`, `staging` and `prod`.
- XLY-001, because the application is not allocated to a service.

`dsml validate` also gives the warning COV-004 for each requirement. Part 5 removes the errors.

## Part 5: Write the infrastructure

The infrastructure layer has two parts:

- The logical part tells which services the application needs: a network, a container service, a database and a user directory. It does not refer to a cloud provider.
- The AWS part tells which AWS service supplies each logical element, and gives the AWS accounts and the environments.

Make the file `model/infrastructure.sysml` with this text:

```sysml
package LoanInfrastructure {
    private import DSML::*;
    private import LoanApplication::*;

    // Logical part
    #Network part network;
    #ContainerService part apiService;
    #RelationalDatabase part loanDb;
    #UserDirectory part users;
    #Uses dependency from apiService to loanDb;
    #Uses dependency from apiService to users;
    allocate loanApi to apiService;

    // AWS part
    #AwsVpc part networkAws;
    #AwsEcsService part apiServiceAws { :>> cpu default = 256; :>> memory default = 512; :>> desiredCount default = 1; }
    #AwsRdsPostgres part loanDbAws { :>> instanceClass default = "db.t4g.micro"; :>> multiAz default = false; }
    #AwsCognito part usersAws;
    #Realizes dependency from networkAws to network;
    #Realizes dependency from apiServiceAws to apiService;
    #Realizes dependency from loanDbAws to loanDb;
    #Realizes dependency from usersAws to users;

    // Accounts and environments
    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "library.dev.example.com"; }
    #Environment part staging { :>> accountId = "333333333333"; :>> region = "eu-west-1"; :>> domain = "library.staging.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "library.example.com";
        #Override part apiServiceProd :> apiServiceAws { :>> desiredCount = 2; :>> minCount = 2; }
        #Override part loanDbProd :> loanDbAws { :>> multiAz = true; }
    }
}
```

The lines have these meanings:

- `// Logical part` is a comment. `//` starts a comment that continues to the end of the line. The toolchain does not read it.
- `#Network part network;` makes the logical network. `#ContainerService`, `#RelationalDatabase` and `#UserDirectory` make the other logical elements in the same form.
- `#Uses dependency from apiService to loanDb;` tells that the container service uses the database. `dependency` is the SysML v2 form for a link from one item to a different item.
- `allocate loanApi to apiService;` puts the application on the container service. This line removes the error XLY-001.
- `#AwsEcsService part apiServiceAws { ... }` tells that an Amazon ECS service on AWS Fargate supplies the container service. `#AwsVpc`, `#AwsRdsPostgres` and `#AwsCognito` are the AWS elements for the other logical elements.
- `:>> cpu default = 256;` gives a value that an environment can change. `default` marks the value as a default value.
- `#Realizes dependency from apiServiceAws to apiService;` connects the AWS element to its logical element. Each logical element must have one AWS element.
- `#ToolingAccount part tooling { ... }` gives the AWS account of the shared tools of the pipelines. `accountId` has 12 digits. `region` is an AWS Region.
- `#Environment part dev { ... }` makes the environment `dev`, with its AWS account, its Region and its domain. The model must have the environments `dev`, `staging` and `prod`. Each environment must have its own AWS account.
- `#Override part loanDbProd :> loanDbAws { :>> multiAz = true; }` changes a value in `prod` only. `:>` tells that `loanDbProd` is a special form of `loanDbAws`. In `prod`, the database is in two availability zones, and the container service has two or more tasks.

The account IDs in this tutorial are examples. Replace them with the IDs of your AWS accounts.

Result: `dsml validate` gives no error. It gives the warning COV-004 for each requirement, because the model has no verification yet.

## Part 6: Write the verifications

A verification tells how you show that a requirement is correct. Each requirement has one verification in this model. The method of a verification is `test`, `'analysis'`, `inspection` or `demonstration`.

Make the file `model/verification.sysml` with this text:

```sysml
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
```

The lines have these meanings:

- `#Verification verification <'V-001'> createLoanTest { ... }` makes a verification with the ID `V-001`. `verification` is the SysML v2 form.
- `:>> method = VerificationMethod::test;` tells that a test shows that the requirement is correct.
- `:>> testFiles = (...);` gives the test files. Each path is relative to the folder of `dsml.toml`. In this tutorial, the test file is a test that `dsml generate` writes in Part 8.
- `objective { verify createLoan; }` links the verification to the requirement `createLoan`. This link is a trace link.
- For the methods `demonstration`, `inspection` and `'analysis'`, the `doc` text gives the evidence.

Result: the model has all five layers. Part 7 validates it.

## Part 7: Validate the model and correct a finding

Validate the model:

```shell
dsml validate
```

The output gives one finding and a summary:

```text
model/verification.sysml:8:9: warning: COV-006: The verification V-001 refers to the test file "services/loan-api/tests/test_loans_http_gen.py". This file does not exist.
  fix: Correct the path in `testFiles`, or add the test file. The path is relative to the folder of the configuration file.
Findings: 0 errors, 1 warning, 0 info.
```

Each finding has these parts:

- The location: the file, the line and the column, for example `model/verification.sysml:8:9`.
- The severity: `error`, `warning` or `info`. An error stops `dsml generate`. A warning does not stop it.
- The rule ID, for example `COV-006`, and the message.
- The line `fix:` tells how to correct the model.

This warning is correct at this time. The test file comes from `dsml generate` in Part 8. After Part 8, the warning does not occur again.

Now see an error finding, and correct it. Do these steps:

1. In `model/infrastructure.sysml`, delete the line `allocate loanApi to apiService;`.
2. Run `dsml validate` again.
3. Read the error finding in the output. The output also gives the warning COV-006.
4. Do the correction of the line `fix:`. Put the line `allocate loanApi to apiService;` back into `model/infrastructure.sysml`.
5. Run `dsml validate` again. The summary must give 0 errors.

The error finding of step 3 is:

```text
model/application.sysml:23:5: error: XLY-001: An application is not allocated to a logical element.
  fix: Allocate the application to one logical element with `allocate`.
```

The location is line 23 of `model/application.sysml`: the application `loanApi`. The application has no service, thus the rule XLY-001 gives an error.

The exit code of `dsml validate` is 0 if the model has no error finding, and 1 if it has one or more. The [reference](reference/README.md) gives each rule and its correction. The page [Reports](reports.md) tells more about the findings.

## Part 8: Generate the code

Generate the code:

```shell
dsml generate
```

`dsml generate` validates the model first. If the model has an error finding, it writes no file. If the model has no error, it writes the files and gives one line for each file, for example `add services/loan-api/app/main_gen.py`.

The generator writes these folders:

| Folder | Contents |
| --- | --- |
| `services/loan-api` | The FastAPI application `loanApi`, with its tests, its database migrations and its `Dockerfile`. |
| `infra` | The OpenTofu code: one module for each logical element, and one root module for the tooling account and for each environment. |
| `.github/workflows` | The GitHub Actions workflows that build, test and deploy the product. |
| `.dsml` | The manifest of the generated files `.dsml/generated.json`, and the trace manifest `.dsml/trace.gen.json`. |

Find the two kinds of files that the generator writes:

- A **generated file** has a name that ends with `.gen.<ext>` or `_gen.py`, for example `services/loan-api/app/main_gen.py` and `infra/envs/prod/main.gen.tf`. Some generated files have a fixed name, for example `services/loan-api/Dockerfile` and `services/loan-api/pyproject.toml`. The generator writes a generated file again at each run. Do not change it. Change the model, and generate again.
- A **create-once file** is a file that you complete. The generator writes it only if it does not exist. In this model, the create-once file is `services/loan-api/app/features/loan/return_book/handler.py`. It is the handler of the custom operation `ReturnBook`. Write the code of the operation in it. After the first run, you own it.

`.dsml/generated.json` gives the list of the generated files and the create-once files. Open it to see each kind.

Validate the model again. The test file of `V-001` now exists, thus the warning COV-006 does not occur again:

```shell
dsml validate
```

The summary gives `Findings: 0 errors, 0 warnings, 0 info.`

Make sure that the generated files agree with the model:

```shell
dsml generate --check
```

This command writes no file. It lists each file that a normal run adds, changes or deletes. If the files agree with the model, the list is empty and the exit code is 0. Run it in CI to find generated files that are not current.

## Next steps

- Change the model, for example add a field to `Loan`, and generate again. Use Git to see the change in the generated code.
- Read [Generated code](generated-code.md) to learn where to add hand-written code.
- Read [Reports](reports.md) to learn about the findings and the trace reports.
- Add a second need and its requirements to the model. Then run `dsml trace coverage` to see the coverage of each requirement.
