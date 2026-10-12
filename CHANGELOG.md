# Changelog

This file gives the changes of each release of the DSML toolchain. The toolchain uses semantic versioning (PRD-CORE-052, Q16). Each section names the changes to the generated output. A change to the generated output is one of these:

- A new generated file, or a generated file that the toolchain does not write any more.
- A change to the text of a generated file for the same model and configuration.

The release workflow `.github/workflows/release.yml` copies the section of the release into the notes of the GitHub release. The heading of each section must be `## <version>`, with no other text. `docs/release.md` gives the steps of a release.

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
