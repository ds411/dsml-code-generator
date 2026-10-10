# Decision record 03: versions and PRD details

Status date: 10 October 2026

## Purpose and status

This record holds 8 questions, Q49 to Q56, that came up while the PRD set was written. The PRDs already use the default of each question and give its ID in the Source column. If you select a different answer, the PRDs change.

Answer in the chat or add a comment on a row. You can write "accept all defaults, except Q52" and give your answer for that question.

One action is also open, and it is not a decision. The PRD writing session could not install OpenSysML, so nobody has parsed the DSML example model or the DSML appendix yet. PRD-TOP-011 and PRD-DSML-004 require this check. It is the first task of phase 1.

Status: closed. On 10 October 2026, the product owner accepted all defaults. Each Selected answer column shows the decision.

## P. Version baseline

Phase 1 needs fixed lines for Python, OpenSysML, PostgreSQL, OpenTofu, Terraform and the AWS provider now. The TypeScript targets start in phases 2 and 3, and their tools change fast, so their lines can wait.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q49 | Which versions does the toolchain pin? Options: (a) exact patch versions in the PRDs now; (b) release lines in this record, and exact patch versions in one version file in the toolchain repository; (c) the newest version at each generation. Option (c) breaks determinism. | (b). Pin the phase 1 lines in the table below. The first phase 1 release fixes the exact patch versions in the version file, and later toolchain releases update it. A new decision record sets the TypeScript lines at the start of phase 2. | Decided |

| Component | Proposed line | Current release, checked on 10 October 2026 | Phase |
| --- | --- | --- | --- |
| Python (toolchain and FastAPI target) | 3.14 | 3.14.8, 30 September 2026; active support until 1 October 2027 ([endoflife.date](https://endoflife.date/python)) | 1 |
| OpenSysML (Python client and `sysml-grpc`) | 0.9.2 | 0.9.2, 5 October 2026 ([OpenSysML](https://pkg.go.dev/github.com/Open-MBEE/OpenSysML)) | 1 |
| FastAPI, Pydantic 2, SQLAlchemy 2.0, Alembic, pytest, uv | Newest minor at the start of phase 1 | Not checked | 1 |
| PostgreSQL on RDS | 18 | RDS supports 18 since 14 November 2025 ([AWS](https://aws.amazon.com/about-aws/whats-new/2025/11/amazon-rds-postgresql-major-version-18)) | 1 |
| OpenTofu | 1.13 | 1.13.0, 29 September 2026 ([OpenTofu blog](https://opentofu.org/blog/archive/)) | 1 |
| Terraform | 1.16 | 1.16.5, 30 September 2026 ([endoflife.date](https://endoflife.date/terraform)) | 1 |
| HCL `required_version` | `>= 1.13.0` | Accepts OpenTofu 1.13 and Terraform 1.16 | 1 |
| AWS provider | 6.x, newest minor at the start of phase 1 | 6.57.1, 29 July 2026, or later ([releases.sh](https://releases.sh/hashicorp/terraform-provider-aws)) | 1 |
| ALB TLS security policy | `ELBSecurityPolicy-TLS13-1-2-2021-06` | Not checked | 1 |
| IaC security scanner | Checkov | Not checked | 1 |
| GitHub-hosted runner | `ubuntu-24.04` | Not checked | 1 |
| Node.js (TypeScript targets) | 26 LTS | 26.11.1, 8 October 2026; 24 is the Active LTS until 20 October 2026 ([endoflife.date](https://endoflife.date/nodejs)) | 2 |
| TypeScript | 6.0 or 7.0, decided at the start of phase 2 | 7.0 announced 8 July 2026; 6.0 announced 23 March 2026 ([TypeScript blog](https://devblogs.microsoft.com/typescript/)) | 2 |
| React | 19 | 19.3 is in Next.js 16.4 | 2 |
| Next.js | 16 | 16.4, 6 October 2026 ([Next.js blog](https://nextjs.org/blog)) | 3 |
| Vite, TanStack Router, Query and Form, Zod, Tailwind CSS, shadcn/ui, Amplify JS, Drizzle, pnpm | Decided at the start of phase 2 | Not checked | 2, 3 |

## Q. Platforms and performance

The toolchain runs where developers and CI run. Windows users can use WSL.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q50 | Which operating systems does the toolchain support, and how fast must it be? | Operating systems: Linux x64, Linux arm64 and macOS arm64. Windows only through WSL. Performance: `dsml validate` and `dsml generate` on a model with 1,000 elements must finish in less than 10 seconds on a GitHub-hosted Linux runner with 4 vCPUs. The toolchain must accept models with up to 10,000 elements. | Decided |

## R. Application generation details

Three choices change how much code the generator owns and how a developer adds to it.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q51 | Does the FastAPI target use synchronous or asynchronous database access? Options: (a) asynchronous SQLAlchemy with the psycopg 3 driver; (b) synchronous SQLAlchemy with psycopg 3; (c) asynchronous with asyncpg. | (a). FastAPI endpoints are `async def`, and the session is an `AsyncSession`. psycopg 3 supports the two modes, so a change to (b) later needs no new driver. | Decided |
| Q55 | Who writes the handler of a CRUD operation? Options: (a) the generator writes a full handler (`handler_gen.py`), and only custom operations get a hand-written stub; (b) each operation gets a create-once stub. | (a). CRUD handlers are standard code, so a stub would make each developer write the same code. To change a CRUD operation, a developer models it as a custom operation. | Decided |
| Q56 | Who owns the dependency lists (`pyproject.toml`, `package.json`)? Options: (a) the generator owns them, and extra dependencies come from `dsml.toml`; (b) they are create-once files that developers own, and `dsml check-output` warns if a pinned version is different from the baseline. | (a). The generator writes the pinned dependencies of the baseline and the extra dependencies of the configuration file, and the generated CI fails if the lockfile does not agree. This keeps PRD-TOP-008 true for each commit. | Decided |

## S. Deployment and traceability details

Q52 has a real trade-off. The commit tag from Q30 makes each deployment update the tags of all resources, so a plan after a new commit is never empty.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q52 | How does the Git commit of the model reach AWS? Options: (a) the tag `dsml:model-commit` on each resource, from a plan-time variable, as Q30 selected; (b) only the tag `dsml:element` on each resource, and the commit in one SSM parameter for each environment and in the deploy summary; (c) the commit tag only on resources whose element changed. | (a), because Q30 selected it. Effect: each deployment of a new commit updates the tags of all taggable resources in place, with no downtime, and each plan shows these tag updates. Option (b) gives plans that show only real changes. Option (c) needs state that the toolchain does not have. | Decided |
| Q53 | When do database migrations run? Options: (a) a one-off ECS task with the new image, before the services move to the new task definition; (b) at container start; (c) by hand. | (a). A failed migration stops the deployment before any service changes. With (b), each task of a service tries to migrate at the same time. | Decided |
| Q54 | Which baseline do `impact` and `suspect` use when the user gives no `--baseline`? Options: (a) the newest release tag `v*` before `HEAD`; (b) the merge base with the main branch; (c) a Git tag `trace-baseline` that a systems engineer moves after each review. | (a). A release is the point where the team accepts the trace state. A team that reviews more often can set (c) in the configuration file. | Decided |

## Sources

- [endoflife.date: Python](https://endoflife.date/python), [Node.js](https://endoflife.date/nodejs) and [Terraform](https://endoflife.date/terraform): release lines and support dates.
- [OpenTofu blog archive](https://opentofu.org/blog/archive/): OpenTofu 1.13.0 release.
- [Next.js blog](https://nextjs.org/blog): Next.js 16.4 and React 19.3.
- [TypeScript blog](https://devblogs.microsoft.com/typescript/): TypeScript 6.0 and 7.0 announcements.
- [Terraform Provider AWS on releases.sh](https://releases.sh/hashicorp/terraform-provider-aws): AWS provider 6.x releases.
- [Amazon RDS for PostgreSQL major version 18](https://aws.amazon.com/about-aws/whats-new/2025/11/amazon-rds-postgresql-major-version-18): RDS support for PostgreSQL 18.
- [OpenSysML on pkg.go.dev](https://pkg.go.dev/github.com/Open-MBEE/OpenSysML): OpenSysML 0.9.2.
