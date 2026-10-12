# Decision record 09: TypeScript targets and phase 2 and 3 details

Status date: 12 October 2026

## Purpose and status

This record holds 4 questions, Q64 to Q67, for phases 2 and 3. Decision issues #150 to #153 asked them when the milestones M9 (#154), M10 (#155) and M11 (#156) were planned. Each changed or new requirement gives its decision in the Source column.

Status: closed. On 12 October 2026, the product owner answered the four decision issues in the project thread of the phase 2 and 3 plan.

## Z. Phases 2 and 3

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q64 | Which versions and tools do the TypeScript targets use (#150)? Options: (a) TypeScript 6.0, the newest stable line of each other tool, Vitest as the test runner, and `tsc` and Steiger as the linters; (b) option (a) with TypeScript 7.0; (c) option (a) and ESLint with `typescript-eslint` as a second linter. | (a) and (c), with a check of TypeScript 7.0 first. The tools are those of the table below. Story #190 checks the tools with TypeScript 7.0 before #158 pins the versions. If all tools operate with TypeScript 7.0, the line is 7.0. If not, the line is 6.0. Result of #190: the line is 6.0. With TypeScript 7.0, `typescript-eslint` and Steiger stop, because they use the JavaScript API of TypeScript, which TypeScript 7.0 does not have (`docs/notes/typescript-check.md`). Changed requirements: PRD-APP-201, PRD-APP-235, PRD-APP-301, PRD-APP-334, PRD-CORE-011, PRD-CICD-004. | Decided |
| Q65 | How does a model refer to an imported OpenAPI file (#151)? Options: (a) a DSML keyword `#ExternalApi` with the attribute `openApiFile`, which the IR adapter converts into IR entities and operations; (b) a key in the configuration file; (c) the generator reads the file directly. | (a). The adapter reads a subset of OpenAPI 3.1 in JSON: object schemas with scalar and enumeration properties, and operations with an `operationId`, a JSON request body and a JSON response. The new rule STR-017 (error) reports a file that does not exist, or an item outside the subset. New requirements: PRD-DSML-058, PRD-CORE-055, PRD-VAL-016. | Decided |
| Q66 | How does a React application call an API on a different domain (#152)? Options: (a) the FastAPI target sends CORS headers for the site domains of the calling `react` applications; (b) CloudFront sends `/api/*` to the ALB of the called application. | (a). The FastAPI application reads the permitted origins from an environment variable at start. The container service module sets the variable for each environment. New requirement: PRD-APP-136. | Decided |
| Q67 | Which names do the Drizzle migration files of the Next.js target use (#153)? Options: (a) add `migrations/meta/_journal.json` to the fixed-name list, and give each migration the tag `<NNNN>_<slug>.gen`; (b) a generated migrator that reads its own journal. | (a). The SQL file of a migration is `migrations/<NNNN>_<slug>.gen.sql`, and the Drizzle migrator reads the journal `migrations/meta/_journal.json`. Changed requirements: PRD-APP-332, PRD-APP-334. | Decided |

## Lines of the TypeScript targets (Q64)

Story #158 writes the exact version of each line into `src/dsml/versions.toml`. The line is the newest stable major line on the day of the story, unless the table gives it.

| Component | Line | Phase |
| --- | --- | --- |
| Node.js | 26 LTS (decision record 03) | 2 |
| TypeScript | 6.0. Story #190 found that `typescript-eslint` and Steiger do not operate with TypeScript 7.0. | 2 |
| React | 19 (decision record 03) | 2 |
| Next.js | 16 (decision record 03). The request interceptor is the file that this line requires (PRD-APP-323). | 3 |
| pnpm | 12 | 2 |
| Vite, TanStack Router, TanStack Query, TanStack Form, Zod, Tailwind CSS | Newest stable major line | 2 |
| shadcn/ui | A pinned copy of the components (Q41) | 2 |
| Amplify JS and its Next.js adapter | Newest stable major line | 2, 3 |
| Drizzle ORM and the PostgreSQL driver `pg` | Newest stable major line | 3 |
| Steiger, Prettier, ESLint with `typescript-eslint`, Vitest | Newest stable major line | 2 |

## Effects on the milestones

- M9 (#154): #190 goes in step 1 and #158 goes in step 2. #190 selected TypeScript 6.0. Its test project also found that the generated projects must add `@steiger/toolkit` as a dev dependency (`docs/notes/typescript-check.md`). #163 adds `#ExternalApi`, PRD-CORE-055 and STR-017. #164 adds the CORS middleware of PRD-APP-136.
- M10 (#155) and M11 (#156): the generated projects get `eslint.config.js`. `dsml check-output` also runs ESLint.
- M11 (#156): #182 writes the migration names of Q67.
