# React generator: project files and generator frame

Story #167 added the first part of the React generator (phase 2). The generator writes a project that `tsc`, ESLint, Steiger, Vitest and `pnpm build` accept. The page renders an empty root. The next stories of M10 (#155) write the code of the FSD layers.

- Generator: `src/dsml/generate/react.py`. It is in the list `GENERATORS` of `src/dsml/generate/generators.py`.
- Common parts of the layer modules: `src/dsml/generate/react_common.py`.
- Layer modules: `react_shared.py`, `react_entities.py`, `react_features.py`, `react_widgets.py`, `react_pages.py` and `react_app.py` in `src/dsml/generate/`.
- Templates: `src/dsml/templates/react/project/`.
- Tests: `tests/test_react_generator.py`.
- Golden files: `tests/golden/react/order-portal/`, with the manifests in `.dsml/` (story #177). Write them again with `uv run python scripts/write_golden_react.py`.
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
| `steiger.config.ts` | The recommended rules of the FSD plugin of Steiger, with the rules `fsd/repetitive-naming` (story #172) and `fsd/insignificant-slice` off, and the rule `fsd/segments-by-purpose` off for `src/app/providers` (story #174). | PRD-APP-234 |
| `eslint.config.js` | The type-aware rules of `typescript-eslint` (`strictTypeChecked`). | PRD-APP-201, Q64 |
| `src/main.gen.tsx` | The entry module. It reads `/config.json`, configures Amplify Auth and then renders the providers (story #174). | PRD-APP-202, PRD-APP-230, PRD-APP-231 |

The seven fixed-name files are the list of PRD-APP-235. Each other generated file has a name that ends with `.gen.ts` or `.gen.tsx` (PRD-CORE-039).

## Header

Each generated `.ts`, `.tsx` and `.js` file starts with the trace header in `//` comments (PRD-APP-017, PRD-TRACE-005). The elements of the header of a project file are the application. JSON has no comments, thus `package.json`, `tsconfig.json` and `components.json` have no header. The header has only line comments, thus `index.html` also has no header.

## FSD layers

The generator calls the function of each layer module, from the lowest to the highest layer: `shared_files`, `entities_files`, `features_files`, `widgets_files`, `pages_files` and `app_files`. Each function gets a `ReactContext` and gives the files of its layer in `src/<layer>/` (PRD-APP-202). In story #167, each function gives no file.

`react_common.py` gives the rules that all layers use:

- `slice_name` and `file_name` give the kebab case of a model element name, for example `order-list` and `order-list-page` (PRD-APP-206).
- `FsdLayout` gives the layout of the layers (story #179). See "Layout of the layers" below.
- `slice_folder` gives the folder of a slice in the React layout, for example `src/pages/order-list`. The layers `app` and `shared` have no slices.
- `public_api_files` gives the public API of a slice: a generated `index.gen.ts` that re-exports the modules of the slice, and a create-once `index.ts` that re-exports `index.gen.ts` (PRD-APP-204, PRD-CORE-044). A create-once file has no header, because a developer owns it.
- `ReactContext.generated_file` renders a template into a generated file with the header. Each template also gets the layout as `layout`.

### Layout of the layers

Story #179 lets the layer modules write the layer names of the Next.js target (PRD-APP-303 to PRD-APP-305). The layer modules use the standard layer names of `LAYERS`. The layout of the context gives the rest:

| Item | `REACT_LAYOUT` | `NEXTJS_LAYOUT` |
| --- | --- | --- |
| Folder of the layer `app` | `src/app` | `src/_app` |
| Folder of the layer `pages` | `src/pages` | `src/_pages` |
| Folders of the other layers | `src/<layer>` | `src/<layer>` |
| Path alias of `src/` | `@/` | `@/` |
| Server-only public API `index.server.ts` | No | Yes |
| Directive `"use client"` in the forms, the buttons and the widgets (`rsc`) | No | Yes |

- `layer_folder` gives the folder of a layer. `slice_folder` gives the folder of a slice. The method `folder(layout)` of each slice class uses it.
- `import_path` gives the import path of a layer or of a slice with the alias, for example `@/_pages/order-list`. The import methods of the slice classes and the templates of the layers use it. The project templates of the React target, for example `main.gen.tsx.j2`, keep the React layer names.
- `public_api_files` accepts server-only modules. It writes a generated `index.server.gen.ts` and a create-once `index.server.ts` that re-exports it (PRD-APP-305). With the React layout, a server-only module is an error.
- The React generator gives `REACT_LAYOUT`. The default layout of `ReactContext` is also `REACT_LAYOUT`. The golden React output did not change.
- `tests/test_react_layout.py` runs the layer modules on the order portal with the two layouts. With the Next.js layout, only the folders of `app` and `pages` and their import paths change.

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

## Features layer

Story #172 added the features layer: `src/dsml/generate/react_features.py` and the templates in `src/dsml/templates/react/features/`.

The React application gets one slice in `src/features/<operation>/` for each operation with a change of each FastAPI application that it calls (`#Calls`). These are `create`, `update`, `delete` and each custom operation that does not use the method GET. The operations `read` and `list` and a custom operation with the method GET do not change data, thus they give no feature slice. The slice name of a CRUD operation is the operation and the entity, for example `create-order`. The slice name of a custom operation is the name of the exposed action, for example `place-order` (PRD-APP-206).

| File | Content | Requirements |
| --- | --- | --- |
| `api/<operation>.gen.ts` | The function of the operation, for example `createOrder`, and the hook of the TanStack Query mutation, for example `useCreateOrderMutation`. A custom operation also gets its Zod schemas: `<operation>InputSchema` and `<operation>OutputSchema`. | PRD-APP-005, PRD-APP-210, PRD-APP-225 |
| `ui/<operation>-form.gen.tsx` | The TanStack Form form of `create`, `update` or a custom operation, for example `CreateOrderForm`. | PRD-APP-210, PRD-APP-226, PRD-APP-227, PRD-APP-228 |
| `ui/<operation>-button.gen.tsx` | The button of `delete` with a confirmation dialog, for example `DeleteCustomerButton`. | PRD-APP-210, PRD-APP-227, PRD-APP-228 |
| `index.gen.ts`, `index.ts` | The public API of the slice. `index.ts` is a create-once file. | PRD-APP-204 |

The rules of the mutations:

- The function of `create` and `update` parses the request body with the input schema of the entity slice, and the response with the output schema of the entity slice.
- The function of a custom operation parses its input with its own input schema. The `in` parameters in the path go into the path. The other `in` parameters are the request body. The input schema and the output schema follow the Pydantic models of the called application. Thus the field names are the JSON names in snake case, for example `order_id`.
- A decimal `in` parameter of a custom operation has no precision. The function `decimalValue` accepts a number, or a text with a decimal number.
- After a success, the mutation invalidates the queries of each changed entity with the query key of its entity slice, for example `["order"]` (PRD-APP-225). The changed entities of a custom operation are the entities of its parameters that have an entity slice.

The rules of the forms:

- The Zod schema of the operation is the validator of the form (`validators.onSubmit`, PRD-APP-226). The form shows the error of a field after the user touches the field. A submit touches all fields.
- Each field uses the shadcn/ui components `Field`, `FieldLabel` and `FieldError`. The label is the field name in words, for example `Order id` for `order_id`.
- The control of a field follows the field type: `NativeSelect` for an enumeration, a check box for a Boolean, a number input for an integer or a real number, a date input for a date, a `datetime-local` input for a date and time, and a text input for the other types. A text field with no `maxLength`, or a `maxLength` more than 200, uses a `Textarea`. A list parameter uses a `Textarea` with one value on each line. A list of numbers or Boolean values gives an error, because the target has no control for it.
- An empty optional field gives no value. A required number field with no value gives `NaN`, thus the schema refuses it.
- An error of the mutation shows in an `Alert`. For a problem details response, the alert shows the `title` and the `detail` (PRD-APP-227).
- The component gets the optional properties `defaultValues` and `onSuccess`. The form of `update` and the button of `delete` also get the key of the entity.
- The forms use native controls and the Radix UI alert dialog. Thus the user can reach each control with the Tab key (PRD-APP-228).

The features layer added the shadcn/ui components `alert-dialog`, `field`, `label`, `native-select` and `separator` to the pinned copy. They need the packages `@radix-ui/react-alert-dialog`, `@radix-ui/react-label`, `@radix-ui/react-separator` and `lucide-react`. The component tests need `jsdom` and Testing Library, thus the generated `package.json` has these dev dependencies: `jsdom`, `@testing-library/dom`, `@testing-library/react` and `@testing-library/user-event`. A test file selects the DOM environment with the comment `// @vitest-environment jsdom`. The default environment of Vitest stays `node`.

The slice names of the features layer repeat the entity names, for example `create-order` and `place-order`. Thus the generated `steiger.config.ts` sets the rule `fsd/repetitive-naming` off.

## Widgets layer

Story #173 added the widgets layer: `src/dsml/generate/react_widgets.py` and the templates in `src/dsml/templates/react/widgets/`.

The React application gets one widget slice for each entity of its list views and one for each entity of its detail views (PRD-APP-210). Two views of one kind for one entity give one slice. The entity must have an entity slice with the operation `list` (list view) or `read` (detail view). If not, `dsml generate` stops with an error.

| File | Content | Requirements |
| --- | --- | --- |
| `<entity>-list/ui/<entity>-table.gen.tsx` | The table of the entity, for example `OrderTable`. It has a column header for each field and paging with `limit` and `offset`. | PRD-APP-114, PRD-APP-210, PRD-APP-228 |
| `<entity>-details/ui/<entity>-details.gen.tsx` | The details of one entity, for example `OrderDetails`. A description list shows each field. | PRD-APP-210 |
| `index.gen.ts`, `index.ts` | The public API of the slice. `index.ts` is a create-once file. | PRD-APP-204 |

The rules of the widgets:

- A widget reads the data with `useQuery` and the query options of the entity slice. Thus it uses the same query keys as the loaders of the pages (PRD-APP-223, PRD-APP-224).
- The table and the details show the key first, then the other fields in the order of the schema. The column header is the field name in words, as the label of a form field. A Boolean value shows as `Yes` or `No`. A `null` value shows as an empty text.
- The table gets the optional properties `pageSize` (1 to 200, the default is 50) and `actions`. `actions` gives the controls of one row, for example a link to the details or the delete button. If `actions` is set, the table has the column "Actions". The pages story (#174) gives these controls, because a widget cannot import the routes of the app layer.
- The buttons "Previous page" and "Next page" change the `offset` by `pageSize`. The text below the table gives the items on the page and the number of all items. While the next page loads, the table shows the previous page (`keepPreviousData`).
- The details widget gets the key of the entity, for example `id`.
- An error of the query shows in an `Alert`. For a problem details response, the alert shows the `title` and the `detail` (PRD-APP-227).
- The column headers are `th` elements with `scope="col"`. The paging controls are native buttons, thus the user can reach each control with the Tab key (PRD-APP-228).

## Pages layer

Story #174 added the pages layer: `src/dsml/generate/react_pages.py` and the templates in `src/dsml/templates/react/pages/`.

The React application gets one slice in `src/pages/<view>/` for each view (PRD-APP-210). The page combines the widgets and the features of the view.

| File | Content | Requirements |
| --- | --- | --- |
| `ui/<view>-page.gen.tsx` | The page of the view, for example `OrderListPage`. The title is the view name in words. The documentation of the view is the description. | PRD-APP-210 |
| `index.gen.ts`, `index.ts` | The public API of the slice. `index.ts` is a create-once file. | PRD-APP-204 |

The rules of the pages:

- A list view shows the table of its entity. The property `actions` of the table gives a link "Details" to the detail view of the entity, if the application has one. It also gives the delete button, if the entity has the operation `delete`.
- A detail view shows the details widget. The page gets the key `id` from the route.
- A form view shows the form of its operation. The operation must be a custom operation of a called application with a method other than GET. After a success, the page shows a status message.
- Each view has one route path (PRD-APP-221): `/<entities>` for a list view, `/<entities>/$id` for a detail view and `/<operation>` for a form view. `<entities>` is the kebab case of the exposed entity, for example `/orders`. `<operation>` is the feature slice name, for example `/place-order`. Two views with one path give an error.

## App layer

Story #174 added the app layer: `src/dsml/generate/react_app.py` and the templates in `src/dsml/templates/react/app/`. The layer `app` has no slices.

| File | Content | Requirements |
| --- | --- | --- |
| `router/routes.gen.tsx` | The route tree with code-based routing. The root route reads the session before each navigation. The routes are the home page `/`, the callback URL `/auth/callback` and one route for each view. | PRD-APP-220, PRD-APP-221, PRD-APP-222, PRD-APP-223 |
| `router/views.gen.ts` | `VIEWS`: the path, the title and the access rule (`public` and `roles`) of each view. `NAVIGATION`: the views of the navigation, in the order of the model. | PRD-APP-221, PRD-DSML-032, PRD-DSML-033 |
| `router/access.gen.ts` | `checkAccess` and `requireView`: the check of the session and the roles. `isPermitted` tells if the session permits a view. | PRD-APP-009, PRD-APP-222 |
| `router/router.gen.ts` | `createAppRouter`: the router with the query client in its context. A test can give a memory history. | PRD-APP-220 |
| `layout/navigation.gen.tsx` | `Navigation`: the views of `NAVIGATION` that the roles of the user permit. | PRD-APP-009 |
| `layout/app-layout.gen.tsx` | `AppLayout`: the title, the navigation, the button "Log in" or "Log out", and the page. | PRD-APP-009 |
| `layout/status-pages.gen.tsx` | The home page, the "not permitted" page, the "not found" page and `RouteError`, the error component of the routes. | PRD-APP-222 |
| `providers/query-client.gen.ts` | `createQueryClient`. The data of a query stays fresh for 30 seconds, thus a widget does not read the data of the loader again. | PRD-APP-223 |
| `providers/app-providers.gen.tsx` | `AppProviders`: the providers of TanStack Query and of the router. | PRD-APP-201 |
| `providers/session.gen.ts` | `startSession`: read `/config.json` and configure Amplify Auth. The entry module calls it before the first render. | PRD-APP-230, PRD-APP-231 |
| `styles/index.css` | The Tailwind CSS file with the theme variables of shadcn/ui. It is a create-once file, thus a developer can change the theme. | PRD-APP-212 |

The rules of the routes:

- The `beforeLoad` function of each view route is `requireView(VIEWS.<view>)`. A public view needs no session. With no session, the function starts the login and gives a `LoginStartedError`. The page shows "Wait for the login page.". With no permitted role, the function gives a `NotPermittedError`, and `RouteError` shows the "not permitted" page (PRD-APP-222). The roles are the user pool groups of the session.
- `beforeLoad` runs before the loader. Thus a route loads no data with no session or with no permitted role.
- The loader of a list route calls `queryClient.ensureQueryData(list<Entity>QueryOptions())`. The loader of a detail route calls `queryClient.ensureQueryData(read<Entity>QueryOptions(params.id))` (PRD-APP-223). The query key of the loader of a list route is the key of the first page of the table.
- The route `/auth/callback` goes to the home page. Amplify Auth reads the code of the login while the root route reads the session.
- A detail view in the navigation gives an error, because it needs the key of an entity.

## External API

Story #175 added the client of an external API. A `react` application can call an external API from an imported OpenAPI file in place of an application of the model (PRD-APP-006). The IR adapter converts the file into IR entities and operations (story #163, `docs/notes/openapi-import.md`). The module `src/dsml/generate/react_external.py` reads these IR elements. The entities layer and the features layer write the client from them. The generator does not read the OpenAPI file.

The names in the client are the names of the OpenAPI file: the schemas, the properties, the operations (`operationId`) and the parameters. Thus the client sends and reads the JSON names of the file.

| Item of the external API | Output | Requirements |
| --- | --- | --- |
| An object schema of a success response | One entity slice, for example `src/entities/pet/`. `model/<schema>.gen.ts` has the Zod schema and its type. It also has the schemas that the schema refers to, before it. These schemas are not exported. | PRD-APP-006, PRD-APP-210 |
| An operation with the method GET | The query key and the query options in `api/<schema>-queries.gen.ts` of the slice of its response, for example `readPetQueryOptions`. | PRD-APP-006, PRD-APP-224 |
| An operation with an other method | One feature slice, as a custom operation, for example `src/features/create-pet/`. The input schema has the path parameters, the query parameters and the properties of the request body. The output schema is the schema of the entity slice of the response. | PRD-APP-006, PRD-APP-225, PRD-APP-226 |

The rules of the external API:

- An object schema of a request body gives no entity slice. Its properties are the fields of the form.
- The query key of an operation is `[<slice>, <operation>, <parameters>]`, for example `["pet", "readPet", { petId }]`. An operation with no parameters has the key `[<slice>, <operation>]`. If all parameters are optional, the parameters have the default `{}`.
- An optional query parameter with no value is not in the query. An optional property can be missing or `null`.
- A decimal property in a response is a number or a text, because the OpenAPI file gives `anyOf` with `number` and `string`. A decimal value in a request uses the function `decimalValue`.
- An array property in a request is a list field with one value on each line. The form sends an empty array if the list is empty.
- After a success, a mutation invalidates the queries of each entity slice of the external API with queries. The OpenAPI file does not tell which schemas an operation changes.
- The operations of each method get a form. Thus an operation with the method DELETE gets a form with its path parameters, not a button.

These items give an error, because the target has no code for them: an operation with the method GET and no JSON response, a property of a request body that refers to an object schema, an array of numbers or Boolean values in a request, a parameter and a property of the request body with one name, a schema that refers to itself, and a property or a parameter with a name that is not a TypeScript identifier.

An entity slice of an external API and an entity slice of a called application with one slice name give an error.

The test model is `tests/models/react/external-api/external-api.sysml` with the OpenAPI file `pet-store.openapi.json`. Its golden output is the full project in `tests/golden/react/external-api/`. The tests are in `tests/test_react_external_api.py`.

The model has no views. An application with no views has an empty navigation. Thus `views.gen.ts` gives the type `readonly View[]` to the empty constant `NAVIGATION`. Without the type, `tsc` refuses the navigation component.

## Golden files and tests

The golden folder is the project folder of the application `orderPortal` of the order portal model. The configuration file of the golden output gives the output folder `.`. Thus the manifests `.dsml/generated.json` and `.dsml/trace.gen.json` are in the golden folder, and their paths start at the project folder (story #177, PRD-CORE-040, PRD-TRACE-006).

The test of the project files compares only the files outside the layer folders `src/<layer>/` and `.dsml/`. The test of each layer story compares the folder of its layer. The test of the full output writes all files and the manifests, as `dsml generate` does, and compares all bytes with the golden folder (PRD-CORE-029, PRD-CORE-030).

The trace manifest gives the symbols of each TypeScript module with a top-level declaration. These generated files have no symbols, thus they are not in the trace manifest: the public API files `index.gen.ts` (they only re-export), the entry module `src/main.gen.tsx`, `steiger.config.ts` and `vite.config.ts`. The FastAPI generator also writes no entry for a file with no symbol, for example `__init__.py`.

The CI job "React golden project" does these steps:

1. It runs Prettier in check mode on `tests/golden/react/` and `tests/react/` (PRD-CORE-035). The manifests in `.dsml/` are JSON files, thus Prettier also examines them.
2. It copies the order portal model and its `dsml.toml` to a temporary folder. It runs `dsml generate` there. This writes the full output of the model: `services/order-api` and `apps/order-portal` (story #177).
3. It compares `apps/order-portal` with the golden folder, but not `.dsml/`. In the full output, the manifests are in the folder of the configuration file.
4. It runs `pnpm install` in `apps/order-portal`, and `uv lock` and `uv sync` in `services/order-api`. The install makes the lockfiles in the temporary folder.
5. It runs `dsml check-output` with no option. The command runs ruff and pyright on the FastAPI application, and `tsc --noEmit`, ESLint and Steiger with the generated `steiger.config.ts` on the React application (stories #170 and #177, PRD-APP-016, `docs/notes/check-output.md`).
6. It copies `tests/react/app/`, `tests/react/features/`, `tests/react/field-rules/`, `tests/react/shared/` and `tests/react/widgets/` into `apps/order-portal/tests/` and runs Vitest. The field rule test gives the values of `order-portal.json` to the Zod schemas. `tests/test_react_entities.py` gives the same values to the Pydantic models of the golden FastAPI output. Both must accept and refuse the same values (PRD-APP-211). The shared layer test replaces `fetch` and the Amplify modules. It examines the runtime configuration, the configuration of Amplify Auth, the bearer token and the problem details errors. The features test renders the forms with Testing Library in jsdom. It examines a field error, a problem details error, the keyboard access, the requests and the invalidation of the entity queries after a mutation. The widgets test renders the table and the details. It examines the column headers, the change to the next page, the keyboard access and a problem details error. The app test renders the application with a memory history. It examines the start of the login with no session, the "not permitted" page, the route loaders, the link to the details and the navigation for each set of roles.
7. It copies the golden project of the external API model to `apps/pet-portal` in a second temporary folder, with the model, its `dsml.toml` and the OpenAPI file. It runs `pnpm install` and `dsml check-output --application petPortal` (story #175).
8. It runs `pnpm build` with marker values in `VITE_` environment variables. It makes sure that `dist/index.html` exists, that `dist/` has no `config.json`, and that `dist/` contains no marker value and no Cognito domain (PRD-APP-233).

## Phase 2 exit

Story #177 completed the checks of the full React output and the phase 2 exit criteria that do not need AWS.

| Check | Where | Requirements |
| --- | --- | --- |
| The full React output of the order portal, with the manifests, agrees with the golden files. | `tests/test_react_generator.py`, and step 3 of the CI job | PRD-CORE-029, PRD-CORE-030, PRD-CORE-040, PRD-TRACE-006 |
| The environment and the clock do not change the full output of the order portal. The output has no absolute path, no user name and no host name. | `tests/test_determinism.py`, in the CI job "Check (linux-x64)" | PRD-CORE-015, PRD-CORE-028, PRD-CORE-033, Q62 |
| The coverage, orphans, impact and suspect reports of the order portal agree with the golden files. The coverage report shows each requirement as `verified`. | `tests/test_trace_reports.py`, `tests/test_trace_changes.py`, `tests/golden/trace/order-portal.*` | PRD-TRACE-001 to PRD-TRACE-018 |
| `dsml check-output` finds no error on the full output. | Step 5 of the CI job | PRD-APP-016, PRD-APP-234 |
| `dist/` of `pnpm build` contains no environment value. | Step 8 of the CI job | PRD-APP-233 |

The determinism test runs `tests/dsml_test_command.py` with the environment variable `DSML_TEST_GENERATORS=toolchain`. Thus the script keeps the generators of the toolchain in place of the test generator. The configuration file of the test gives an output folder to each generator: the FastAPI application, the React application, the infrastructure and the workflows.

`scripts/write_golden_reports.py` writes the reports of the order portal from a project with the full output of `dsml generate`. The Vitest tests of `tests/react/` are in `apps/order-portal/tests/`, as in the CI job. The verifications V-003 and V-004 of the order portal model name these test files:

- V-003 (R-003, the list and the details of the orders): `app.test.tsx`, `shared.test.ts` and `widgets.test.tsx`.
- V-004 (R-004, the form that places an order): `features.test.tsx` and `field-rules.test.ts`.

The model folder `docs/model/examples/order-portal/` has no test files. Thus `dsml validate` on the model gives the warning COV-006 for each test file. In the project of the reports, only V-001 gets COV-006. The FastAPI generator writes the tests of the order API as generated files in `services/order-api/tests/`, not the hand-written file of V-001.

The Git repository of the impact and suspect reports of the order portal keeps only the configuration file and the model. Its `.gitignore` names the output folders. Thus a change to a generator does not change the commit hashes in these reports. A change to the file list or to the symbols of a generator can change the reports. Then run `uv run python scripts/write_golden_reports.py`.

The phase 2 exit criterion "The reference model with a React application and a FastAPI application deploys to dev" waits for an AWS account (Q58, M8 #142).

## Differences from the story text

- The story gives `src/main.tsx` as a generated file. PRD-CORE-039 and PRD-APP-235 permit only names that end with `.gen.<ext>` and the fixed-name list. `main.tsx` is not on that list. Thus the entry module is `src/main.gen.tsx`.
- Story #174: the Steiger rule `fsd/insignificant-slice` stays off in the generated configuration. Each model element has its own slice (PRD-APP-210). Thus only the page of a form view uses the feature slice of its operation, and no page uses the feature slice of an operation with no form view. The rule finds these slices.
- Story #174: the Steiger rule `fsd/segments-by-purpose` refuses the segment name `providers`. PRD-APP-210 gives this name, thus the rule is off for `src/app/providers`.
- Story #177: the story asks that the status of each verified requirement becomes `verified`. The coverage report gives this status from the links (PRD-TRACE-014). The attribute `status` of the requirements in the model stays `approved`, as in the order service model of phase 1.
- Story #174: TanStack Query 5.104 marks `queryClient.ensureQueryData` as deprecated. PRD-APP-223 gives this method. Thus `routes.gen.tsx` sets the ESLint rule `@typescript-eslint/no-deprecated` off. A change to PRD-APP-223 can replace the method with `queryClient.query` and `staleTime: "static"`.

## Items for the next stories

- The application reads one API base URL, `apiBaseUrl` in `/config.json`. Thus an application that calls an application of the model and an external API sends the requests of both to one URL.

- With pnpm 12, `pnpm install` can write `pnpm-workspace.yaml` in the project (the setting `minimumReleaseAgeExclude`). `pnpm-lock.yaml` and this file do not have the Prettier format. Thus `prettier --check .` in the generated pipeline finds them. The project has no `.prettierignore`, because the file is not on the fixed-name list of PRD-APP-235. The M10 exit criterion examines only the golden files, and Prettier finds no change in them. Thus this item stays open.
