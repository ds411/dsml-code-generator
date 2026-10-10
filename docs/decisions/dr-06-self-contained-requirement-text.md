# Decision record 06: self-contained requirement text

Status date: 10 October 2026

## Purpose and status

This record holds 1 question, Q61, that came up in story #15 (the PRD model). Q61 changes the text of 9 requirements. Each of these requirements gives Q61 in the Source column.

Status: closed. On 10 October 2026, the product owner asked for this change in the project thread of story #15.

## W. Requirement text

Story #15 added a test that compares the `doc` text of each requirement in the PRD model with `docs/index/requirements.csv`. The PRD text is correct, so the model got the PRD text. But 9 requirement texts referred to "the table above", "the tree above" or "the catalog below". In the PRD model and in the CSV index, these words do not identify a table.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q61 | How does a requirement refer to a table, a tree or a catalog in its PRD? Options: (a) with the name of the PRD section that contains it, for example "the table of the section "Reports""; (b) with the words "above" or "below", as before. | (a). The text then has the same meaning in the PRD, in the CSV index and in the PRD model. Where the list is short, the text also gives its items. Changed requirements: PRD-APP-110, PRD-APP-121, PRD-APP-210, PRD-CICD-001, PRD-CORE-001, PRD-DSML-035, PRD-IAC-001, PRD-TRACE-013 and PRD-VAL-015. The meaning of each requirement does not change. | Decided |
