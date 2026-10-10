# React target (phase 2)

## Stack and FSD layout

The React target is a static single-page application. Its code is in the FSD layers in `src/`, and each slice has a public API file.

```text
src/
├── app/
│   ├── providers/
│   ├── layout/navigation.gen.tsx
│   └── router/routes.gen.tsx
├── pages/order-list/
│   ├── index.ts                      # create once
│   ├── index.gen.ts
│   └── ui/order-list-page.gen.tsx
├── widgets/order-list/ui/order-table.gen.tsx
├── features/cancel-order/
│   ├── api/cancel-order.gen.ts
│   └── ui/cancel-order-form.gen.tsx
├── entities/order/
│   ├── api/order-queries.gen.ts
│   └── model/order.gen.ts
└── shared/
    ├── api/client.gen.ts
    ├── auth/amplify.gen.ts
    ├── config/runtime-config.gen.ts
    └── ui/                           # shadcn/ui components, create once
```

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-201 | The React target must use strict TypeScript, pnpm, Vite, React, TanStack Router, TanStack Query, TanStack Form, Zod, Tailwind CSS, shadcn/ui and Amplify Auth. The versions must come from the version baseline. | Inspection | Q17, Q49 |
| PRD-APP-202 | The generator must put the code in the FSD layers `app`, `pages`, `widgets`, `features`, `entities` and `shared` in `src/`. | Test | AD2 |
| PRD-APP-203 | Generated code must obey the FSD import rules: a module imports only from lower layers, and only through the public API of a slice. | Test | AD2 |
| PRD-APP-204 | Each slice must have a create-once `index.ts` that re-exports the generated `index.gen.ts`. | Test | Q34 |
| PRD-APP-205 | The path alias `@/` must refer to `src/`. | Test | AD2 |
| PRD-APP-206 | Slice names and file names must be the kebab case of the model element names. | Test | Q35 |

## Map from model elements to FSD layers

Each model element has one home layer. The generator writes the files in the segment that agrees with their purpose: `model`, `api` or `ui`.

| Model element | FSD slice | Generated files |
| --- | --- | --- |
| Entity | `entities/<entity>` | `model/<entity>.gen.ts`: TypeScript types and Zod schemas. `api/<entity>-queries.gen.ts`: TanStack Query options for `read` and `list`. |
| Operation with input (`create`, `update`, custom) | `features/<operation>` | `api/<operation>.gen.ts`: the mutation. `ui/<operation>-form.gen.tsx`: the TanStack Form form. |
| Operation with no input (`delete`) | `features/<operation>` | `api/<operation>.gen.ts` and `ui/<operation>-button.gen.tsx` with a confirmation dialog |
| List view | `widgets/<entity>-list` | `ui/<entity>-table.gen.tsx` with paging |
| Detail view | `widgets/<entity>-details` | `ui/<entity>-details.gen.tsx` |
| View | `pages/<view>` | `ui/<view>-page.gen.tsx`, which combines widgets and features |
| Navigation, routes, providers | `app` | `router/routes.gen.tsx`, `layout/navigation.gen.tsx`, `providers/*.gen.tsx` |
| API client, auth, configuration, UI kit | `shared` | `api/client.gen.ts`, `auth/amplify.gen.ts`, `config/runtime-config.gen.ts`, `ui/` (shadcn/ui) |

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-210 | The generator must put each model element in the slice and the files that the table of the section "Map from model elements to FSD layers" gives. | Test | Q35, Q61 |
| PRD-APP-211 | The Zod schemas of an entity must apply the same field rules as the Pydantic models of PRD-APP-112. | Test | Q18 |
| PRD-APP-212 | The generator must write the shadcn/ui components that the templates use into `shared/ui` as create-once files, from the pinned copy in the toolchain package. | Test | Q41 |

## Routing, data access and forms

The generator writes the route tree in code, because the model already gives the routes. Route loaders fill the TanStack Query cache, and forms use the same Zod schemas as the API client.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-220 | The generator must write the TanStack Router route tree with code-based routing in `src/app/router/routes.gen.tsx`. The project must not use the TanStack Router file-based routing plugin. | Test | Q39 |
| PRD-APP-221 | Each view must have one route. A list view must use the path `/<entities>`, a detail view `/<entities>/$id`, and a form view `/<operation>`. | Test | Q39 |
| PRD-APP-222 | The `beforeLoad` function of each route must check the session and the roles of the view. With no session, it must start the login. With no permitted role, it must show a "not permitted" page. | Test | Q42, PRD-APP-009 |
| PRD-APP-223 | The loader of each list and detail route must load its data with `queryClient.ensureQueryData` and the query options of the entity slice. | Test | Q35 |
| PRD-APP-224 | Each query key must be an array in the form `[<entity>, <operation>, <parameters>]`. | Test | Q16 |
| PRD-APP-225 | After a mutation, the generated code must invalidate the queries of the changed entity. | Test | Q35 |
| PRD-APP-226 | Each form must use TanStack Form with the Zod schema of its operation as the validator. Each field must use the shadcn/ui form components, with a label and an error message. | Test | Q17, Q40 |
| PRD-APP-227 | The client must show a problem details response as an error message with its `title` and `detail`. | Test | PRD-APP-014 |
| PRD-APP-228 | Each table must have column headers, and the user must be able to reach each control with the keyboard. | Inspection | Q17 |

## Authentication, runtime configuration and build

One static build operates in all environments. At start, the application reads `/config.json`, which the deployment pipeline writes for each environment.

| ID | Requirement | Verification | Source |
| --- | --- | --- | --- |
| PRD-APP-230 | Before the first render, the application must read `/config.json`. The file must give the API base URL, the AWS Region, the user pool ID, the app client ID and the managed login domain. | Test | Q43, PRD-APP-010 |
| PRD-APP-231 | `shared/auth/amplify.gen.ts` must configure Amplify Auth from the runtime configuration and use Cognito managed login with PKCE. | Test | Q42 |
| PRD-APP-232 | The API client must add the access token of the session to each request as a bearer token. | Test | Q42 |
| PRD-APP-233 | `pnpm build` must write the static files to `dist/`. The build must not contain environment values. | Test | Q43 |
| PRD-APP-234 | The generator must write a Steiger configuration, and `dsml check-output` must run Steiger with no error. | Test | AD2, Q28 |
| PRD-APP-235 | The fixed-name generated files of the React target must be: `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `components.json` and `steiger.config.ts`. | Inspection | Q34, PRD-CORE-039 |
