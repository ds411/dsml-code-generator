# React generator: project files and generator frame

Story #167 added the first part of the React generator (phase 2). The generator writes a project that `tsc`, ESLint, Steiger, Vitest and `pnpm build` accept. The page renders an empty root. The next stories of M10 (#155) write the code of the FSD layers.

- Generator: `src/dsml/generate/react.py`. It is in the list `GENERATORS` of `src/dsml/generate/generators.py`.
- Common parts of the layer modules: `src/dsml/generate/react_common.py`.
- Layer modules: `react_shared.py`, `react_entities.py`, `react_features.py`, `react_widgets.py`, `react_pages.py` and `react_app.py` in `src/dsml/generate/`.
- Templates: `src/dsml/templates/react/project/`.
- Tests: `tests/test_react_generator.py`.
- Golden files: `tests/golden/react/order-portal/`. Write them again with `uv run python scripts/write_golden_react.py`.
- CI: the job "React golden project" in `.github/workflows/ci.yml`.

## Inputs

The generator reads only the IR and the configuration (PRD-APP-001, PRD-CORE-026). It writes files for each application with `target = Target::react`.

- The key `applications.<name>.output` gives the output folder of the application (PRD-APP-002). If the key is missing, `dsml generate` stops with an error.
- The key `applications.<name>.dependencies` gives extra run-time dependencies in the form `<package>@<version>`, for example `date-fns@4.1.0` or `@scope/package@1.2.3`. The generator adds them to `dependencies` in `package.json`, in sorted order (PRD-CORE-046). An extra dependency must not be a package of the target. The version baseline gives the version of these packages (PRD-TOP-008).
- The versions come from `src/dsml/versions.toml` (PRD-APP-201). `docs/notes/typescript-baseline.md` gives the items.

## Output

All files are generated files. The generator writes them again at each run. It does not write `pnpm-lock.yaml` (PRD-CORE-036).

| File | Content | Requirements |
| --- | --- | --- |
| `package.json` | The pinned run-time and dev dependencies, the scripts, `packageManager` (pnpm) and `devEngines` (Node.js). | PRD-APP-201, PRD-CORE-046, PRD-TOP-008 |
| `tsconfig.json` | Strict TypeScript. The path alias `@/*` to `./src/*`. | PRD-APP-201, PRD-APP-205 |
| `vite.config.ts` | The React and Tailwind CSS plugins. The alias `@/` to `/src/`. The output folder `dist/`. The Vitest settings. | PRD-APP-205, PRD-APP-233, Q64 |
| `index.html` | The page. It loads `src/main.gen.tsx`. | PRD-APP-233 |
| `components.json` | The settings of shadcn/ui: the components are in `@/shared/ui`. | PRD-APP-201, Q41 |
| `steiger.config.ts` | The recommended rules of the FSD plugin of Steiger. | PRD-APP-234 |
| `eslint.config.js` | The type-aware rules of `typescript-eslint` (`strictTypeChecked`). | PRD-APP-201, Q64 |
| `src/main.gen.tsx` | The entry module. It renders an empty root. | PRD-APP-202 |

The seven fixed-name files are the list of PRD-APP-235. Each other generated file has a name that ends with `.gen.ts` or `.gen.tsx` (PRD-CORE-039).

## Header

Each generated `.ts`, `.tsx` and `.js` file starts with the trace header in `//` comments (PRD-APP-017, PRD-TRACE-005). The elements of the header of a project file are the application. JSON has no comments, thus `package.json`, `tsconfig.json` and `components.json` have no header. The header has only line comments, thus `index.html` also has no header.

## FSD layers

The generator calls the function of each layer module, from the lowest to the highest layer: `shared_files`, `entities_files`, `features_files`, `widgets_files`, `pages_files` and `app_files`. Each function gets a `ReactContext` and gives the files of its layer in `src/<layer>/` (PRD-APP-202). In story #167, each function gives no file.

`react_common.py` gives the rules that all layers use:

- `slice_name` and `file_name` give the kebab case of a model element name, for example `order-list` and `order-list-page` (PRD-APP-206).
- `slice_folder` gives the folder of a slice, for example `src/pages/order-list`. The layers `app` and `shared` have no slices.
- `public_api_files` gives the public API of a slice: a generated `index.gen.ts` that re-exports the modules of the slice, and a create-once `index.ts` that re-exports `index.gen.ts` (PRD-APP-204, PRD-CORE-044). A create-once file has no header, because a developer owns it.
- `ReactContext.generated_file` renders a template into a generated file with the header.

## Entities layer

Story #168 added the entities layer: `src/dsml/generate/react_entities.py` and the templates in `src/dsml/templates/react/entities/`.

The React application gets one slice in `src/entities/<entity>/` for each exposed entity of each FastAPI application that it calls (`#Calls`). The slice uses the CRUD slices of the FastAPI generator (`dsml.generate.fastapi_slices`). Thus the Zod schemas and the Pydantic models come from the same IR entities and operations (PRD-APP-005).

| File | Content | Requirements |
| --- | --- | --- |
| `model/<entity>.gen.ts` | The output schema `<entity>Schema`, the page schema `<entity>PageSchema` (if the entity has `list`), the input schemas `create<Entity>InputSchema` and `update<Entity>InputSchema` (if the entity has `create` or `update`), and their TypeScript types. | PRD-APP-112, PRD-APP-115, PRD-APP-210, PRD-APP-211 |
| `api/<entity>-queries.gen.ts` | The query keys and the TanStack Query options of `read` and `list`, if the entity has these operations. | PRD-APP-114, PRD-APP-210, PRD-APP-224 |
| `index.gen.ts`, `index.ts` | The public API of the slice. `index.ts` is a create-once file. | PRD-APP-204 |

The rules of the schemas:

- The field names are the JSON names of the API. A related entity is its key (PRD-APP-115).
- An input schema is a strict object, because the Pydantic input models refuse other fields. The key is not in an input schema.
- A nullable field accepts `null` and can be missing. Each field of the update input can be missing. The field rules become Zod rules: `min` and `max` for `minLength`, `maxLength`, `minValue` and `maxValue`, and `regex` for `pattern` (PRD-APP-112, PRD-APP-211).
- A `Decimal` value in a request is a number or a text. The function `decimal` in the model file applies the precision, the scale, `minValue` and `maxValue` as Pydantic does. Pydantic ignores the zeros at the start and at the end of the value. The client does not accept a text with an exponent, for example `1e2`.
- A `Decimal` value in a response is a text, as in `openapi.gen.json`. An output schema has no field rules, as the Pydantic output model.
- `z.guid()` checks a UUID, because Pydantic accepts each UUID form with hexadecimal digits.

Each query key is an array `[<entity>, <operation>, <parameters>]` (PRD-APP-224), for example `["order", "read", { id }]` and `["order", "list", { limit, offset }]`. The key of all queries of an entity is `["order"]`. The features story (#172) uses it to invalidate the queries after a mutation (PRD-APP-225). The list key gives the default values of `limit` (50) and `offset` (0), so the two forms of one request have one key.

The query functions call `apiRequest` from `@/shared/api`. The function takes an object with `method`, `path`, `query`, `body` and `signal`, and gives the JSON body of the response as `unknown`. The query function parses the body with the Zod schema. The shared layer (story #169) writes `apiRequest`.

The model files and the query files have trace symbols (PRD-TRACE-006). `src/dsml/generate/typescript_symbols.py` finds the top-level declarations of a generated TypeScript file. A function gives a symbol of the kind `function`. A constant, a type or an interface gives a symbol of the kind `class`.

## Shared layer

Story #169 added the shared layer: `src/dsml/generate/react_shared.py`, the templates in `src/dsml/templates/react/shared/` and the pinned copy of shadcn/ui in `src/dsml/templates/react/shadcn-ui/`. The layer `shared` has no slices. Each segment has a public API: a generated `index.gen.ts` and a create-once `index.ts`, as a slice has. Thus other layers import `@/shared/api`, `@/shared/auth`, `@/shared/config`, `@/shared/lib` and `@/shared/ui`.

| File | Content | Requirements |
| --- | --- | --- |
| `config/runtime-config.gen.ts` | `loadRuntimeConfig` reads `/config.json` and parses it with `runtimeConfigSchema`. `runtimeConfig` gives the loaded values. The keys are `apiBaseUrl`, `region`, `userPoolId`, `appClientId` and `loginDomain`: the constant `CONFIGURATION_KEYS` of the pipeline generator. | PRD-APP-010, PRD-APP-230 |
| `auth/amplify.gen.ts` | `configureAuth` configures Amplify Auth with Cognito managed login and the authorization code flow (`responseType: "code"`). Amplify uses PKCE with this flow. The callback path `/auth/callback`, the logout path `/` and the scopes are the values of the app client of the user directory (PRD-IAC-019). `currentSession` gives the access token and the groups (`cognito:groups`). `startLogin` and `logout` start the login and the logout. | PRD-APP-007, PRD-APP-231 |
| `api/client.gen.ts` | `apiRequest` adds the access token as a bearer token. An error response gives an `ApiError`. For a problem details response, the error has the `title` and the `detail`, and the message is `<title>: <detail>`. | PRD-APP-014, PRD-APP-227, PRD-APP-232 |
| `ui/*.tsx`, `lib/utils.ts` | The shadcn/ui components and the function `cn`. These are create-once files from the pinned copy. | PRD-APP-212, PRD-CORE-048 |

The copy has the components `alert`, `button`, `card`, `input`, `table` and `textarea`. They use only the packages of the version baseline. `src/dsml/templates/react/shadcn-ui/README.md` gives the source commit, the changes to the source files and the steps to update the copy. The features story (#172) and the widgets story (#173) can add components. A component such as `label`, `dialog` or `alert-dialog` needs a Radix UI package. Add that package to the version baseline and to `RUNTIME_PACKAGES` first.

No generated file contains an environment value (PRD-APP-233). The application reads the values from `/config.json` at run time.

## Golden files and tests

The golden folder is the project folder of the application `orderPortal` of the order portal model. It has no manifests in `.dsml/`. The phase 2 exit story (#177) adds them.

The test of the project files compares only the files outside the layer folders `src/<layer>/`. The test of each layer story compares the folder of its layer. Thus the stories of one step change different golden files.

The CI job "React golden project" does these steps:

1. It runs Prettier in check mode on `tests/golden/react/` and `tests/react/` (PRD-CORE-035).
2. It copies the golden project to a temporary folder. Then it runs `pnpm install`. The install makes `pnpm-lock.yaml` in the copy.
3. It runs `tsc --noEmit`, ESLint and Steiger. While the golden project has no folder `src/pages`, Steiger uses `tests/react/steiger-before-pages.config.ts`. This configuration sets the rule `fsd/insignificant-slice` off, because no page refers to the entity slices yet.
4. It copies `tests/react/field-rules/` and `tests/react/shared/` into the copy and runs Vitest. The field rule test gives the values of `order-portal.json` to the Zod schemas. `tests/test_react_entities.py` gives the same values to the Pydantic models of the golden FastAPI output. Both must accept and refuse the same values (PRD-APP-211). The shared layer test replaces `fetch` and the Amplify modules. It examines the runtime configuration, the configuration of Amplify Auth, the bearer token and the problem details errors.
5. It runs `pnpm build` with marker values in `VITE_` environment variables. It makes sure that `dist/index.html` exists, that `dist/` has no `config.json`, and that `dist/` contains no marker value and no Cognito domain (PRD-APP-233).

## Differences from the story text

- The story gives `src/main.tsx` as a generated file. PRD-CORE-039 and PRD-APP-235 permit only names that end with `.gen.<ext>` and the fixed-name list. `main.tsx` is not on that list. Thus the entry module is `src/main.gen.tsx`.

## Items for the next stories

- `components.json` gives `src/app/styles/index.css` as the Tailwind CSS file. The story that writes the app layer must write this file and import it in the entry module.
- The pages story (#174) makes the pages refer to the entity slices. Then the CI job uses the generated `steiger.config.ts`, and `tests/react/steiger-before-pages.config.ts` can go.
- The pages story (#174) writes the entry module and the app layer. Before the first render, the entry module must call `loadRuntimeConfig` and then `configureAuth` (PRD-APP-230, PRD-APP-231). The router must have the route `/auth/callback`. `beforeLoad` can use `currentSession` and `startLogin` (PRD-APP-222).
- The app layer must write the Tailwind CSS theme variables of shadcn/ui (for example `--primary`) in `src/app/styles/index.css`, because the components use them.
- With pnpm 12, `pnpm install` can write `pnpm-workspace.yaml` in the project (the setting `minimumReleaseAgeExclude`). `pnpm-lock.yaml` and this file do not have the Prettier format. Thus `prettier --check .` in the generated pipeline finds them. The project has no `.prettierignore`, because the file is not on the fixed-name list of PRD-APP-235.
