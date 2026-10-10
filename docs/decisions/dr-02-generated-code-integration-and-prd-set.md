# Decision record 02: generated code, integration and PRD set

Status date: 10 October 2026

## Purpose and status

This record holds 15 open questions, Q34 to Q48. The answers in [DSML decision record 01: scope and architecture](dr-01-scope-and-architecture.md) raised them. The PRD set starts when these questions are closed.

Most questions come from three decisions: Feature-Sliced Design (FSD) for React and Next.js, vertical slices for FastAPI, and OpenSysML as the engine. Each question has a default. The defaults use the current documents of FSD and OpenSysML (see Sources).

Status: closed. On 10 October 2026, the product owner accepted all defaults. Each Selected answer column shows the decision.

## How to answer

Answer in the chat or add a comment on a row. You can write "accept all defaults, except Q36 and Q42" and give your answers for those.

When a question closes, its Status changes to Decided and the Default column shows the selected answer. The numbers continue from decision record 01. The text uses ASD-STE100 Simplified Technical English, Issue 9.

## J. Generated code layout

Generated files stay in the slice that owns them, because FSD and vertical slices keep all code of a slice together. A file name suffix, not a folder, marks a generated file.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q34 | Where do generated files go? Options: (a) a top-level `gen/` folder, as in the Q15 default (it breaks FSD and vertical slices); (b) in each slice, in the segment that agrees with the purpose of the file, with a name suffix; (c) in each slice, in a separate `generated` folder. | (b). Generated file names end with `.gen.ts`, `.gen.tsx` or `_gen.py`. The generator writes and deletes only these files. Each slice has a public API file (`index.ts`) that the "create once" mode writes. It re-exports `index.gen.ts`, and developers can add exports to it. The Next.js `app/` folder is fully generated, because Next.js sets its file names. | Decided |
| Q35 | How do model elements map to FSD layers in React and Next.js? | Entity: `entities/<entity>` (types, Zod schemas, TanStack Query hooks). Custom operation or form action: `features/<operation>` (TanStack Form form, mutation). List and detail blocks: `widgets/<entity>-list` and `widgets/<entity>-details`. View: `pages/<view>`. Router, providers, navigation and authentication start: `app`. API client, shadcn/ui components, authentication client and configuration: `shared/api`, `shared/ui`, `shared/auth` and `shared/config`. | Decided |
| Q36 | How does Next.js agree with FSD, and where is the server code? Options: (a) the layout of the FSD guide for Next.js, in one package; (b) a monorepo with an FSD web package and a server package with vertical slices. | (a). The Next.js `app/` folder is at the project root and contains only route files that re-export from FSD. The FSD layers are in `src/`, and the layers app and pages have the names `_app` and `_pages`. Route handlers are in `src/_app/api-routes`. Each slice exports its server-only code (data access, business logic) through `index.server.ts`. The Drizzle schema and queries are in `src/shared/db`. | Decided |
| Q37 | What is the size of a FastAPI slice, and where is shared code? Options: one slice for each operation, or one slice for each entity. | One slice for each operation, in one folder for each entity: `app/features/<entity>/<operation>/`. A slice contains `endpoint_gen.py` (router), `schemas_gen.py` (Pydantic models) and `handler.py` (hand-written, create once). SQLAlchemy table models are shared in `app/shared/db/models/`. The database session, the Cognito token check, the configuration and the error types are in `app/shared/`. `app/main_gen.py` registers all slice routers in sorted order. Alembic migrations are in `migrations/`. | Decided |

The trees that follow show the defaults with one entity (`Order`) and one custom operation (`cancelOrder`).

React with FSD:

```text
src/
├── app/
│   ├── providers/
│   └── router/routes.gen.tsx
├── pages/order-list/
│   ├── index.ts                      # create once
│   ├── index.gen.ts
│   └── ui/order-list-page.gen.tsx
├── widgets/order-list/ui/order-table.gen.tsx
├── features/cancel-order/
│   ├── api/cancel-order.gen.ts
│   ├── model/cancel-order.ts         # hand-written
│   └── ui/cancel-order-form.gen.tsx
├── entities/order/
│   ├── api/order-queries.gen.ts
│   └── model/order.gen.ts
└── shared/
    ├── api/client.gen.ts
    ├── auth/
    └── ui/                           # shadcn/ui components
```

Next.js with FSD:

```text
app/                                  # Next.js routes only, generated
├── orders/page.tsx                   # re-exports @/_pages/order-list
└── api/orders/[id]/cancel/route.ts   # re-exports @/_app/api-routes
src/
├── _app/
│   ├── api-routes/cancel-order.gen.ts
│   └── providers/
├── _pages/order-list/
├── widgets/order-list/
├── features/cancel-order/
│   ├── index.ts
│   ├── index.server.ts
│   └── api/cancel-order.server.ts    # hand-written
├── entities/order/
└── shared/
    ├── db/schema.gen.ts
    └── ui/
```

FastAPI with vertical slices:

```text
app/
├── main_gen.py
├── features/order/
│   ├── cancel_order/
│   │   ├── endpoint_gen.py
│   │   ├── schemas_gen.py
│   │   └── handler.py                # hand-written, create once
│   └── get_order/
└── shared/
    ├── auth/cognito_gen.py
    ├── config_gen.py
    └── db/
        ├── session_gen.py
        └── models/order_gen.py
migrations/
```

## K. Toolchain and library integration

The toolchain calls OpenSysML through its Python client and pins one version. The generator, not a build plugin, writes routes and keeps a pinned copy of shadcn/ui.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q38 | How does Python call OpenSysML? Options: (a) the `opensysml` Python client; (b) the `sysml` CLI as a subprocess; (c) a Go adapter program that writes the IR. | (a). The [opensysml](https://pkg.go.dev/github.com/Open-MBEE/OpenSysML) Python client uses gRPC and starts `sysml-grpc` as a private child process. One release tag gives the Python package and the binary, so the toolchain pins one version for both (0.9.2, released on 5 October 2026). OpenSysML is not yet at version 1.0. An IR adapter isolates its API, and golden IR tests run at each version change. | Decided |
| Q39 | Which route mode does TanStack Router use? Options: (a) file-based routing, which TanStack recommends: a build plugin writes the route tree from a `routes/` folder; (b) code-based routing; (c) virtual file routes. | (b). The DSML generator writes the route tree in `src/app/router/routes.gen.tsx`, and each route imports a page slice. A `routes/` folder is not an FSD layer, and a build plugin adds a second code generator. The model already gives the route tree. | Decided |
| Q40 | Does Next.js also use TanStack Form? | Yes, for client-side forms. The server uses the same Zod schemas to validate the input again. | Decided |
| Q41 | Where does the shadcn/ui source come from? The shadcn/ui CLI copies component source from a registry when it runs, and the registry can change. Options: (a) the CLI at generation time; (b) a pinned copy in the generator package. | (b). The generator package holds a pinned copy of the shadcn/ui components that its templates use. The generator writes them to `shared/ui` in "create once" mode, so developers own them and can change them. A generator release updates the copy. | Decided |

## L. Authentication with Amazon Cognito

One user pool for each environment holds the users, and its groups are the roles of the model. All targets use the authorization code flow with PKCE.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q42 | How does each target use Cognito? Options for the web clients: (a) the AWS Amplify Auth library; (b) a general OIDC library (`oidc-client-ts` for React, Auth.js for Next.js). | Infrastructure: one user pool for each environment, one app client for each application, and one user pool group for each model role. Login uses Cognito managed login with the authorization code flow and PKCE. React and Next.js: (a) Amplify Auth, so both targets use one library. In Next.js, the Amplify adapter for Next.js keeps the tokens in cookies, so server code can read the session. FastAPI: a shared dependency in `app/shared/auth` checks the JWT access token against the JWKS of the user pool and maps the `cognito:groups` claim to model roles. The web clients send the access token as a bearer token. The PRDs check the current library versions. | Decided |

## M. CI/CD and AWS accounts

CI uses short-term AWS credentials and builds each image one time. Each environment has its own AWS account.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q43 | Which pipelines does the toolchain generate for GitHub Actions? | AWS access: GitHub OIDC and one IAM role for each environment, with no long-term access keys. Pull request: model validation with SARIF upload to code scanning; a determinism check (run the generator again, then `git diff --exit-code` must find no change); build, lint and tests of each application; `tofu plan` for dev, with the plan in the job summary. Main branch: build the images, push them to ECR, then `tofu apply` and deploy to dev. Promotion: a release tag or a manual run moves the same image digest to staging and then to prod. A GitHub environment with required reviewers protects prod. Generated code is in Git. Actions are pinned to commit SHAs. Workflow files are in `.github/workflows/` and their names end with `.gen.yml`. | Decided |
| Q44 | Which AWS account layout? Options: (a) one account for all environments; (b) one account for each environment; (c) one account for each environment, plus a shared tooling account for ECR. | (c). The tooling account holds ECR, and each environment account pulls images by digest. Each environment account holds its own OpenTofu state bucket and its own deploy role. AWS Organizations manages the accounts. | Decided |

## N. Model conventions

IDs have a type letter and a number that is never used again. Each element type has a small set of mandatory attributes.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q45 | Which ID format do needs, requirements and verifications use? Option: also add an OpenSysML `IdentityMetadata::ElementId` annotation, so a rename keeps the identity. | `N-001` for needs, `R-001` for requirements and `V-001` for verifications. The number has a minimum of three digits with leading zeros. Each ID is unique in the model, and a deleted ID is not used again. The ID is the SysML v2 short name, for example `<'R-001'>`, and the toolchain uses it as the trace ID. ElementId annotations are not mandatory. A project can set a different ID pattern in its configuration. | Decided |
| Q46 | Which attributes are mandatory? | Need: ID, title, text, stakeholder, priority and status. Requirement: ID, title, text, kind, priority and status. Verification: ID, title and method (test, analysis, inspection or demonstration). Rationale, source and owner are optional. Status values: draft, approved, implemented, verified and retired. | Decided |

## O. The PRD set

The PRD set has eight documents: one top-level PRD and seven PRDs, one for each part of the toolchain.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q47 | Which documents are in the PRD set? Option: fewer documents, for example CI/CD in the IaC PRD and the core in the DSML PRD. | The eight documents in the table below. The application generation PRD has one tab for the common rules and one tab for each target. | Decided |
| Q48 | Does an appendix write the PRD requirements in the DSML? (Q33 had no answer.) | Yes. The top-level PRD has a second tab that holds all PRD requirements and product needs as one `.sysml` text in the DSML. The short name of each requirement is its PRD ID, for example `<'PRD-DSML-001'>`. OpenSysML must parse the text with no errors. This is the first test of the DSML. | Decided |

| Document | ID prefix | Scope | Phase |
| --- | --- | --- | --- |
| Top-level PRD | PRD-TOP | Product goals, users, phases, cross-cutting requirements, project dictionary, links to all PRDs and decision records | 1 |
| DSML PRD | PRD-DSML | DSML library, the model layers (needs, requirements, application, infrastructure, verification), IDs and attributes | 1 |
| Toolchain core PRD | PRD-CORE | OpenSysML integration, IR, CLI, GitHub Action, determinism rules and generation gap rules | 1 |
| Application generation PRD | PRD-APP | Common rules, then FastAPI (phase 1), React (phase 2) and Next.js (phase 3) | 1 to 3 |
| Infrastructure generation PRD | PRD-IAC | Logical and AWS layers, HCL output for OpenTofu and Terraform, Cognito, AWS accounts | 1 |
| CI/CD generation PRD | PRD-CICD | GitHub Actions workflows and AWS access from CI | 1 |
| Validation PRD | PRD-VAL | Rule catalog, severities, output formats and waivers | 1 |
| Traceability PRD | PRD-TRACE | Link types, trace manifest, trace comments, AWS tags and reports | 1 |

## Sources

- [Usage with Next.js, Feature-Sliced Design](https://feature-sliced.design/docs/guides/tech/with-nextjs): folder layout, `_app` and `_pages` layer names, `index.server.ts`, route handlers in `api-routes`, the `db` segment.
- [OpenSysML on pkg.go.dev](https://pkg.go.dev/github.com/Open-MBEE/OpenSysML): version 0.9.2, Python client over gRPC, one release tag for package and binary, element identity.
- [Code-based routing, TanStack Router](https://tanstack.com/router/latest/docs/framework/react/routing/code-based-routing): code-based routing and the recommendation for file-based routing.
