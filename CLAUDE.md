# Rule for all sessions: ASD-STE100

Write all text in ASD-STE100 Simplified Technical English, Issue 9. This rule applies to chat replies, plans, commit messages, pull request text, code comments, user messages and documentation.

- Use only approved STE words, with their approved meanings. You can also use the project dictionary in `docs/prd/00-top-level-prd.md`, product names and names in `code` font.
- Write sentences of 20 words or fewer in a procedure, and 25 words or fewer in a description.
- Write one instruction in each sentence. Use the imperative form for an instruction.
- Use the active voice and simple verb tenses. Do not use the "-ing" form of a verb, except in a technical name.
- Use "must" for an obligation. Do not use "shall", "should" or "may".
- Write six sentences or fewer in a paragraph. Use a vertical list for a sequence of steps.

# DSML toolchain

This repository builds the DSML toolchain, an internal product. The toolchain has five parts:

1. A domain-specific modeling language (DSML) on SysML v2 for needs, requirements, application, infrastructure and verification.
2. Deterministic code generation for FastAPI (phase 1), React (phase 2) and Next.js (phase 3).
3. Deterministic code generation for OpenTofu and Terraform, and for GitHub Actions pipelines.
4. Validation of the model.
5. Traceability from stakeholder needs to code, tests and AWS resources.

## Source of truth

- Requirements: `docs/prd/`. Start with `docs/prd/00-top-level-prd.md`.
- Decisions and their reasons: `docs/decisions/` (records 01 to 04, all closed).
- If a PRD and a decision record do not agree, the PRD is correct. Tell the user about the difference.
- Machine-readable lists: `docs/index/requirements.csv` and `docs/index/decisions.csv`.
- The PRD requirements as a DSML model: `docs/model/prd/*.sysml`. Example model: `docs/model/examples/order-service.sysml`.

Do not load all documents at the start. Read the PRD for the part that you work on:

| Work on | Read |
| --- | --- |
| DSML library, model layers | `docs/prd/01-dsml-prd.md`, `docs/model/` |
| CLI, configuration, OpenSysML adapter, IR, determinism, generated files | `docs/prd/02-toolchain-core-prd.md` |
| Application generators | `docs/prd/03-application-generation/00-common-rules.md`, then the file of the target |
| OpenTofu and Terraform generator | `docs/prd/04-infrastructure-generation-prd.md` |
| GitHub Actions generator | `docs/prd/05-cicd-generation-prd.md` |
| Validator and rule catalog | `docs/prd/06-validation-prd.md` |
| Trace manifest, trace comments, reports | `docs/prd/07-traceability-prd.md` |
| Versions of tools and libraries | `docs/decisions/dr-03-versions-and-prd-details.md` |

## Phase 1 scope

Phase 1 contains: the DSML library with all five layers; OpenSysML integration, IR, CLI and GitHub Action; validation; traceability; the FastAPI generator; the infrastructure generator (network, container service, database, user directory, secrets); and the GitHub Actions generator. React, Next.js and the static site are not in phase 1.

The product owner has no AWS account at this time. The tests that deploy to AWS wait for an AWS account (Q58). Do not try to deploy to AWS.

## Rules for all toolchain code

- Python 3.14. uv manages the project (PRD-TOP-001, Q49).
- OpenSysML 0.9.2 is the SysML v2 engine. Only the IR adapter module imports `opensysml` (PRD-CORE-020).
- Validators and generators read only the IR (PRD-CORE-026). The IR adapter evaluates formal constraints and writes the results into the IR (PRD-CORE-054, Q57).
- Validation, generation and trace reports do not use the network or an AI model (PRD-TOP-004, PRD-TOP-005).
- Output is byte-identical for the same model, configuration and toolchain version: sorted lists, no timestamps, no random values, no absolute paths, UTF-8, LF line ends (PRD-CORE-028 to PRD-CORE-038).
- Generated file names end with `.gen.<ext>` or `_gen.py`, or are on the fixed-name list of the target (PRD-CORE-039). The generator never changes a hand-written file (PRD-CORE-042).
- Each generator has golden-file tests (PRD-CORE-030). Each validation rule has one model that it accepts and one model that it rejects (PRD-VAL-008).
- User messages and documentation use ASD-STE100 Simplified Technical English, Issue 9. "Must" marks an obligation (PRD-TOP-009, PRD-CORE-008).

## Trace your work to the PRDs

Put a trace comment above each module, class or function that implements a PRD requirement:

```python
# trace: PRD-CORE-028, PRD-CORE-033
```

This uses the trace comment form of PRD-TRACE-009, so the toolchain can later trace its own code.

## Work process

`CONTRIBUTING.md` gives the full work process. Obey these rules:

- The GitHub issue tracker holds all open items. Each branch and each pull request is for one story issue.
- Do each story on a new branch from the newest `main`. Use the name `story/<issue>-<short-name>`, or the branch name that the session gives.
- Merge work into `main` only through a pull request. Do not merge it: the product owner does a squash merge.
- Fill in `.github/pull_request_template.md`. Then add a comment with the recommended squash commit message (`.github/squash_commit_comment_template.md`). Edit the comment after each push that changes the scope.
- Use the issue templates in `.github/ISSUE_TEMPLATE/` and the commit template `.gitmessage`.
- To change a PRD requirement, obey "Changes to a PRD requirement" in `CONTRIBUTING.md`.

## First task

The DSML library does not exist yet. Nobody has parsed the example model or the PRD model with OpenSysML. Create the `DSML` library package, then make `docs/model/examples/order-service.sysml` and `docs/model/prd/*.sysml` parse and resolve with no error (PRD-DSML-004, PRD-TOP-011). The SysML syntax in the PRDs is a sketch. If OpenSysML does not accept it, change the sketch, not the requirement, and record each change.

## Requirement IDs

- PRD requirements: `PRD-<PART>-<NNN>`. Parts: TOP, DSML, CORE, APP, IAC, CICD, VAL, TRACE.
- Decisions: Q1 to Q58 and AD1 to AD3. The Source column of each requirement gives its decisions.
- Validation rules: `<CATEGORY>-<NNN>`, for example `COV-003`.
