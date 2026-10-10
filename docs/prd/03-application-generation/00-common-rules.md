# Application generation PRD: FastAPI, React, Next.js

Status date: 10 October 2026

## Summary

The application generators write the code of each application in the model from the IR. Each generator has one target. This file gives the rules for all targets, and one file gives the rules for each target.

| Target | Phase | Architecture | File | Requirement IDs |
| --- | --- | --- | --- | --- |
| FastAPI (REST API only) | 1 | Vertical slices | [FastAPI (phase 1)](01-fastapi.md) | PRD-APP-101 to 199 |
| React (frontend only) | 2 | Feature-Sliced Design | [React (phase 2)](02-react.md) | PRD-APP-201 to 299 |
| Next.js (full stack) | 3 | Feature-Sliced Design | [Next.js (phase 3)](03-nextjs.md) | PRD-APP-301 to 399 |

- **Goals covered:** N-002 (deterministic generation) and N-004 (traceability into code).
- **Prefix:** PRD-APP. The rules for all targets use PRD-APP-001 to 099.
- **Related PRDs:** the toolchain core PRD gives the determinism and generated file rules. The infrastructure PRD deploys the output. Decision record 03 gives the exact versions of the stacks.

## Targets and inputs

Each application in the model has one target and one output folder. Applications that share an API get their types from the same IR elements, so the client and the server always agree.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-001 | Each application generator must read only the IR. | Inspection | Q8 |
| PRD-APP-002 | For each application in the IR, the generator of its target must write the code in the output folder that the configuration file gives for that application. | Test | Q18 |
| PRD-APP-003 | A generator must write code only for the entities, operations, views and roles in the IR, and for the health endpoint of PRD-APP-012. | Test | Q14 |
| PRD-APP-004 | A FastAPI or Next.js application must also write an OpenAPI 3.1 document, `openapi.gen.json`, from the IR. The OpenAPI document that the running service supplies must agree with it. | Test | Q18 |
| PRD-APP-005 | The client types of a React application and the schemas of the API that it calls must come from the same IR entities and operations. A contract test in the toolchain CI must compare the generated client with the `openapi.gen.json` of the called application. | Test | Q18 |
| PRD-APP-006 | Phase 2: a React application can call an external API that an imported OpenAPI file gives, in place of an application in the model. | Test | Q18 |

## Rules for all targets

All targets use Cognito for login, check roles on the server, read their configuration at run time and pass the output checks.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-007 | Each application must authenticate users with the Amazon Cognito user pool of its environment. Web clients must use Cognito managed login with the authorization code flow and PKCE. | Test | Q17, Q42 |
| PRD-APP-008 | For each operation, the generated server code must examine the access token. It must return HTTP 401 if there is no valid token, and HTTP 403 if no group in the `cognito:groups` claim is in `allowedRoles`. An operation with `public = true` must need no token. | Test | Q14, Q42 |
| PRD-APP-009 | The generated web client must show only the navigation items and views that the roles of the user permit. It must send a user with no session to the login page. The server check of PRD-APP-008 stays the protection. | Test | Q14 |
| PRD-APP-010 | Each application must read its environment values at run time, not at build time. One build or one container image must operate in all environments. | Test | Q43 |
| PRD-APP-011 | Each application must get secret values from environment variables that ECS sets from Secrets Manager. Generated code must not contain a secret value. | Test | PRD-TOP-006 |
| PRD-APP-012 | A FastAPI or Next.js application must supply `GET /healthz` with no authentication. It must return HTTP 200 while the process operates. | Test | Q21 |
| PRD-APP-013 | The Dockerfile of a FastAPI or Next.js application must use a multi-stage build and a base image pinned by digest. The container must run as a user that is not root and must not contain a secret value. | Test | Q25, Q49 |
| PRD-APP-014 | API errors must use problem details (RFC 9457) with the media type `application/problem+json`. | Test | Q14 |
| PRD-APP-015 | Server logs must be JSON lines on standard output, with a request ID in each line. Logs must not contain tokens or secret values. | Test | PRD-TOP-006 |
| PRD-APP-016 | The generated code of each target must pass `dsml check-output` with no error. | Test | Q28 |
| PRD-APP-017 | Each generated source file must have the trace header that the traceability PRD gives. | Test | Q30 |
