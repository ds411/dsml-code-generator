# Decision record 08: release assets

Status date: 12 October 2026

## Purpose and status

This record holds 1 question, Q63, about the place where a release publishes the toolchain package. Q63 changes PRD-CORE-047. PRD-CORE-047 gives Q63 in the Source column.

Status: closed. On 12 October 2026, the product owner selected option (b) of decision issue #133 in the project thread of milestone M7 (#9).

## Y. Release assets

PRD-CORE-047 told that the release process publishes the toolchain package to "the internal package index". No PRD and no decision record named this index. GitHub Packages has no Python registry. The product owner has no AWS account at this time (Q58), so AWS CodeArtifact is not available. The repository `ds411/dsml-code-generator` is public.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q63 | Where does a release publish the toolchain package? Options: (a) a PEP 503 simple index on GitHub Pages; (b) the assets of the GitHub release only, with no package index; (c) AWS CodeArtifact; (d) public PyPI. | (b). The release workflow attaches the wheel and the sdist to the GitHub release of the tag `v<version>`. A user installs the wheel from its release URL, for example `uv tool install https://github.com/ds411/dsml-code-generator/releases/download/v<version>/dsml-<version>-py3-none-any.whl`. The dependencies come from PyPI. There is no package index, so the repository variable `DSML_INDEX_URL` of the generated workflows goes away. Changed requirement: PRD-CORE-047. | Decided |

## Effects on M7

- #137: the GitHub Action installs the toolchain from the wheel URL of the release. It has no input for an index URL.
- #140: the generated workflows install the toolchain through the action, with no index URL. The generated README does not give `DSML_INDEX_URL`.
- #141: the release workflow attaches the wheel and the sdist to the GitHub release.
