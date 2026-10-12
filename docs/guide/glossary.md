# Glossary

This page gives a short meaning for each term and each product name of the user guide. The terms of the project dictionary of the [top-level PRD](../prd/00-top-level-prd.md#project-dictionary) have the same meaning here. The [concepts page](concepts.md) tells more about the main terms.

## Terms

| Term | Meaning |
| --- | --- |
| Alembic | A Python tool that changes the tables of a database from one version to the next. The FastAPI target uses it. |
| API | Application programming interface: the set of operations that a program gives to other programs. |
| application | One deployable unit in the model, with one target. |
| attribute | A value of a model item, for example a title or a size. |
| availability zone | One or more data centers in an AWS Region. Two zones keep a database available if one zone stops. |
| AWS | Amazon Web Services, the cloud provider of the generated infrastructure. |
| AWS account | A container for AWS resources, with a 12-digit ID. Each environment has its own account. |
| baseline | A Git commit that the toolchain compares with the current model. |
| build | To compile and package code. |
| category | The first part of a rule ID, for example `COV` in `COV-003`. It tells what the rule examines. |
| CLI | Command-line interface. The CLI of the toolchain is the command `dsml`. |
| commit | To record a change in Git. Also the record of the change. |
| container | A package of an application and all the files that it needs to operate. A container image is the stored form of a container. |
| container service | A logical service that operates the containers of an application. In AWS, it is an Amazon ECS service. |
| create-once file | A file that the generator writes only if it does not exist. After that, a developer owns it. |
| CRUD | Create, read, update and delete: the standard operations on the data of an entity. The DSML also adds `list`. |
| CSV | Comma-separated values: a text format for a table. |
| custom operation | An operation that is not a CRUD operation. It has an HTTP method and a path. A developer writes its logic. |
| definition | A SysML v2 type. It tells what a kind of item is, for example `part def Task`. |
| deploy | To put a build into an environment. |
| deterministic | Always the same output for the same input. The output of the toolchain is deterministic. |
| domain | The internet name of an environment, for example `tasks.example.com`. |
| Drizzle | A TypeScript library for database access. The Next.js target uses it (phase 3). |
| DSML | The domain-specific modeling language of this product: the SysML v2 library package `DSML`. |
| element | One item in the model, for example a need, an entity or an environment. |
| entity | A data type in the application layer that the generator maps to a table, types and schemas. |
| environment | One deployment of the infrastructure: dev, staging or prod. |
| exposed entity | An entity that an application gives through its API, with CRUD operations. |
| FastAPI | A Python framework for web APIs. It is the target of phase 1. |
| finding | One result of a validation rule: rule ID, severity, message, location. |
| formal constraint | A condition in a requirement that the toolchain can calculate, for example `multiAz == true`. |
| FSD | Feature-Sliced Design: a method to arrange the code of a web frontend in layers and slices. The React and Next.js targets use it. |
| generate | To write files from the IR with the generator. |
| generated file | A file that the generator writes and deletes. Its name ends with `.gen.<ext>` or `_gen.py`, or is on the fixed-name list of its target. |
| generator | The part of the toolchain that writes the code for one kind of output: an application target, the infrastructure or the pipelines. |
| Git | The version control system that holds the model and the code. |
| GitHub Actions | The service of GitHub that builds, tests and deploys code automatically. The generated pipelines are GitHub Actions workflows. |
| hand-written file | A file that a developer writes. The generator never changes it. |
| HCL | HashiCorp Configuration Language: the language of OpenTofu and Terraform files. |
| header | The first lines of a generated source file. They tell that the generator wrote the file, and give its elements. |
| HTML | The language of web pages. A trace report can be an HTML file. |
| HTTP method | The kind of an HTTP request, for example `GET` or `POST`. |
| IR | Intermediate representation: the versioned JSON form of the model that validators and generators read. |
| IR adapter | The part of the toolchain that converts the result of OpenSysML into the IR. |
| Jinja | A template engine for Python. The generators use Jinja templates on the inside. A user does not edit a template. |
| JSON | JavaScript Object Notation: a text format for data. |
| JSON Schema | A JSON document that tells the correct structure of a different JSON document. |
| layer | (1) One of the five parts of the model: need, requirement, application, infrastructure, verification. (2) An FSD layer. The text always states which. |
| lint | To examine code with a static analysis tool. |
| manifest | A JSON file that lists generated files or trace data. |
| MCP | Model Context Protocol: a standard protocol that connects an AI agent to tools and data. |
| MCP prompt | A prompt template that an MCP server gives to an AI agent. |
| MCP resource | A read-only text that an MCP server gives to an AI agent, for example the rule catalog. |
| MCP server | A program that gives MCP tools, MCP resources and MCP prompts to an AI agent through the Model Context Protocol. |
| MCP tool | A function of an MCP server that an AI agent can call, for example `validate`. |
| metadata keyword | A name with `#` before it, for example `#Need`. It gives a model item a special meaning. The DSML supplies the keywords. |
| model | The set of `.sysml` files that describe one product. |
| multiplicity | The number of values that an item can have, for example `[1]` or `[0..1]`. |
| need | A stakeholder concern in the model, with an ID such as `N-001`. |
| network | A logical service that connects the other services and isolates them from the internet. In AWS, it is an Amazon VPC. |
| Next.js | A full-stack framework for web applications with React. It is the target of phase 3. |
| OMG | Object Management Group: the standards organization that publishes SysML v2. |
| OpenSysML | The SysML v2 engine that the toolchain uses to read the model text. |
| OpenTofu | An open-source tool that makes cloud resources from HCL files. |
| operation | An API action of an application: a CRUD action or a custom action. |
| package | A named container for model items, like a folder. |
| parse | To read model text into a syntax tree. |
| phase | One stage of the product plan. Phase 1 has the FastAPI target, phase 2 adds React and phase 3 adds Next.js. |
| pin | To set one exact version or commit SHA. |
| pipeline | A GitHub Actions workflow that the generator writes. |
| PostgreSQL | A relational database. The generated infrastructure uses PostgreSQL in Amazon RDS. |
| priority | The importance of a need or a requirement: `must`, `should`, `could` or `wont`. |
| promote | To deploy the same build to the next environment. |
| push | To send commits or a container image to a remote store. |
| qualified name | A name with the names of its containers, separated by `::`, for example `Priority::must`. |
| React | A JavaScript library for user interfaces. It is the target of phase 2. |
| realization | The AWS form of a logical infrastructure element. |
| redefinition | A SysML v2 statement that gives a new value to an attribute of the definition, for example `:>> title = "List tasks";`. |
| Region | An AWS area with its own data centers, for example `eu-west-1`. |
| relational database | A database that keeps data in tables. In AWS, it is a PostgreSQL database in Amazon RDS. |
| relationship | A connection between two model items, for example `satisfy` or `verify`. |
| requirement | A requirement element in the model, with an ID such as `R-001`, or a PRD requirement. |
| role | A named set of permissions in the application layer. |
| rule | One validation check with an ID, a severity and a message. |
| SARIF | Static Analysis Results Interchange Format: a JSON format for findings. GitHub can show SARIF findings. |
| severity | The importance of a finding: `error`, `warning` or `info`. |
| short name | The ID of an element in `<'...'>` before its name, for example `<'R-001'>`. |
| skill | A folder with instructions and reference files that tells an AI agent how to do a task. |
| slice | An FSD slice, or a vertical slice of a FastAPI application. |
| SQLAlchemy | A Python library for database access. The FastAPI target uses it. |
| stakeholder | A person or group that has needs. |
| status | The stage of a need or a requirement: `draft`, `approved`, `implemented`, `verified` or `retired`. |
| stub | A create-once file with an empty function that a developer completes, for example `handler.py`. |
| suspect link | A trace link with an end that changed after the baseline. |
| symbol | A named item in a code file, for example a class, a function, a route or an HCL resource address. |
| SysML v2 | Systems Modeling Language, version 2: a standard language for the description of systems. |
| tag | A Git name for one commit, for example `v1.0.0`. |
| target | The framework that the generator writes code for: React, Next.js or FastAPI. |
| template | A text with spaces that the generator fills with data from the IR. |
| Terraform | A tool that makes cloud resources from HCL files. The toolchain supports it and OpenTofu. |
| TOML | A text format for configuration files. The configuration file `dsml.toml` uses it. |
| tooling account | The AWS account that holds the shared tools of the pipelines, separate from the environments. |
| trace | To find the elements and files that a link connects. |
| trace comment | A comment in a hand-written file that connects code to an element, for example `# trace: R-001`. |
| trace link | A relationship from one element to a different element or to a file. |
| trace manifest | The file `.dsml/trace.gen.json`. It gives the files, symbols and lines of each element. |
| TypeScript | A language for programs that adds types to JavaScript. The React and Next.js targets use it. |
| usage | One item of a definition, for example `part rose : Plant;`. |
| user directory | A logical service that keeps the users and their sign-in data. In AWS, it is Amazon Cognito. |
| user guide | The documentation in `docs/guide/` for users of the toolchain. |
| uv | A tool that manages Python projects and their dependencies. |
| validate | To examine the model with the validation rules. |
| validator | The part of the toolchain that runs the validation rules on the IR. |
| verification | A verification element with an ID such as `V-001`, which shows how a requirement is verified. |
| view | A UI page in the application layer: list, detail or form. |
| waiver | An annotation that stops one rule for one element, with a reason and an owner. |

## AWS services

The infrastructure layer uses these AWS services. The [infrastructure generation PRD](../prd/04-infrastructure-generation-prd.md) gives all of them.

| Name | Meaning |
| --- | --- |
| Amazon Cognito | The AWS service for users and sign-in. It realizes a user directory. |
| Amazon ECS | Amazon Elastic Container Service: the AWS service that runs containers. It realizes a container service. |
| AWS Fargate | The mode of Amazon ECS where AWS manages the servers. |
| Amazon RDS | Amazon Relational Database Service: the AWS service for relational databases. It realizes a relational database. |
| Amazon VPC | Amazon Virtual Private Cloud: a private network in AWS. It realizes a network. |
