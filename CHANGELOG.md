# Changelog

This file gives the changes of each release of the DSML toolchain. The toolchain uses semantic versioning (PRD-CORE-052, Q16). Each section names the changes to the generated output. A change to the generated output is one of these:

- A new generated file, or a generated file that the toolchain does not write any more.
- A change to the text of a generated file for the same model and configuration.

The release workflow `.github/workflows/release.yml` copies the section of the release into the notes of the GitHub release. The heading of each section must be `## <version>`, with no other text. `docs/release.md` gives the steps of a release.

## 0.2.0

This release adds phase 2 (React), phase 3 (Next.js), the AI assistance and the user guide. The tests that deploy to AWS wait for an AWS account (Q58, #142).

### Changes to the generated output

These changes apply to a model of phase 1 with no change:

- The generated GitHub Actions workflows use the toolchain action `ds411/dsml-code-generator@v<version>` of this release: `@v0.2.0`, with the input `version: "0.2.0"`.
- The root module of each environment sets `APP_ENVIRONMENT` for each container service. This corrects a defect: without this variable, the generated FastAPI application stopped at start (#207).
- A FastAPI application that a `react` application calls sends CORS headers for the site domain of each application that calls it. The FastAPI target adds the CORS middleware and the variable `CORS_ALLOWED_ORIGINS`. The root module of each environment sets the variable (#204, PRD-APP-136, Q66).
- The manifests `.dsml/generated.json` and `.dsml/trace.gen.json` change with the files above.
- `dsml ir` writes the IR version 1.1.0 (#197).
- The SARIF output of `dsml validate` gives the toolchain version 0.2.0. Its rule list has the new rule STR-017 and a new help text for XLY-005 (#201).
- The starter model of `dsml init` gives the DSML library version 1.1. The comment of the starter `dsml.toml` refers to the skill `dsml-cli` (#195, #262).

These changes apply to a model that uses the new keywords of phase 2 and phase 3:

- The React generator writes the FSD code of each `react` application: the project files, the entities, the shared layer with the pinned copy of shadcn/ui, the features, the widgets, the pages, the routes and the navigation (#206, #208, #209, #212, #213, #214).
- The React generator writes the entity slices and the feature slices of an external API from an imported OpenAPI file (#215).
- The Next.js generator writes the full-stack code of each `nextjs` application: the project files and the `Dockerfile`, the Drizzle schema and the migrations, the authentication with `proxy.ts`, the entity, feature and widget slices, the route handlers and the server functions, the pages and the navigation, and `openapi.gen.json` (#220, #222, #241, #242, #244, #245, #246).
- The infrastructure generator writes the local module `static-site` for each `#StaticSite` element. Each root module with a static site has a second AWS provider for `us-east-1` (#200).
- The infrastructure generator and the GitHub Actions generator write a `nextjs` application as a container application (#221).
- The generated workflows check, build and deploy each React application. The deploy jobs upload the static files to S3, write `/config.json` and invalidate the CloudFront cache (#203).
- `dsml init --target react` and `dsml init --target nextjs` write a starter configuration file and a starter model (#211, #243).
- `dsml skills install` writes the skills `dsml-modeling` and `dsml-cli` (#251, #253, #254, Q68).

### Toolchain

- The DSML library 1.1.0 adds the keywords `#View`, `#StaticSite`, `#AwsStaticSite` and `#ExternalApi`, and the navigation of an application. A model of version 1.0 stays valid (#195, #201).
- The IR adapter reads a local OpenAPI 3.1 JSON file of an `#ExternalApi` element (#201, Q65).
- The validation rules examine the views, the static sites and the Next.js applications. The new rule STR-017 examines an imported OpenAPI file (#199, #201, #222).
- `dsml check-output` runs `tsc`, ESLint and Steiger on each `react` and `nextjs` application (#210, #243).
- `dsml mcp` starts the local MCP server with the stdio transport. The server needs the optional dependency group `mcp` (#251, #252, #255, #258, Q69, Q70).
- The version baseline pins the versions of the React and Next.js targets. TypeScript uses the line 6.0 (#194, #196, Q64).
- The reference models "order portal" (phase 2) and "order web" (phase 3) (#198, #218).
- The user guide in `docs/guide/`, with the concepts, a modeling tutorial, the generated code, the reports, the AI assistance and the DSML reference (#249, #256, #257, #259, #260, Q71).

## 0.1.0

The first release of the toolchain. It contains phase 1.

### Changes to the generated output

- The generated GitHub Actions workflows install and run the toolchain through the toolchain action `ds411/dsml-code-generator@v<version>`. The action installs the wheel from the GitHub release. The workflows and the generated README do not use the repository variable `DSML_INDEX_URL` any more (#140, Q63).
- The FastAPI generator writes the project files, the shared code, the Cognito token check and the role check, the SQLAlchemy models, the schemas, the CRUD slices, the custom operations with their handler stubs, the Alembic migrations and `openapi.gen.json`.
- The infrastructure generator writes the OpenTofu and Terraform root modules and the modules for the network, the container service, the database, the user directory and the secrets. It also writes the tooling root module and the bootstrap root modules.
- The GitHub Actions generator writes the pull request workflow `pr.gen.yml`, the main and promote workflows, and the README of the pipelines with the repository settings.
- `dsml generate` writes the manifest `.dsml/generated.json` and the trace manifest `.dsml/trace.gen.json`.

### Toolchain

- The DSML library with the five layers: needs, requirements, application, infrastructure and verification.
- The subcommands `init`, `validate`, `generate`, `trace`, `ir`, `check-output` and `version`.
- The validator with the rule catalog, the waivers and the SARIF 2.1.0 output.
- The trace reports `coverage`, `orphans`, `impact` and `suspect`, with the Git baseline.
- The check of the SHA-256 hash of `sysml-grpc` before each start (PRD-CORE-049).
- The GitHub Action of the toolchain, with the SARIF upload to code scanning (PRD-CORE-050, PRD-CORE-051).
- The release workflow, which attaches the wheel and the sdist to the GitHub release (PRD-CORE-047, Q63).
