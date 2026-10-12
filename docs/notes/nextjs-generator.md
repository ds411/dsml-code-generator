# Next.js generator: project files and generator frame

Story #180 added the first part of the Next.js generator (phase 3). The generator writes a project that `tsc`, ESLint, Steiger, Vitest, `next build` and `docker build` accept. The container answers `GET /healthz`. The next stories of M11 (#156) write the other parts.

- Generator: `src/dsml/generate/nextjs.py`. It is in the list `GENERATORS` of `src/dsml/generate/generators.py`, after the React generator.
- Part modules: `nextjs_database.py` (#182), `nextjs_auth.py` (#183), `nextjs_slices.py` (#184), `nextjs_routes.py` (#186) and `nextjs_pages.py` (#188) in `src/dsml/generate/`. In story #180, each function gives no file.
- Templates: `src/dsml/templates/nextjs/project/`.
- Tests: `tests/test_nextjs_generator.py`.
- Golden files: `tests/golden/nextjs/order-web/`, with no manifests in `.dsml/`. Write them again with `uv run python scripts/write_golden_nextjs.py`.
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
| `Dockerfile` | A multi-stage build on the pinned Node.js image. The runtime stage has the `standalone` output only, runs as the user `node` and listens on port 3000. | PRD-APP-013, PRD-APP-333 |
| `.dockerignore` | Only the listed files go into the build context. | PRD-APP-013 |
| `app/layout.tsx` | Re-exports the root layout of `src/_app/layout/`. | PRD-APP-302 |
| `app/healthz/route.ts` | Re-exports the handler of `GET /healthz`. | PRD-APP-012, PRD-APP-302 |
| `src/_app/layout/root-layout.gen.tsx` | The root layout. It reads the public runtime values at each request and gives them to the client components. | PRD-APP-010, PRD-APP-325 |
| `src/_app/api-routes/healthz.gen.ts` | `GET /healthz`: HTTP 200 with `{"status": "ok"}` and no token. | PRD-APP-012 |
| `src/shared/config/` | `public-config.gen.tsx`: the client component `PublicConfigProvider` and the hook `usePublicConfig`. `public-config.server.gen.ts`: the function `readPublicConfig`. | PRD-APP-325 |
| `src/shared/log/` | `request-id.gen.ts`: the request ID. `logger.server.gen.ts`: the function `log` and the wrapper `withRequestLog` of a route handler. | PRD-APP-015 |

The fixed-name list is the list of PRD-APP-334. It also has `proxy.ts`, `middleware.ts` and `migrations/meta/_journal.json` for the next stories. Each other generated file has a name that ends with `.gen.ts` or `.gen.tsx` (PRD-CORE-039).

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

The infrastructure generator must set these variables in the container service of a `nextjs` application (#181). `GET /healthz` does not read them, thus the health check operates with no configuration.

## Logs

Each route handler that `withRequestLog` wraps writes one JSON line on standard output for each request (PRD-APP-015). The line has the time, the level, the message, the request ID, the method, the path, the status and the duration. The request ID comes from the header `X-Request-ID`, or the handler makes a new one. The response has the header `X-Request-ID`. An error that the handler does not catch gives HTTP 500 with problem details.

The server of the `standalone` output writes some start lines that are not JSON, for example `✓ Ready`. The generated code does not write these lines.

## Server-only modules

A server-only module imports `server-only` and has a name that ends with `.server.gen.ts`. The public API `index.server.ts` of its segment exports it, and `index.ts` does not (PRD-APP-305). For example, the root layout imports `readPublicConfig` from `@/shared/config/index.server`.

## Notes for the next stories

- The golden test of each part story compares only the files of its part. `PART_FOLDERS` in `tests/test_nextjs_generator.py` gives these folders. `src/_app/api-routes/healthz.gen.ts` belongs to the project files.
- The generator writes the segments `config` and `log` of `src/shared/`. If a part story uses the shared layer writer of the React target, it must not write these segments again.
- The Dockerfile does not copy the migrations yet. Story #182 adds `migrate.gen.mjs` and the migration files to the image.
- The root layout has no providers and no style sheet yet. Story #188 adds the providers, the navigation and the style sheet `src/_app/styles/index.css` of `components.json`.
- The CI job runs Vitest with no tests. The part stories add their tests.
