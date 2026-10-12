# Next.js target (phase 3)

## Stack and FSD layout

The Next.js target follows the FSD guide for Next.js: the Next.js `app/` folder holds only route files, and the FSD layers are in `src/` with the names `_app` and `_pages` ([Usage with Next.js](https://feature-sliced.design/docs/guides/tech/with-nextjs)).

```text
app/                                  # Next.js routes only, generated
├── layout.tsx
├── orders/page.tsx                   # re-exports @/_pages/order-list
└── api/orders/[id]/cancel/route.ts   # re-exports @/_app/api-routes
src/
├── _app/
│   ├── api-routes/cancel-order.gen.ts
│   └── providers/
├── _pages/order-list/
├── widgets/order-list/
├── features/cancel-order/
│   ├── index.ts                      # create once
│   ├── index.server.ts               # create once
│   └── api/cancel-order.server.ts    # hand-written, create once
├── entities/order/
└── shared/
    ├── db/schema.gen.ts
    └── ui/                           # shadcn/ui, create once
migrations/
```

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-301 | The Next.js target must use strict TypeScript, pnpm, Next.js with the App Router, React, TanStack Query, TanStack Form, Zod, Tailwind CSS, shadcn/ui, Drizzle ORM with the PostgreSQL driver `pg`, Amplify Auth with its Next.js adapter, ESLint with `typescript-eslint` and Vitest. The versions must come from the version baseline. | Inspection | Q17, Q49, Q64 |
| PRD-APP-302 | The Next.js `app/` folder must be at the project root and hold only route files that re-export from `src/`. The generator must own the full `app/` folder. | Test | Q36, Q34 |
| PRD-APP-303 | The FSD layers must be in `src/`, and the layers `app` and `pages` must have the names `_app` and `_pages`. | Test | Q36, AD2 |
| PRD-APP-304 | The generator must map model elements to slices as PRD-APP-210 gives, with the layer names of PRD-APP-303. | Test | Q35 |
| PRD-APP-305 | A slice must export server-only modules through `index.server.ts` and other modules through `index.ts`. Each server-only module must import `server-only`. | Test | Q36 |
| PRD-APP-306 | The generated code must obey the FSD import rules of PRD-APP-203, and `dsml check-output` must run Steiger with no error. | Test | AD2 |

## Route handlers and server-only code

Each operation is one route handler under `/api`, with the same contract as the FastAPI target. The logic of the operation is a server function in its feature slice.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-310 | For each operation, the generator must write a route handler in `src/_app/api-routes/<operation>.gen.ts`. A generated `app/api/<path>/route.ts` must re-export it. | Test | Q36 |
| PRD-APP-311 | The REST contract must be the contract of the FastAPI target (PRD-APP-110 to PRD-APP-115), with the path prefix `/api`. | Test | Q18 |
| PRD-APP-312 | A route handler must validate the input with the Zod schema of the operation, check the token and the roles, call the server function of the operation and return JSON or problem details. | Test | Q40, Q42 |
| PRD-APP-313 | For a CRUD operation, the generator must write the server function as `features/<operation>/api/<operation>.server.gen.ts`. For a custom operation, it must write `<operation>.server.ts` as a create-once stub that throws an error with the HTTP status 501. | Test | Q14, Q55 |
| PRD-APP-314 | Server components of pages must call the server functions for `read` and `list` directly, with no HTTP request. Client components must call the route handlers through TanStack Query. | Test | Q36 |

## Pages, forms and authentication

Pages are server components in `_pages`. Forms are client components that validate on the client and again on the server. Amplify keeps the session in cookies, so server code can read it.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-320 | For each view, the generator must write a page slice in `src/_pages/<view>` and a generated `app/<route>/page.tsx` that re-exports it. Routes must use the paths of PRD-APP-221. | Test | Q36 |
| PRD-APP-321 | Each form must be a client component that uses TanStack Form with the Zod schema of its operation. The route handler must validate the same input again with the same schema. | Test | Q40 |
| PRD-APP-322 | Authentication must use Amplify Auth with its Next.js adapter, and the adapter must keep the tokens in cookies. | Test | Q42 |
| PRD-APP-323 | The generated request interceptor (`middleware.ts` or `proxy.ts`, as the pinned Next.js version requires) must send a request for a protected page with no session to the login. | Test | Q42 |
| PRD-APP-324 | Server components and route handlers must get the session through the Amplify adapter and apply the role checks of PRD-APP-008. | Test | Q42 |
| PRD-APP-325 | The root layout must give the public runtime values (Region, user pool ID, app client ID, login domain) to client components from server-side environment variables. The build must not use `NEXT_PUBLIC_` variables. | Test | Q43, PRD-APP-010 |

## Data access, migrations and container

Drizzle holds the schema and the queries in `src/shared/db`. The generator writes the migration files from the schema snapshot, as for the FastAPI target.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-330 | The generator must write the Drizzle schema of all entities in `src/shared/db/schema.gen.ts`, with the type map of PRD-APP-121. | Test | Q36, Q19 |
| PRD-APP-331 | The generator must write each migration from the difference between `.dsml/schema-snapshot.json` and the IR, in the file format that the Drizzle migrator reads. The project must not use `drizzle-kit generate`. | Test | Q19, Q16 |
| PRD-APP-332 | PRD-APP-125 to PRD-APP-128 must also apply to the Next.js target, with the SQL file name `migrations/<NNNN>_<slug>.gen.sql`. The migration command must be `node migrate.gen.mjs`. | Test | Q19, Q53, Q67 |
| PRD-APP-333 | The Next.js build must use the `standalone` output. The Dockerfile must run the server on port 3000. | Test | Q25 |
| PRD-APP-334 | The fixed-name generated files of the Next.js target must be: `package.json`, `tsconfig.json`, `next.config.ts`, the full `app/` folder, `middleware.ts` or `proxy.ts`, `drizzle.config.ts`, `components.json`, `steiger.config.ts`, `eslint.config.js`, `vitest.config.ts`, `migrations/meta/_journal.json`, `Dockerfile` and `.dockerignore`. | Inspection | Q34, PRD-CORE-039, Q64, Q67 |
