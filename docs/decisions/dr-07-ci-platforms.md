# Decision record 07: CI platforms

Status date: 11 October 2026

## Purpose and status

This record holds 1 question, Q62, about the operating systems of the toolchain CI. Q62 changes PRD-CORE-029 and the phase 1 exit criterion. PRD-CORE-029 gives Q62 in the Source column.

Status: closed. On 11 October 2026, the product owner asked for this change in the project thread of story #109.

## X. CI platforms

Q50 gives the operating systems of the toolchain: Linux x64, Linux arm64 and macOS arm64. Before this decision, CI ran each check on these three operating systems. The GitHub Actions minutes of the account are limited. The arm64 and macOS runners use more minutes than the Linux x64 runner.

| ID | Question and options | Selected answer | Status |
| --- | --- | --- | --- |
| Q62 | On which operating systems does the toolchain CI run? Options: (a) Linux x64, Linux arm64 and macOS arm64, as Q50 gives; (b) only Linux x64. | (b). The toolchain still supports the operating systems of Q50, but CI does not test Linux arm64 and macOS arm64. Changed requirement: PRD-CORE-029. Changed phase 1 exit criterion: the determinism check passes in CI on Linux x64. | Decided |
