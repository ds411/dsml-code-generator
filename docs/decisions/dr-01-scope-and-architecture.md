# Decision record 01: scope and architecture

Status date: 10 October 2026

## Purpose and status

This record closes 33 questions and adds 3 decisions from the product owner. Together, they set the scope and the architecture of the DSML toolchain. The PRD set uses this record as its baseline.

The toolchain has five parts:

1. A DSML on SysML v2 for stakeholder needs, requirements, application code and infrastructure.
2. Deterministic code generation for React, Next.js and FastAPI.
3. Deterministic code generation for OpenTofu and Terraform.
4. Validation of the model.
5. Traceability.

Status: closed, except Q33. The decisions were made on 10 October 2026. Some answers raised new questions. Decision record 02 contains them.

## How to read this record

Each question has an ID from Q1 to Q33. Each additional decision has an ID from AD1 to AD3. Decision record 02 continues the numbers from Q34.

The Basis column has one of these values:

- **Default**: the product owner accepted the proposed default.
- **Changed**: the product owner selected a different answer.

A third value, **Open**, means that the question had no answer. The question moves to decision record 02.

The text of this record uses ASD-STE100 Simplified Technical English, Issue 9. The word "must" marks an obligation.

## Summary of changes from the defaults

Five answers are different from the defaults, and three decisions are new. All other questions use the default, except four sub-questions and Q33 that had no answer. Decision record 02 contains them.

| ID | Topic | Selected answer |
| --- | --- | --- |
| AD1 | Name of the language | DSML (domain-specific modeling language). The name "DMSL" in earlier text was a typo. |
| AD2 | React and Next.js architecture | Feature-Sliced Design (FSD). |
| AD3 | FastAPI architecture | Vertical slice architecture. |
| Q4 | Product type | Internal product. |
| Q8 | SysML v2 engine and toolchain language | OpenSysML is the engine. Python is the toolchain language. uv is the Python project tool. |
| Q17 | Target stacks | TanStack Router (not React Router). TanStack Form (not React Hook Form). shadcn/ui for components. Amazon Cognito for authentication. |
| Q25 | CI/CD | The toolchain generates CI/CD pipelines for GitHub Actions in phase 1. |
| Q32 | PRD structure | Several PRD documents and one top-level document that links them. |

## A. Language and document conventions

The PRD set uses STE Issue 9 and the word "must" for each requirement.

| ID | Question and options | Selected answer | Basis |
| --- | --- | --- | --- |
| Q1 | Which word marks a requirement? Options: "must" (approved in STE) or "shall" (used in ISO/IEC/IEEE 29148, not approved in STE). | Each PRD requirement uses "must". The conventions section of each PRD defines the word. | Default |
| Q2 | Does the PRD set have a project dictionary? | Yes. An appendix lists the approved technical nouns and technical verbs of the project. The product owner gave no company term list, so the PRD set starts a new list. | Default |
| Q3 | Does the validator check the text of needs and requirements against STE? | Yes, as an optional rule set: sentence length, approved modal verbs, passive voice and the project dictionary. The tool does not claim full STE compliance. | Default |

## B. Product scope

The toolchain is an internal product. Phase 1 delivers the model layers, validation, traceability, the FastAPI generator and the OpenTofu generator.

| ID | Question and options | Selected answer | Basis |
| --- | --- | --- | --- |
| Q4 | Who uses the product? Is it internal, open source or commercial? | Internal product. The three user roles are: systems engineer (needs and requirements), software developer (application model) and platform engineer (infrastructure). | Changed |
| Q5 | How is the toolchain delivered? | A CLI and a GitHub Action in phase 1. A VS Code extension with a language server comes in a later phase. | Default |
| Q6 | Which parts are in which phase? | Phase 1: the four model layers, validation, traceability, the FastAPI generator, the OpenTofu generator and the GitHub Actions generator (from Q25). Phase 2: the React generator. Phase 3: the Next.js generator. | Default |

## C. Language architecture

The DSML is a SysML v2 model library. OpenSysML parses the model, and the toolchain is written in Python.

| ID | Question and options | Selected answer | Basis |
| --- | --- | --- | --- |
| Q7 | How does the DSML extend SysML v2? Options: (a) a model library with metadata definitions; (b) a new concrete syntax that compiles to SysML v2; (c) both. | (a) A model library with metadata definitions. Models are standard SysML v2 textual notation with user-defined keywords, for example `#Need` and `#Entity`. All compliant tools can read the models. | Default |
| Q8 | Which engine parses the model? Which language does the toolchain use? Options: OMG Pilot Implementation, OpenSysML, sysml2kit, Sensmetry Syside, our own parser. | OpenSysML is the SysML v2 engine. The engine stays behind a versioned intermediate model (IR). Generators and validators read only the IR. Python is the toolchain language, and uv manages the Python project. | Changed |
| Q9 | What is the source of truth for the model? | Textual `.sysml` files in Git. Import from a Systems Modeling API server comes in a later phase. The PRD set does not require a graphical tool. | Default |
| Q10 | How do elements keep a stable identity? | Each need, requirement and verification has a mandatory short name, for example `<'R-001'>`. Other elements use their qualified name. The validator reports a rename as an identity change against the Git baseline. The ID format is open (decision record 02). | Default |

The sketch that follows shows the selected style. It is not the final syntax.

```sysml
package OrderApp {
    private import DSML::*;

    #Stakeholder part def ShopOwner;

    #Need concern <'N-001'> trackOrders {
        doc /* The shop owner must see the status of each order. */
        stakeholder owner : ShopOwner;
    }

    #Requirement requirement <'R-001'> orderStatusApi {
        doc /* The API must return the status of an order in less than 300 ms. */
        frame trackOrders;
    }

    #Entity part def Order {
        attribute id : String;
        attribute status : OrderStatus;
    }

    #Service part orderService;
    satisfy orderStatusApi by orderService;
}
```

## D. Needs and requirements

Requirements have mandatory text and optional formal constraints. Phase 1 includes a verification layer.

| ID | Question and options | Selected answer | Basis |
| --- | --- | --- | --- |
| Q11 | Which attributes do needs and requirements have? | Core set: ID, title, text, rationale, priority (MoSCoW), status, source and owner. Requirements also have a kind: functional, performance, security, interface or constraint. Users can add attributes through the DSML library. The set of mandatory attributes is open (decision record 02). | Default |
| Q12 | Are requirements formal? | Text is mandatory. A formal constraint is optional, for example `require constraint { p95Latency <= 300 [ms] }`. The validator evaluates a constraint when it refers to model attributes. | Default |
| Q13 | Is there a verification layer? | Yes. Phase 1 includes verification elements and `verify` links to test files. Test generation comes in a later phase. | Default |

## E. Application model and code generation

The application model contains structure, API operations, UI views and security, but not business logic. The generator output is byte-identical for the same input.

| ID | Question and options | Selected answer | Basis |
| --- | --- | --- | --- |
| Q14 | What does the application model contain? Option: also model behavior with SysML v2 actions and state machines. | Phase 1 scope: entities (fields, types, constraints, relations); API operations (CRUD and custom operations with typed input and output); UI views (list, detail and form pages, and navigation, for React and Next.js only); security (roles and permissions for each operation and view). Business logic is not in the model. Developers write it by hand in extension points. Behavior generation is not in phase 1. | Default |
| Q15 | How are generated code and hand-written code kept apart? Options: generation gap, protected regions, merge. | Generation gap. The generator replaces generated files at each run. Hand-written code is in other files and calls or extends the generated code. There are no protected regions and no merge. A "create once" mode writes stubs for hand-written files only if they do not exist. The location of generated files changes because of AD2 and AD3 (decision record 02). | Default |
| Q16 | What does "deterministic" mean? | The same model, generator version and configuration give byte-identical output on all operating systems. Rules: sorted output, no timestamps, LF line ends, UTF-8, already-formatted template output and golden-file tests. No AI model is in the generation path. Lockfiles are outside the determinism boundary. CI makes them, and Git keeps them. | Default |
| Q17 | Which stack does each target use? | TypeScript targets: strict TypeScript and pnpm. React: Vite, TanStack Router, TanStack Query, TanStack Form with Zod, Tailwind CSS and shadcn/ui. Next.js: App Router, route handlers for the REST API, Drizzle ORM and shadcn/ui. FastAPI: uv, Pydantic v2, SQLAlchemy 2 with Alembic, and pytest. Authentication: Amazon Cognito for all targets. The PRDs pin the exact versions. | Changed |
| Q18 | Can one model contain several applications? | Yes. An application is one deployable unit with one target. A React app and a FastAPI service in one model use one API model. Import of an external OpenAPI file comes in phase 2. | Default |
| Q19 | Which database? How are migrations made? | PostgreSQL only in phase 1. The generator keeps a schema snapshot in Git. It writes each migration from the difference between the snapshot and the model. A destructive change (drop or rename) needs an explicit model annotation. | Default |

## F. Infrastructure model and IaC

The infrastructure model has a cloud-neutral layer and an AWS layer. The generator writes raw AWS resources in HCL that OpenTofu and Terraform both accept.

| ID | Question and options | Selected answer | Basis |
| --- | --- | --- | --- |
| Q20 | Which abstraction level? Options: (a) AWS resources directly; (b) logical elements with an AWS binding; (c) both layers. | (c) Two layers. The logical layer is cloud-neutral. The AWS layer realizes it. A second cloud adds one more realization layer. | Default |
| Q21 | Which AWS services are in phase 1? | React: S3, CloudFront, ACM and Route 53. Next.js: ECS Fargate behind an ALB. FastAPI: ECS Fargate behind an ALB. Data: RDS for PostgreSQL. Shared: VPC with public and private subnets, ECR, Secrets Manager, KMS, CloudWatch Logs and IAM roles with least privilege. Amazon Cognito is added because of Q17. SQS and Aurora Serverless are not in phase 1. | Default |
| Q22 | OpenTofu or Terraform? | HCL that both tools accept. OpenTofu is the primary CI target. Features of only one tool are available only through an option. The AWS provider major version is pinned. State is in an S3 backend with state locks. | Default |
| Q23 | Raw resources or community modules? | Raw `aws_*` resources in generated local modules. There is no external module dependency, and each resource has a trace tag. | Default |
| Q24 | How does the model show environments? | The model contains the environments dev, staging and prod. Each environment changes a small set of attributes: size, count and Multi-AZ. The generator writes one root module for each environment. The AWS account layout is open (decision record 02). | Default |
| Q25 | How do the application and infrastructure connect? Is CI/CD generation in phase 1? | The application generator writes the Dockerfile. The IaC generator writes ECR, the service and the task definition, with the image tag as a variable. The toolchain generates CI/CD pipelines for GitHub Actions in phase 1. | Changed |

## G. Validation

Validation rules are Python code that reads the IR. An error stops code generation.

| ID | Question and options | Selected answer | Basis |
| --- | --- | --- | --- |
| Q26 | Where do the rules live? Options: (a) SysML v2 constraints in the DSML library; (b) code rules that read the IR; (c) both. | (b) Python code rules that read the IR in phase 1. Each rule has an ID, a severity, a message and a fix hint. | Default |
| Q27 | Which rule categories? | 1. SysML v2 well-formedness (from OpenSysML). 2. DSML structure, for example: each entity has a primary key. 3. Coverage: each need has a requirement, and each requirement has a satisfying element. 4. Cross-layer: each application has an allocation, and a React-only target has no database entity. 5. AWS policy: no public database, encryption at rest, mandatory tags and name length limits. 6. Requirement text: the optional STE rule set from Q3. No company policies were given. | Default |
| Q28 | Which output formats and gates? | Text for people, JSON, and SARIF for CI and code review tools. Code generation stops if there is an error. A `#Waiver` annotation can suppress a rule, but it must have a reason and an owner. An optional output check runs `tsc`, `ruff`, `tofu validate` and `tflint` on the generated code. | Default |

## H. Traceability

The trace chain goes from the stakeholder to the AWS resource. SysML v2 relationships carry the links in the model, and a manifest and tags carry them outside the model.

| ID | Question and options | Selected answer | Basis |
| --- | --- | --- | --- |
| Q29 | Which link types? | Stakeholder to need: the `stakeholder` member of the concern. Need to requirement: `frame`. Requirement to requirement: derivation and refinement. Requirement to application element: `satisfy`. Application element to infrastructure element: `allocate`. Requirement to verification: `verify`. | Default |
| Q30 | How does the trace go into code and into the cloud? | Each generated file has a header with element IDs. The generator writes a sorted `trace.json` (element, file, symbol). Developers can add trace comments in hand-written code, for example `# trace: R-001`, and the tool reads them. Each AWS resource has tags with the element ID and the Git commit of the model. | Default |
| Q31 | Which reports? | Coverage matrix, orphan report, impact analysis (from a changed element to the affected requirements and files) and suspect links after a change. A Git commit is the baseline. Output formats: static HTML, CSV and JSON. All reports are deterministic. | Default |

## I. The PRD set

The PRD set has several PRD documents and one top-level document that links them.

| ID | Question and options | Selected answer | Basis |
| --- | --- | --- | --- |
| Q32 | One PRD or several? | Several PRD documents and one top-level document that links them. Requirement IDs have a prefix for each PRD, for example `PRD-GEN-012`. The list of PRD documents is open (decision record 02). | Changed |
| Q33 | Does an appendix write the PRD requirements in the DSML, as a `.sysml` file? | No answer. The question moves to decision record 02. | Open |

## Additional decisions

The product owner added three decisions. AD2 and AD3 set the application architecture of the generated code.

| ID | Decision | Effect |
| --- | --- | --- |
| AD1 | The language is a DSML (domain-specific modeling language). The name "DMSL" in earlier text was a typo. | All documents use "DSML". The model library package is `DSML`. |
| AD2 | The React and Next.js generators use Feature-Sliced Design (FSD). FSD puts code in layers (app, pages, widgets, features, entities, shared). Each layer contains slices, and each slice contains segments. | The generators map model elements to FSD layers and slices. Decision record 02 sets the mapping, the Next.js folder layout and the location of server code. |
| AD3 | The FastAPI generator uses vertical slice architecture. Each feature is one slice that contains its route, schemas, handler and data access. | The generator writes one folder for each slice. Decision record 02 sets the slice size and the shared code. |

AD2 and AD3 change one part of Q15. A top-level `gen/` folder does not agree with FSD or vertical slices, because each slice must contain all of its code. Decision record 02 sets the new location of generated files.

## Items that move to decision record 02

The answers above raise 15 new questions, Q34 to Q48. [DSML decision record 02: generated code, integration and PRD set](dr-02-generated-code-integration-and-prd-set.md) contains them with defaults.

| New ID | Topic | Comes from |
| --- | --- | --- |
| Q34 | Location of generated files | Q15, AD2, AD3 |
| Q35 | Map from model elements to FSD layers | AD2 |
| Q36 | Next.js layout with FSD, and the location of server code | AD2 |
| Q37 | FastAPI slice size and shared code | AD3 |
| Q38 | How Python calls OpenSysML, and the version pin | Q8 |
| Q39 | TanStack Router route mode | Q17 |
| Q40 | TanStack Form in Next.js | Q17 |
| Q41 | Deterministic source for shadcn/ui components | Q16, Q17 |
| Q42 | Amazon Cognito for each target | Q17, Q21 |
| Q43 | GitHub Actions pipelines | Q25 |
| Q44 | AWS account layout | Q24 |
| Q45 | ID format | Q10 |
| Q46 | Mandatory attributes | Q11 |
| Q47 | Documents in the PRD set | Q32 |
| Q48 | DSML appendix for the PRD requirements | Q33 |
