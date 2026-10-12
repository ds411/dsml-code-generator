# Next.js generator: project files and generator frame

Story #180 added the first part of the Next.js generator (phase 3). The generator writes a project that `tsc`, ESLint, Steiger, Vitest, `next build` and `docker build` accept. The container answers `GET /healthz`. The next stories of M11 (#156) write the other parts.

- Generator: `src/dsml/generate/nextjs.py`. It is in the list `GENERATORS` of `src/dsml/generate/generators.py`, after the React generator.
- Part modules: `nextjs_database.py` (#182), `nextjs_auth.py` (#183), `nextjs_slices.py` (#184), `nextjs_routes.py` (#186) and `nextjs_pages.py` (#188) in `src/dsml/generate/`. In story #180, each function gives no file.
- Templates: `src/dsml/templates/nextjs/project/`.
- Tests: `tests/test_nextjs_generator.py`.
- Golden files: `tests/golden/nextjs/order-web/`, with the schema snapshot but no manifests in `.dsml/`. Write them again with `uv run python scripts/write_golden_nextjs.py`. The configuration of the script is in the parent folder, with the output folder `order-web`, because a generator must not write into the folder `.dsml/` of the configuration file.
- CI: the job "Next.js golden project" in `.github/workflows/ci.yml`.

## Inputs

The generator reads only the IR and the configuration (PRD-APP-001, PRD-CORE-026). It writes files for each application with `target = Target::nextjs`.

- The key `applications.<name>.output` gives the output folder of the application (PRD-APP-002). If the key is missing, `dsml generate` stops with an error.
- The key `applications.<name>.dependencies` gives extra run-time dependencies in the form `<package>@<version>` (PRD-CORE-046). An extra dependency must not be a package of the target. The function `dependencies` of `react.py` does this check for the two targets.
- The versions come from `src/dsml/versions.toml` (PRD-APP-301, PRD-TOP-008). Story #180 added the items `server-only`, `tailwindcss-postcss`, `types-node` and `node-image`. `docs/notes/typescript-baseline.md` gives the items.

## Layout

The generator gives `NEXTJS_LAYOUT` of `react_common.py` to the part modules in a `ReactContext` (PRD-APP-303, PRD-APP-305). Thus the part modules can use the layer writers of the React target. `docs/notes/react-generator.md` ("Layout of the layers") gives the layout.

- The Next.js `app/` folder is at the project root. It holds only route files that re-export from `src/` (PRD-APP-302). The generator owns the full `app/` folder: the item `app/` of the fixed-name list agrees with each file in it.
- The FSD layers are in `src/`. The layers `app` and `pages` have the names `_app` and `_pages`.

## Output

All files are generated files, except the create-once public API files `index.ts` and `index.server.ts`. The generator does not write `pnpm-lock.yaml` (PRD-CORE-036).

| File | Content | Requirements |
| --- | --- | --- |
| `package.json` | The pinned run-time and dev dependencies, the scripts, `packageManager` (pnpm) and `devEngines` (Node.js). The key `postcss` gives the PostCSS plugin of Tailwind CSS to Next.js. | PRD-APP-301, PRD-CORE-046, PRD-TOP-008 |
| `tsconfig.json` | Strict TypeScript. The path alias `@/*` to `./src/*`. The options that `next build` requires, thus `next build` does not change the file. | PRD-APP-301, PRD-APP-303 |
| `next.config.ts` | The `standalone` output. No `X-Powered-By` header. | PRD-APP-333 |
| `components.json` | The settings of shadcn/ui with server components (`rsc`). | PRD-APP-301, Q41 |
| `steiger.config.ts` | The recommended rules of the FSD plugin of Steiger, with the changes of the React target. The rule `fsd/typo-in-layer-name` is also off, because Steiger reads `_app` and `_pages` as typos. | PRD-APP-306 |
| `eslint.config.js` | The type-aware rules of `typescript-eslint` (`strictTypeChecked`). ESLint does not examine `.next/` and `next-env.d.ts`. | PRD-APP-301, Q64 |
| `vitest.config.ts` | The Vitest settings and the alias `@/` to `/src/`. | PRD-APP-301, Q64 |
| `drizzle.config.ts` | The schema, the migration folder and the database settings for a developer tool. The project does not install `drizzle-kit`, thus the file does not import it. | PRD-APP-331, PRD-APP-334 |
| `Dockerfile` | A multi-stage build on the pinned Node.js image. The runtime stage has the `standalone` output, the migration command and the migrations only. It runs as the user `node` and listens on port 3000. | PRD-APP-013, PRD-APP-332, PRD-APP-333 |
| `.dockerignore` | Only the listed files go into the build context. | PRD-APP-013 |
| `app/layout.tsx` | Re-exports the root layout of `src/_app/layout/`. | PRD-APP-302 |
| `app/healthz/route.ts` | Re-exports the handler of `GET /healthz`. | PRD-APP-012, PRD-APP-302 |
| `src/_app/layout/root-layout.gen.tsx` | The root layout. It reads the public runtime values at each request and gives them to the client components. | PRD-APP-010, PRD-APP-325 |
| `src/_app/api-routes/healthz.gen.ts` | `GET /healthz`: HTTP 200 with `{"status": "ok"}` and no token. | PRD-APP-012 |
| `src/shared/config/` | `public-config.gen.tsx`: the client component `PublicConfigProvider` and the hook `usePublicConfig`. `public-config.server.gen.ts`: the function `readPublicConfig`. | PRD-APP-325 |
| `src/shared/log/` | `request-id.gen.ts`: the request ID. `logger.server.gen.ts`: the function `log` and the wrapper `withRequestLog` of a route handler. | PRD-APP-015 |

The fixed-name list is the list of PRD-APP-334. It also has `proxy.ts` and `middleware.ts` for the next stories. Each other generated file has a name that ends with `.gen.<ext>` (PRD-CORE-039), or is the schema snapshot `.dsml/schema-snapshot.json` (PRD-APP-124) of the list `STATE_FILES`.

## Public runtime values

The build reads no environment value and uses no `NEXT_PUBLIC_` variable (PRD-APP-010, PRD-APP-325). Thus one container image operates in all environments.

- The root layout calls `connection()` of `next/server`. Thus Next.js renders it at each request, not at build time.
- `readPublicConfig` reads these environment variables of the container. A missing variable gives an error that names the variable.

| Key | Environment variable |
| --- | --- |
| `region` | `AWS_REGION` |
| `userPoolId` | `COGNITO_USER_POOL_ID` |
| `appClientId` | `COGNITO_APP_CLIENT_ID` |
| `loginDomain` | `COGNITO_LOGIN_DOMAIN` |

The infrastructure generator sets these variables in the container service of a `nextjs` application (story #181). `GET /healthz` does not read them, thus the health check operates with no configuration.

## Logs

Each route handler that `withRequestLog` wraps writes one JSON line on standard output for each request (PRD-APP-015). The line has the time, the level, the message, the request ID, the method, the path, the status and the duration. The request ID comes from the header `X-Request-ID`, or the handler makes a new one. The response has the header `X-Request-ID`. An error that the handler does not catch gives HTTP 500 with problem details.

The server of the `standalone` output writes some start lines that are not JSON, for example `✓ Ready`. The generated code does not write these lines.

## Server-only modules

A server-only module imports `server-only` and has a name that ends with `.server.gen.ts`. The public API `index.server.ts` of its segment exports it, and `index.ts` does not (PRD-APP-305). For example, the root layout imports `readPublicConfig` from `@/shared/config/index.server`.

## Authentication

Story #183 added the auth part: `src/dsml/generate/nextjs_auth.py` and the templates in `src/dsml/templates/nextjs/auth/`. Authentication uses Amplify Auth with its Next.js adapter (PRD-APP-322, Q42, Q64). The tests are in `tests/test_nextjs_auth.py` and `tests/nextjs/auth/`.

| File | Content | Requirements |
| --- | --- | --- |
| `src/shared/auth/amplify.gen.ts` | The function `configureAuth`: Amplify Auth in the browser with Cognito managed login, the authorization code flow and PKCE. The option `ssr` of Amplify keeps the tokens in cookies. The paths of the login page, the callback URL and the logout URL, and the scopes of the app client. The functions `loginUrl` and `returnPath`. | PRD-APP-007, PRD-APP-322 |
| `src/shared/auth/access.gen.ts` | The types `Access` and `Session`, the function `sessionOf` and the role check `checkAccess`. | PRD-APP-008 |
| `src/shared/auth/login-page.gen.tsx` | The client component `LoginPage`. It keeps the path after the login in the session storage and starts the managed login. | PRD-APP-007, PRD-APP-323 |
| `src/shared/auth/callback-page.gen.tsx` | The client component `CallbackPage`. Amplify changes the code into tokens. Then the page goes to the path after the login. | PRD-APP-007, PRD-APP-322 |
| `src/shared/auth/session.server.gen.ts` | `getSession`, `requireSession`, `authorize` and `accessProblem`. | PRD-APP-008, PRD-APP-323, PRD-APP-324 |
| `app/auth/login/page.tsx`, `app/auth/callback/page.tsx` | The route files of the two pages. | PRD-APP-302 |
| `proxy.ts` | The request interceptor. | PRD-APP-323 |

The pages of the authentication use these paths:

| Path | Page |
| --- | --- |
| `/auth/login?next=<path>` | The login page. Only a path on this site is permitted as `next`. |
| `/auth/callback` | The callback URL of the app client. This is `CALLBACK_PATH` of the infrastructure generator, thus the infrastructure did not change. |
| `/` | The logout URL of the app client (`LOGOUT_PATH`). |

### Session on the server

The first call of `getSession` reads the user pool ID and the app client ID with `readPublicConfig` and calls `createServerRunner` of the adapter. Thus the values come from the environment at run time, not from the build (PRD-APP-010, PRD-APP-011). The adapter reads the tokens from the cookies and examines them with the keys of the user pool. A token that is not valid gives no session.

- A server component or a route handler calls `getSession()` with no argument. The adapter reads the cookies of the request.
- `authorize(access)` applies the role check of PRD-APP-008. It gives `{ ok: true, session }`, or `{ ok: false, response }` with problem details: HTTP 401 if there is no valid token, and HTTP 403 if no group in `cognito:groups` is in the roles. A public item needs no token, thus `authorize` does not read the session. The texts are the texts of the FastAPI target.
- The route handlers (#186) and the pages (#188) use these functions. A page with no permitted role must show a "not permitted" page (PRD-APP-009).

### Request interceptor

The pinned Next.js 16 uses the name `proxy.ts`, not `middleware.ts` (PRD-APP-323). The matcher has the route of each view that is not public, sorted: `/<entities>` for a list view, `/<entities>/:id` for a detail view and `/<operation>` for a form view (PRD-APP-221). The name comes from the `#Exposed` element of the application that exposes the entity or the operation. If the application does not expose it, `dsml generate` stops with an error. If each view is public, the generator does not write `proxy.ts`.

The interceptor calls `requireSession`. With no session, it sends HTTP 307 to `/auth/login` with the requested path and query in `next`. It does not check the roles. `GET /healthz`, the route handlers in `app/api/` and the auth pages are not in the matcher.

### Tests

- `tests/test_nextjs_auth.py` compares the auth files of the order web with the golden files. It also examines the matcher with public views, and the error for a view with no exposed element.
- `tests/nextjs/auth/auth.test.ts` is a Vitest test. The CI job copies it into the golden project. It replaces the Amplify adapter and gives test tokens. It examines the 401 and 403 results of `authorize`, the redirect of the interceptor and the path after the login.
- The CI job gets `/orders` from the container with no session. The response must be HTTP 307 to `/auth/login?next=%2Forders`.

## Notes for the next stories

- The golden test of each part story compares only the files of its part. `PART_FOLDERS` in `tests/test_nextjs_generator.py` gives these folders. `src/_app/api-routes/healthz.gen.ts` belongs to the project files.
- The generator writes the segments `config` and `log` of `src/shared/`. If a part story uses the shared layer writer of the React target, it must not write these segments again.
- Story #182 added the database part: `src/shared/db/`, `migrations/`, `migrate.gen.mjs` and `standalone-migrate.gen.mjs`. `docs/notes/schema-snapshot.md` ("Drizzle migrations of the Next.js target") gives the files. A server function gets the database with `getDatabase()` from `@/shared/db/index.server`, and the tables from `@/shared/db`.
- The `standalone` output has only the files that the server needs. After `next build`, the Dockerfile runs `node standalone-migrate.gen.mjs`. The script copies `migrate.gen.mjs` and the files that it needs into the `standalone` output, with the file trace of Next.js (`next/dist/compiled/@vercel/nft`). The trace is a part of Next.js that has no public API. The CI job runs `node migrate.gen.mjs` in the image, thus a change of Next.js that breaks the script makes the job fail.
- ESLint does not examine the scripts `*.gen.mjs`, because the type-aware rules need the TypeScript project.
- The root layout has no providers and no style sheet yet. Story #188 adds the providers, the navigation and the style sheet `src/_app/styles/index.css` of `components.json`. A client component that calls Amplify Auth, for example a logout button, must first call `configureAuth` of `@/shared/auth` with `usePublicConfig()` and `window.location.origin`.
- The CI job runs Vitest with no tests. The part stories add their tests.
