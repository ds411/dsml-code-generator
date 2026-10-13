# Generated code

This page tells what `dsml generate` writes from a model, and where you write your own code. You do not need to know FastAPI, React, Next.js, OpenTofu or GitHub Actions before you read it. The [concepts](concepts.md) page gives the three kinds of files. The [glossary](glossary.md) gives a short meaning for each term.

The examples come from the golden files of this repository. A golden file is the expected output of a generator for a reference model. The tests of the toolchain compare each run with the golden files.

| Reference model | Applications | Golden files |
| --- | --- | --- |
| [Order service](../model/examples/order-service.sysml) | `orderApi` (FastAPI) | [FastAPI](../../tests/golden/fastapi/order-service), [infrastructure](../../tests/golden/infrastructure/order-service), [pipelines](../../tests/golden/pipelines/order-service) |
| [Order portal](../model/examples/order-portal/order-portal.sysml) | `orderApi` (FastAPI) and `orderPortal` (React) | [FastAPI](../../tests/golden/fastapi/order-portal), [React](../../tests/golden/react/order-portal), [infrastructure](../../tests/golden/infrastructure/order-portal), [pipelines](../../tests/golden/pipelines/order-portal) |
| [Order web](../model/examples/order-web/order-web.sysml) | `orderWeb` (Next.js) | [Next.js](../../tests/golden/nextjs/order-web), [infrastructure](../../tests/golden/infrastructure/order-web), [pipelines](../../tests/golden/pipelines/order-web) |

Phase 1 has the FastAPI target, the infrastructure and the pipelines. The React target and the Next.js target come in later phases. This page also tells about them, because their generators and golden files are in the repository.

## Where the generator writes the files

The configuration file `dsml.toml` gives one output folder for each part of the output. Each path is relative to the folder of the configuration file.

```toml
schema = 1

[model]
paths = ["model"]

[applications.orderApi]
output = "services/order-api"

[applications.orderPortal]
output = "apps/order-portal"

[infrastructure]
output = "infra"

[pipelines]
output = ".github/workflows"
```

- The name after `applications.` is the name of the application in the model, for example `orderApi`.
- The generator writes no infrastructure file if the key `infrastructure.output` is missing.
- `dsml generate --application orderApi` writes only the files of one application. `dsml generate --infrastructure` and `dsml generate --pipelines` write only one part.

The generator also writes two manifests in the folder `.dsml/` beside the configuration file:

- `.dsml/generated.json` gives each file that the generator owns.
- `.dsml/trace.gen.json` gives the code of each model element. The [reports](reports.md#the-trace-manifest) page tells about it.

## The kinds of files

The generator writes three kinds of files. A developer writes the fourth kind.

| Kind | How you find it | What the generator does at each run | Can you change it? |
| --- | --- | --- | --- |
| Generated file | The name ends with `.gen.<ext>` or `_gen.py`, for example `main_gen.py` or `main.gen.tf`. | It writes the file again. It deletes the file if the model no longer needs it. | No. |
| Fixed-name file | The name is on the fixed-name list of the target, for example `pyproject.toml` or `Dockerfile`. | The same as a generated file. | No. |
| Create-once file | The manifest gives it in the list `createOnce`, for example `handler.py`. | It writes the file only if the file does not exist. | Yes. After the first run, you own it. |
| Hand-written file | Any other file. | Nothing. It does not read, change or delete the file. | Yes. |

A fixed-name file is a generated file with a name that a tool requires. For example, uv must find `pyproject.toml`, and Docker must find `Dockerfile`. Thus the name cannot end with `.gen`.

| Target | Fixed-name files |
| --- | --- |
| FastAPI | `pyproject.toml`, `Dockerfile`, `.dockerignore`, `alembic.ini`, `migrations/env.py` and each `__init__.py` in a generated folder |
| React | `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `components.json`, `steiger.config.ts` and `eslint.config.js` |
| Next.js | `package.json`, `tsconfig.json`, `next.config.ts`, the full `app/` folder, `proxy.ts`, `drizzle.config.ts`, `components.json`, `steiger.config.ts`, `eslint.config.js`, `vitest.config.ts`, `migrations/meta/_journal.json`, `Dockerfile` and `.dockerignore` |
| Infrastructure | None. Each file name ends with `.gen.tf` or `.gen.md`. |
| Pipelines | None. Each file name ends with `.gen.yml` or `.gen.md`. |

### The manifest of the generated files

The file `.dsml/generated.json` gives the path and the SHA-256 hash of each generated file and fixed-name file. It gives only the path of each create-once file. This part comes from the golden manifest of the order service:

```json
{
  "createOnce": [
    {
      "part": "application/orderApi",
      "path": "services/order-api/app/features/order/cancel_order/handler.py"
    }
  ],
  "generated": [
    {
      "part": "application/orderApi",
      "path": "services/order-api/.dockerignore",
      "sha256": "17520f6e359f6b2831d79c0befca31c35d67319173228d0f4c8a50eee951db74"
    },
```

Commit the manifest with the code. The generator uses the hashes to find a generated file that a person changed. Then `dsml generate` stops with an error, and writes no file:

```text
dsml: error: services/order-api/app/main_gen.py: The file is different from its hash in the manifest.
dsml: error: No file was written. Use --overwrite to replace or delete these files.
```

To keep your change, move it into a hand-written file, or change the model. To discard your change, run `dsml generate --overwrite`.

### The header of a generated file

Each generated source file that permits comments starts with two lines. The first line tells that the generator owns the file. The second line gives the model elements of the file. This header comes from the golden file `app/features/order/cancel_order/endpoint_gen.py` of the order service:

```python
# Generated by dsml 0. Do not edit.
# Elements: OrderService::CancelOrder, OrderService::Order, OrderService::orderApi::cancelOrder
```

The number is the major version of the toolchain. A create-once file has no header, because you own it.

## FastAPI application

The FastAPI target writes a REST API in Python. The code uses FastAPI for the HTTP endpoints, Pydantic for the data checks, SQLAlchemy for the database access, and Alembic for the database migrations. uv manages the Python project.

Each operation is one vertical slice: one folder with all the code of the operation. Code that all slices use is in `app/shared/`. These paths are relative to the output folder `services/order-api`:

```text
app/
├── main_gen.py                          # makes the application, adds the router of each slice
├── migrate_gen.py                       # applies the database migrations
├── features/order/
│   ├── create_order/                    # CRUD operation: all files generated
│   │   ├── endpoint_gen.py
│   │   ├── handler_gen.py
│   │   └── schemas_gen.py
│   └── cancel_order/                    # custom operation
│       ├── endpoint_gen.py
│       ├── handler.py                   # create once: your logic
│       └── schemas_gen.py
└── shared/
    ├── auth/cognito_gen.py              # examines the access token
    ├── config_gen.py                    # reads the environment variables
    ├── errors_gen.py                    # API errors as problem details
    └── db/models/order_gen.py           # the table of the entity Order
migrations/versions/0001_create_order_gen.py
tests/test_orders_http_gen.py
.dsml/schema-snapshot.json
openapi.gen.json
pyproject.toml
Dockerfile
```

| Model element | Files |
| --- | --- |
| `#Entity` | One SQLAlchemy model and one database table: `app/shared/db/models/order_gen.py`. A migration adds the table: `migrations/versions/0001_create_order_gen.py`. |
| `#Exposed` entity with `crud` | One slice for each CRUD operation, for example `app/features/order/create_order/`. Each slice has an endpoint, the Pydantic schemas and a generated handler. |
| `#Operation` (custom operation) | One slice with an endpoint and the schemas, for example `app/features/order/cancel_order/`. The slice also has the create-once file `handler.py`. |
| `#Roles` and `allowedRoles` | A role check in each endpoint. The endpoint returns HTTP 401 with no valid token, and HTTP 403 if the user has no permitted role. |
| `@FieldRules` | Pydantic field constraints. A request that breaks a rule gets HTTP 422. |
| `#Application` | The project files: `pyproject.toml`, `Dockerfile`, `app/main_gen.py`, `app/shared/` and the OpenAPI document `openapi.gen.json`. |
| Each operation | Generated HTTP tests, for example `tests/test_orders_http_gen.py` and `tests/test_cancel_order_http_gen.py`. |

The generator keeps the database schema of the last run in `.dsml/schema-snapshot.json`. When an entity changes, the generator compares the model with the snapshot. Then it writes one new migration file, and updates the snapshot. It never changes a migration that it wrote before. A migration that deletes or renames a table or a column needs the `#Destructive` metadata in the model.

### The custom operation stub

For a custom operation, the generator writes `handler.py` one time. This part comes from the golden file `app/features/order/cancel_order/handler.py`:

```python
# trace: OrderService::CancelOrder
async def handle(data: CancelOrderInput, session: AsyncSession, user: User) -> CancelOrderOutput:
    """Do the operation CancelOrder. Replace this body with the logic."""
    raise NotImplementedError("Write the logic of the operation cancel_order.")
```

The generated endpoint `endpoint_gen.py` validates the input, checks the roles and opens a database session. Then it calls `handle`. Until you write the logic, the endpoint returns HTTP 501.

## React application

The React target writes a static web client in TypeScript. It uses the Feature-Sliced Design (FSD) layout: the code is in the layers `app`, `pages`, `widgets`, `features`, `entities` and `shared` in `src/`. A slice is one folder in a layer. These paths are relative to the output folder `apps/order-portal`:

```text
src/
├── app/router/routes.gen.tsx            # the routes of the views
├── app/layout/navigation.gen.tsx        # the navigation items of the roles
├── pages/order-list/
│   ├── index.ts                         # create once: the public API of the slice
│   ├── index.gen.ts
│   └── ui/order-list-page.gen.tsx
├── widgets/order-list/ui/order-table.gen.tsx
├── features/cancel-order/
│   ├── api/cancel-order.gen.ts          # the API call
│   └── ui/cancel-order-form.gen.tsx     # the form
├── entities/order/
│   ├── api/order-queries.gen.ts
│   └── model/order.gen.ts               # the types and the Zod schemas
└── shared/
    ├── api/client.gen.ts
    ├── auth/amplify.gen.ts
    └── ui/button.tsx                    # create once: a UI component
```

| Model element | Files |
| --- | --- |
| `#Entity` | The slice `entities/<entity>`: the types and the data checks in `model/order.gen.ts`, and the read and list queries in `api/order-queries.gen.ts`. |
| Operation with input (`create`, `update` or custom) | The slice `features/<operation>`: the API call and a form, for example `api/create-order.gen.ts` and `ui/create-order-form.gen.tsx`. |
| List view and detail view | The slices `widgets/<entity>-list` and `widgets/<entity>-details`, for example `ui/order-table.gen.tsx`. |
| View | The slice `pages/<view>`, for example `ui/order-list-page.gen.tsx`. |
| `#Roles` | The navigation items and the views that each role can see. The server still examines each request. |

The generator writes a create-once `index.ts` in each slice. It re-exports the generated `index.gen.ts`. Add the exports of your own modules to `index.ts`. The UI components in `src/shared/ui/` are also create-once files, so you can change their style.

## Next.js application

The Next.js target writes a full-stack web application in TypeScript. The Next.js folder `app/` holds only route files. Each route file re-exports code from `src/`. The FSD layers are in `src/`, and the layers `app` and `pages` have the names `_app` and `_pages`. These paths are relative to the output folder `apps/order-web`:

```text
app/
├── orders/page.tsx                      # re-exports src/_pages/order-list
└── api/orders/[id]/cancel/route.ts      # re-exports src/_app/api-routes
src/
├── _app/api-routes/cancel-order.gen.ts  # the route handler of the operation
├── _pages/order-list/ui/order-list-page.server.gen.tsx
├── features/cancel-order/
│   ├── index.ts                         # create once
│   ├── index.server.ts                  # create once
│   └── api/cancel-order.server.ts       # create once: your logic
├── entities/order/model/order.gen.ts
└── shared/db/schema.gen.ts              # the tables for Drizzle
migrations/0001_create_order.gen.sql
openapi.gen.json
```

Each operation is one route handler under `/api`, with the same REST contract as the FastAPI target. For a CRUD operation, the server function is generated, for example `src/features/create-order/api/create-order.server.gen.ts`. For a custom operation, the generator writes the create-once file `src/features/cancel-order/api/cancel-order.server.ts`. Until you write the logic, the route handler returns HTTP 501.

## Infrastructure

The infrastructure generator writes HCL for OpenTofu and Terraform. HCL is the language of the two tools. The same files operate with the two tools. These paths are relative to the folder of the configuration file:

```text
infra/
├── modules/                             # one local module for each logical kind
│   ├── network/main.gen.tf
│   ├── container-service/main.gen.tf
│   ├── relational-database/main.gen.tf
│   └── user-directory/main.gen.tf
├── envs/                                # one root module for each environment
│   ├── dev/main.gen.tf
│   ├── staging/main.gen.tf
│   └── prod/main.gen.tf
├── tooling/main.gen.tf                  # the ECR repositories of the images
└── bootstrap/                           # one root module for each AWS account
    ├── tooling/README.gen.md
    ├── dev/README.gen.md
    ├── staging/README.gen.md
    └── prod/README.gen.md
```

A root module is a folder where you run `tofu plan` and `tofu apply`. A local module is a set of resources that a root module calls.

| Model element | Files |
| --- | --- |
| `#Network` with `#AwsVpc` | The module `infra/modules/network/`, and a call to it in each environment. |
| `#ContainerService` with `#AwsEcsService` | The module `infra/modules/container-service/`: the ECS service, the load balancer, the auto scaling and the log group. |
| `#RelationalDatabase` with `#AwsRdsPostgres` | The module `infra/modules/relational-database/`. |
| `#UserDirectory` with `#AwsCognito` | The module `infra/modules/user-directory/`: the Cognito user pool, one app client for each application and one group for each role. |
| `#SecretStore` with `#AwsSecrets` | The module `infra/modules/secret-store/`: one secret and one KMS key for each secret. The golden files of the order web have it. |
| `#Environment` | The root module `infra/envs/<environment>/` and the bootstrap root module `infra/bootstrap/<environment>/`. |
| `#Override` | Different values in the root module of one environment, for example `multi_az = true` in prod. |
| `#ToolingAccount` | The root modules `infra/tooling/` and `infra/bootstrap/tooling/`. |

The root module of each environment calls the same modules. This part comes from the golden file `infra/envs/dev/main.gen.tf` of the order service:

```hcl
module "order_db" {
  source = "../../modules/relational-database"

  database_name       = "order_db"
  deletion_protection = false
  element             = "OrderService::orderDb"
  instance_class      = "db.t4g.micro"
  master_username     = "dsml_admin"
  multi_az            = false
  name                = "order-service-dev-order-db"
```

The value `element` becomes the AWS tag `dsml:element` on each resource. Thus you can find the model element of each AWS resource.

Before the first deployment, apply the bootstrap root module of each account. The file `README.gen.md` in each bootstrap folder gives the steps. You can add hand-written `.tf` files to a root module. The generator does not change them.

## Pipelines

The pipeline generator writes three GitHub Actions workflows in `.github/workflows/`:

| File | When it runs | What it does |
| --- | --- | --- |
| `.github/workflows/pr.gen.yml` | On each pull request | Validates the model and uploads the findings. Runs `dsml generate --check`. Builds and tests each application. Runs `dsml check-output`. Runs `tofu plan` for dev. |
| `.github/workflows/main.gen.yml` | On each push to the main branch | Builds each container image one time, and deploys it to dev. |
| `.github/workflows/promote.gen.yml` | On a release tag `v*` | Deploys the same build to staging, then to prod after a person approves it. |

The generator also writes `.github/workflows/README.gen.md`. It gives the settings that an administrator must make in the GitHub repository, for example the environments and the reviewers of prod. Hand-written workflows can stay in the same folder, because their names do not end with `.gen.yml`.

## Where you write your code

Write your code only in create-once files and hand-written files. Do not change a generated file or a fixed-name file.

| Your code | Where to write it |
| --- | --- |
| The logic of a custom operation in FastAPI | The create-once file `handler.py` of the slice, for example `app/features/order/cancel_order/handler.py`. |
| The logic of a custom operation in Next.js | The create-once file `<operation>.server.ts`, for example `src/features/cancel-order/api/cancel-order.server.ts`. |
| More modules in a React or Next.js slice | A new file in the slice. Export it from the create-once `index.ts`. |
| Your own tests | A hand-written file in a test folder. Do not end its name with `_gen.py` or `.gen.<ext>`. Give the folder in the key `trace.tests`. |
| More AWS resources | A hand-written `.tf` file in a root module. Do not end its name with `.gen.tf`. |
| More workflows | A hand-written workflow file in `.github/workflows/`. Do not end its name with `.gen.yml`. |
| More dependencies of an application | The key `applications.<name>.dependencies` of the configuration file. The generator adds them to `pyproject.toml` or `package.json`. |

### What occurs at the next `dsml generate`

1. The generator validates the model. If there is an error finding, it stops and writes no file.
2. It compares each generated file on the disk with its hash in the manifest. If a person changed a generated file, it stops and writes no file.
3. It writes each generated file again. A file with the same content does not change, so Git shows no difference.
4. It deletes each generated file that the model no longer needs, for example the slice of a deleted operation.
5. It writes each new create-once file. It does not change a create-once file that exists.
6. It does not read, change or delete a hand-written file.

If an operation changes in the model, the generator changes the schemas, but not your `handler.py`. Then the type check shows each place where `handler.py` does not agree with the new schemas. Correct these places by hand. If you delete a custom operation from the model, the generator deletes its generated files, but keeps `handler.py`. Delete the old file yourself.

Run `dsml generate --check` before you commit. It writes no file, and lists each file that a normal run adds, changes or deletes. The pipeline `pr.gen.yml` runs the same check, and fails if the committed files are not current.

## The templates

The generators write the code from templates. The templates use Jinja, a template engine for Python. They are part of the toolchain package, in `src/dsml/templates/`. Each version of the toolchain has its own templates.

You do not edit a template, and you do not need to know Jinja. To change the generated code, change one of these items:

- **The model.** For example, add an attribute to an entity, or add a role to an operation.
- **The configuration file.** For example, change an output folder, or add a dependency.
- **The toolchain version.** A new version can have new templates. The release notes tell about the changes in the output.

The output is deterministic. The same model, configuration and toolchain version always give the same bytes. Thus each difference in the generated code comes from one of the three items above.

## Check the generated code

`dsml check-output` runs the language tools of each target on the generated code. Install the tools before you run the command. If a tool is missing, the command reports an error with the name of the tool.

| Target | Tools | What each tool examines |
| --- | --- | --- |
| FastAPI | `ruff check`, `ruff format --check` | Ruff finds errors and style problems in the Python code, and examines the format. |
| FastAPI | `pyright` | Pyright examines the Python types. It finds a `handler.py` that does not agree with the schemas. Run `uv sync` in the folder of the application first. |
| React and Next.js | `tsc --noEmit` | The TypeScript compiler examines the types. It writes no file. |
| React and Next.js | `eslint .` | ESLint finds errors and style problems in the TypeScript code. |
| React and Next.js | `steiger ./src` | Steiger examines the FSD rules: a module imports only from lower layers, and only through the public API of a slice. Run `pnpm install` in the folder of the application first. |
| Infrastructure | `tofu fmt -check` | OpenTofu examines the format of the HCL. |
| Infrastructure | `tofu init -backend=false`, `tofu validate` | OpenTofu examines each root module: the syntax, the references and the attribute names of the resources. |
| Infrastructure | `tflint` | TFLint examines each root module with the AWS rule set, for example for an instance type that does not exist. |

`dsml check-output --application orderApi` checks one application. `dsml check-output --infrastructure` checks only the infrastructure. With no option, the command checks each application and the infrastructure.

The report has one line for each tool. The status is `pass`, `error` or `not run`. The output of a tool that did not pass follows its line. The exit code is 0 if each tool passed, and 1 if a tool found an error or is missing.

## Next steps

- Read the [reports](reports.md) page to understand the findings and the trace reports.
- Read about the [configuration file](../configuration.md).
- Read the [AI assistance](ai-assistance.md) page to let an AI agent help you write the model.
