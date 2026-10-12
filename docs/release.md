# Release of the toolchain

This document gives the steps of a release of the DSML toolchain, from the tag to the installation with `uv tool install`. The release workflow `.github/workflows/release.yml` builds the package and makes the GitHub release.

- The toolchain uses semantic versioning: `<major>.<minor>.<patch>` (PRD-CORE-052, Q16).
- The release attaches the wheel and the sdist to the GitHub release of the tag `v<version>`. There is no package index (PRD-CORE-047, Q63).
- The dependencies of the toolchain come from PyPI.

## Before the release

The product owner must do these steps in a pull request. The pull request must merge into `main` before the tag.

1. Select the new version. Increase the major version for a change that is not compatible. Increase the minor version for a new function. Increase the patch version for a correction only.
2. Set the version in `pyproject.toml`:

   ```sh
   uv version <version>
   ```

3. Add the section `## <version>` at the top of the sections in `CHANGELOG.md`. Write no other text in the heading.
4. In the section, name each change to the generated output (PRD-CORE-052). Use the subsection `### Changes to the generated output`.
5. Run the package tests:

   ```sh
   uv run pytest tests/test_package.py
   ```

## Push the tag

1. Get the newest `main`:

   ```sh
   git switch main
   git pull origin main
   ```

2. Make sure that the CI of the newest commit on `main` passed.
3. Make the tag and push it. The tag must be `v` and the version in `pyproject.toml`:

   ```sh
   git tag v<version>
   git push origin v<version>
   ```

## The release workflow

The push of the tag starts the release workflow. The job does these steps:

1. It makes sure that the tag is `v<version>`, with the version in `pyproject.toml`. If not, the job stops with an error.
2. It makes sure that `main` contains the commit of the tag. If not, the job stops with an error.
3. It writes the release notes from the section `## <version>` of `CHANGELOG.md`. If the section is missing or empty, the job stops with an error.
4. It builds the wheel and the sdist with `uv build`.
5. It runs `tests/test_package.py` on the built files. The tests make sure that the package contains the DSML library, the IR schema and the templates (PRD-CORE-048, PRD-DSML-006). They also install the wheel with `uv tool install`, get `sysml-grpc` with its hash check, and validate the example model.
6. It makes the GitHub release `v<version>` with the release notes. It attaches the wheel and the sdist as assets.

If a step fails, the workflow makes no release. Correct the cause in a pull request. Then remove the tag and push it again on the new commit of `main`:

```sh
git push origin --delete v<version>
git tag --force v<version> <commit>
git push origin v<version>
```

## Install the release

1. Install uv.
2. Install the toolchain from the wheel of the release:

   ```sh
   uv tool install --python 3.14 https://github.com/ds411/dsml-code-generator/releases/download/v<version>/dsml-<version>-py3-none-any.whl
   ```

3. Get the `sysml-grpc` binary of OpenSysML and check its SHA-256 hash (PRD-CORE-049). After this step, the toolchain does not use the network:

   ```sh
   "$(uv tool dir)/dsml/bin/python" -m dsml.adapter.binary
   ```

4. Make sure that the installation is correct:

   ```sh
   dsml version
   ```

The GitHub Action of the toolchain does steps 2 and 3 for the generated workflows. `docs/action.md` gives the action.
