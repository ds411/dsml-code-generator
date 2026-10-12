# Concepts

This page tells what the model is and what the DSML toolchain does. You do not need to know SysML v2, Jinja, OpenTofu or the other target tools before you read it. The [glossary](glossary.md) gives a short meaning for each term.

## The problem that the toolchain solves

A team that makes a software product keeps much data in different places. The needs of the users are in one document. The requirements are in a different document. The code, the tests and the cloud resources are in the repository. When one of these items changes, it is difficult to find all the other items that must also change.

The DSML toolchain keeps this data in one model. The model is a set of text files in the Git repository of the product. The toolchain reads the model and does these tasks:

- It validates the model, and tells you about each error.
- It generates the code of the application, the infrastructure and the pipelines.
- It traces each need to its requirements, code, tests and AWS resources.

The toolchain does the same work each time. It does not use an AI model or the network for these tasks.

## The work cycle

This is the cycle from a need to code in AWS:

1. Write the needs of the stakeholders in the model.
2. Write the requirements that frame each need.
3. Write the application and the infrastructure that satisfy the requirements.
4. Write the verifications that show how you verify each requirement.
5. Run `dsml validate` and correct each error finding.
6. Run `dsml generate` to write the code of the application, the infrastructure and the pipelines.
7. Write the hand-written code: the logic of the custom operations and the tests.
8. Commit the model and the code. The generated pipelines build the code, and deploy it to the AWS environments.
9. Run `dsml trace coverage` to see which requirements have code and a verification.

When a need or a requirement changes, change the model, and do the cycle again.

## SysML v2 in five minutes

SysML v2 is a standard language for the description of systems. The Object Management Group (OMG) publishes it. A SysML v2 model can be text or diagrams. The DSML uses only the text form. A model file has the extension `.sysml`.

A DSML model uses only a small part of SysML v2:

- **Package.** A package is a named container for model items. It is like a folder. `package Garden { ... }` makes a package with the name `Garden`.
- **Definition.** A definition is a type: it tells what a kind of item is. `part def Plant` defines the kind "plant".
- **Usage.** A usage is one item of a definition. `part rose : Plant;` is one plant with the name `rose`. The colon (`:`) gives the definition of the usage.
- **Attribute.** An attribute is a value of an item, for example a height or a name. `attribute height : Real;` gives each plant a height.
- **Relationship.** A relationship connects two items. For example, `satisfy` tells that an item satisfies a requirement.
- **Metadata keyword.** A metadata keyword is a name with `#` before it, for example `#Need`. It gives an item a special meaning. The DSML gives these keywords. A different metadata form is `@` with a name, for example `@DsmlVersion { ... }`. It adds data to the item that contains it.

This example uses packages, definitions, usages and attributes. It has no DSML keyword:

```sysml
package Garden {
    part def Plant {
        attribute height : ScalarValues::Real;
    }
    part rose : Plant;
    part tulip : Plant;
}
```

Some more items of the text form:

- Each statement ends with a semicolon (`;`), or with a block in braces (`{ ... }`).
- `//` starts a comment that continues to the end of the line. `doc /* ... */` gives the text of an item.
- `<'N-001'>` before a name gives the item a short name. The DSML uses the short name as the ID of a need, a requirement or a verification.
- `:>> title = "...";` gives a value to an attribute that the item gets from its definition. SysML v2 calls this a redefinition.
- `private import DSML::*;` lets the package use the names of the `DSML` package with no prefix.
- `::` separates the parts of a qualified name, for example `Priority::must`.

## What the DSML adds

The DSML is a SysML v2 library package with the name `DSML`. It adds metadata keywords, attribute types and lists of values. It does not change the SysML v2 language. Thus each tool that reads SysML v2 can also read a DSML model.

A DSML model has five layers. Each layer answers one question:

| Layer | Question | Main keywords |
| --- | --- | --- |
| Needs | Who needs the product, and what do they need? | `#Stakeholder`, `#Need` |
| Requirements | What must the product do? | `#Requirement` |
| Application | Which data and operations does the software have? | `#Application`, `#Entity`, `#Operation`, `#Roles` |
| Infrastructure | Where does the software operate in AWS? | `#ContainerService`, `#RelationalDatabase`, `#Environment` and more |
| Verification | How do you show that a requirement is correct? | `#Verification` |

The examples below make one small model: an API for the tasks of a team. Each example is one model file with one package. A model can also put all layers in one package. The [example model](../model/examples/order-service.sysml) does this.

### Needs layer

A stakeholder is a person or group that has needs. A need tells what a stakeholder wants, in the words of the stakeholder. Each need has an ID such as `N-001`, a title, a text, a priority and a status.

The root package of the model must also state the version of the DSML that the model uses, with `@DsmlVersion`.

```sysml
package TaskNeeds {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def TeamLead;

    #Need concern <'N-001'> seeOpenTasks {
        doc /* The team lead must see the open tasks of the team. */
        :>> title = "See open tasks";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder lead : TeamLead;
    }
}
```

### Requirements layer

A requirement tells what the product must do. Each requirement has an ID such as `R-001`. The relationship `frame` connects the requirement to the need that it comes from.

```sysml
package TaskRequirements {
    private import DSML::*;
    private import TaskNeeds::*;

    #Requirement requirement <'R-001'> listTasks {
        doc /* The API must return a list of the tasks. */
        :>> title = "List tasks";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame seeOpenTasks;
    }
}
```

### Application layer

The application layer tells what the software contains:

- An application is one unit of software that you deploy. Its target is the framework that the toolchain generates code for, for example FastAPI.
- An entity is a data type, for example a task. The generator makes a database table and data types from it. `#Key` marks the attribute that identifies each item.
- An exposed entity gets CRUD operations: create, read, update, delete and list. A custom operation is a different API action, with an HTTP method and a path.
- A role is a named set of permissions. `allowedRoles` tells which roles can use an operation.

The relationship `satisfy` tells that the application satisfies the requirement.

```sysml
package TaskApplication {
    private import DSML::*;
    private import ScalarValues::*;
    private import TaskRequirements::*;

    #Roles enum def TeamRoles { member; lead; }

    #Entity part def Task {
        #Key attribute id : Uuid [1];
        attribute title : String [1] { @FieldRules { maxLength = 200; } }
        attribute finished : Boolean [1];
    }

    #Application part taskApi {
        :>> target = Target::fastapi;
        #Exposed part tasks : Task [*] {
            :>> crud = (CrudKind::create, CrudKind::read, CrudKind::list);
            :>> allowedRoles = (TeamRoles::member, TeamRoles::lead);
        }
    }
    satisfy listTasks by taskApi;
}
```

The numbers in square brackets give the multiplicity: how many values the item can have. `[1]` means exactly one value. `[0..1]` means no value or one value. `[*]` means any number of values.

### Infrastructure layer

The infrastructure layer has two parts:

- The **logical part** tells which services the application needs, with no reference to a cloud provider: a network, a container service, a database and a user directory. The relationship `allocate` puts the application on a container service. `#Uses` tells that one service uses a different service.
- The **AWS part** tells how AWS supplies each logical element. For example, `#AwsRdsPostgres` is a PostgreSQL database in Amazon RDS. `#Realizes` connects the AWS element to its logical element.

An environment is one deployment of the infrastructure: `dev`, `staging` or `prod`. Each environment has an AWS account, an AWS Region and a domain. An environment can change some values with `#Override`. In this example, the prod database is in two availability zones (`multiAz = true`).

The tooling account is the AWS account that holds the shared tools of the pipelines.

```sysml
package TaskInfrastructure {
    private import DSML::*;
    private import TaskApplication::*;

    #Network part network;
    #ContainerService part apiService;
    #RelationalDatabase part taskDb;
    #UserDirectory part users;
    #Uses dependency from apiService to taskDb;
    #Uses dependency from apiService to users;
    allocate taskApi to apiService;

    #AwsVpc part networkAws;
    #AwsEcsService part apiServiceAws { :>> cpu default = 256; :>> memory default = 512; :>> desiredCount default = 1; }
    #AwsRdsPostgres part taskDbAws { :>> instanceClass default = "db.t4g.micro"; :>> multiAz default = false; }
    #AwsCognito part usersAws;
    #Realizes dependency from networkAws to network;
    #Realizes dependency from apiServiceAws to apiService;
    #Realizes dependency from taskDbAws to taskDb;
    #Realizes dependency from usersAws to users;

    #ToolingAccount part tooling { :>> accountId = "111111111111"; :>> region = "eu-west-1"; }
    #Environment part dev { :>> accountId = "222222222222"; :>> region = "eu-west-1"; :>> domain = "tasks.dev.example.com"; }
    #Environment part staging { :>> accountId = "333333333333"; :>> region = "eu-west-1"; :>> domain = "tasks.staging.example.com"; }
    #Environment part prod {
        :>> accountId = "444444444444";
        :>> region = "eu-west-1";
        :>> domain = "tasks.example.com";
        #Override part apiServiceProd :> apiServiceAws { :>> desiredCount = 2; }
        #Override part taskDbProd :> taskDbAws { :>> multiAz = true; }
    }
}
```

`default` gives a value that an environment can change. `:>` in `apiServiceProd :> apiServiceAws` tells that the prod item is a special form of `apiServiceAws`.

### Verification layer

A verification tells how you show that a requirement is correct. Each verification has an ID such as `V-001` and a method: test, inspection, analysis or demonstration. The relationship `verify` connects the verification to its requirement. A test verification also gives the files of its tests.

```sysml
package TaskVerification {
    private import DSML::*;
    private import TaskRequirements::*;

    #Verification verification <'V-001'> listTasksReview {
        :>> title = "Review of the task list API";
        :>> method = VerificationMethod::inspection;
        objective { verify listTasks; }
    }
}
```

These six model files make one model. The test of this guide validates them together, and finds no error.

## The IR

The IR (intermediate representation) is a JSON form of the model. The toolchain makes it from the model files in this sequence:

1. OpenSysML reads the model files and the DSML library.
2. The IR adapter converts the result into the IR. It also calculates the formal constraints of the requirements, and puts the results into the IR.
3. The validator and the generators read only the IR.

The IR has a version and a JSON Schema. It contains each element of the five layers, its attributes, its links and the location of the element in its file. It does not contain data that is special to OpenSysML.

Thus a new version of OpenSysML changes only the IR adapter. The validator and the generators do not change. Run `dsml ir` to see the IR of your model.

## Validation, findings and waivers

`dsml validate` examines the model with the validation rules. Each rule has an ID, for example `COV-003`, a severity and a message. The first part of the ID is the category of the rule:

| Category | What the rules examine |
| --- | --- |
| SYN | The SysML v2 syntax and the names. |
| STR | The structure of the elements, for example mandatory attributes. |
| COV | The coverage: each need has a requirement, and each requirement has a satisfying element and a verification. |
| XLY | The links between the layers, for example each application is on a service. |
| AWS | The AWS values, for example the account IDs and the Regions. |
| FCN | The formal constraints of the requirements. |
| IDN | The identity of the elements, compared with a baseline. |
| TXT | The text of the needs and requirements. This category is optional. |

A finding is one result of a rule. It gives the rule ID, the severity, a message and the location in the model. The severity is `error`, `warning` or `info`. An error finding stops `dsml generate`, so the generator does not write code from a model with an error.

A waiver stops one rule for one element. Use a waiver only when you know the cause of the finding and accept it. The waiver must give the rule, a reason and an owner. It can also give a date when it expires. For example, `@Waiver { rule = "COV-004"; reason = "The test comes in the next release."; owner = "Task team"; }` on a requirement stops COV-004 for that requirement. The report shows the waived findings in a separate group.

## Code generation

`dsml generate` validates the model, then writes the code. The generators write three kinds of output:

- **Application code** for the target of each application. Phase 1 has the FastAPI target. React and Next.js come in later phases.
- **Infrastructure code** for OpenTofu or Terraform. This code makes the AWS resources of each environment.
- **Pipelines** for GitHub Actions. The pipelines build, test and deploy the product.

The repository contains three kinds of files:

| Kind | Who writes it | Can you change it? |
| --- | --- | --- |
| Generated file | The generator writes it again at each run. Its name ends with `.gen.<ext>` or `_gen.py`, or is on the fixed-name list of the target. | No. Change the model, and generate again. |
| Create-once file | The generator writes it only if it does not exist, for example the `handler.py` stub of a custom operation. | Yes. After the first run, you own it. |
| Hand-written file | A developer writes it. | Yes. The generator never changes it. |

The generator keeps a manifest of its files in `.dsml/generated.json`. If you change a generated file, `dsml generate` stops with an error, and does not write over your change. `dsml generate --check` writes no file. It lists each file that a normal run changes.

The output is deterministic: the same model, configuration and toolchain version always give the same bytes. The generator sorts each list, and writes no date, time, random value or absolute path. Thus a change in the generated code always comes from a change in the model, the configuration or the toolchain. A reviewer can see that change in Git.

## Traceability

Traceability lets you follow a need to its code, tests and AWS resources, and back.

- **Trace links.** The relationships of the model are trace links: `stakeholder`, `frame`, `satisfy`, `allocate`, `#Realizes` and `verify`. `#derivation` and `#refinement` connect one requirement to a different requirement.
- **Trace manifest.** The generator writes `.dsml/trace.gen.json`. It gives, for each element, the generated files, the symbols in the files and their lines. Each generated source file also starts with a header that names its elements.
- **Trace comments.** In a hand-written file, a trace comment connects the next function or class to an element. For example, `# trace: R-001` in Python, or `// trace: R-001` in TypeScript.
- **Reports.** The subcommand `trace` writes one of four reports, as HTML, CSV or JSON:
  - `coverage`: the status of each requirement: missing, satisfied or verified.
  - `orphans`: the items that have no link, for example a need with no requirement, or a trace comment with an unknown ID.
  - `impact`: for each element that changed after the baseline, the needs, requirements, verifications, files and AWS resources that the change affects.
  - `suspect`: the trace links with an end that changed after the baseline. A person must examine these links again.

The baseline is an earlier Git commit of the model. `dsml trace impact --baseline v1.0.0` compares the model with the commit of the tag `v1.0.0`.

## Parts that you do not need to know

The toolchain uses these parts on the inside. You do not need to know them to write a model or to use the generated code:

- **OpenSysML** is the SysML v2 engine. It reads the model text. Only the IR adapter uses it.
- **Jinja** is a template engine for Python. The generators use Jinja templates to write the code. The templates are part of the toolchain. You do not edit a template. To change the generated code, change the model or the configuration.
- **The tools of each target.** The generated code uses FastAPI, SQLAlchemy and Alembic for a Python API, OpenTofu or Terraform for the infrastructure, and GitHub Actions for the pipelines. Later phases add React, Next.js, Drizzle and FSD. `dsml check-output` runs the language tools of each target on the generated code. You need to know a target tool only to write hand-written code for it.

## Next steps

- Read the [glossary](glossary.md) for the meaning of each term.
- Do the [modeling tutorial](modeling-tutorial.md) to write your first model.
- Read about the [configuration file](../configuration.md).
