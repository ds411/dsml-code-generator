# DSML toolchain: PRD bundle

Status date: 10 October 2026. All decisions (Q1 to Q58, AD1 to AD3) are closed. The text uses ASD-STE100 Simplified Technical English, Issue 9.

## Contents

```text
CLAUDE.md                                  Project brief for Claude Code
docs/
├── prd/
│   ├── 00-top-level-prd.md                Goals, users, architecture, phases, conventions, dictionary
│   ├── 01-dsml-prd.md                     PRD-DSML
│   ├── 02-toolchain-core-prd.md           PRD-CORE
│   ├── 03-application-generation/         PRD-APP, one file for each target
│   ├── 04-infrastructure-generation-prd.md  PRD-IAC
│   ├── 05-cicd-generation-prd.md          PRD-CICD
│   ├── 06-validation-prd.md               PRD-VAL
│   └── 07-traceability-prd.md             PRD-TRACE
├── decisions/                             Decision records 01 to 04
├── model/
│   ├── README.md
│   ├── prd/*.sysml                        All PRD requirements as a DSML model
│   └── examples/order-service.sysml       Example model with all five layers
└── index/
    ├── requirements.csv                   One row for each PRD requirement
    └── decisions.csv                      One row for each decision
```

## Use with Claude Code

1. Unzip the bundle into the root of the toolchain repository. `CLAUDE.md` goes to the root, and the documents go to `docs/`.
2. If the repository already has a `CLAUDE.md`, merge the two files. Keep the result short, because Claude Code loads `CLAUDE.md` into each session.
3. Start Claude Code in the repository. A good first prompt is: "Read CLAUDE.md and docs/prd/00-top-level-prd.md, then do the first task in CLAUDE.md."

## Live documents

The bundle is a copy. The live documents are on claude.ai:

- [Top-level PRD](https://claude.ai/code/artifact/1ca8c61d-af04-469c-b04c-755aa8d7c128)
- [DSML PRD](https://claude.ai/code/artifact/2f3caccc-85d1-45cc-a570-d4493d16b9fd)
- [Toolchain core PRD](https://claude.ai/code/artifact/4f8c2692-e430-46b5-ad01-4483ca117079)
- [Application generation PRD](https://claude.ai/code/artifact/38be587f-3959-4d4d-a39f-a1923313e1ec)
- [Infrastructure generation PRD](https://claude.ai/code/artifact/8c075844-7325-402b-badd-87cbbdd90faa)
- [CI/CD generation PRD](https://claude.ai/code/artifact/40a79a1f-2760-4796-8de9-85822cab2353)
- [Validation PRD](https://claude.ai/code/artifact/6095f07a-e81c-48ac-9d33-ed548690a4e6)
- [Traceability PRD](https://claude.ai/code/artifact/9d874245-dfbb-4712-8370-c56252131dd8)
- [Decision record 01](https://claude.ai/code/artifact/7699d83f-b0de-4dc9-a037-644454a8988d), [02](https://claude.ai/code/artifact/d36abca8-3e59-487c-9f81-bb2dcad0d633), [03](https://claude.ai/code/artifact/85af4b8d-0ba4-442b-94e9-a5d80200d255)

If you change a live document, export the bundle again.

## Open action

Nobody has parsed the `.sysml` files with OpenSysML yet. This is the first task of phase 1 (PRD-TOP-011, PRD-DSML-004).
