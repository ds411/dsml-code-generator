# Pinned copy of shadcn/ui

This folder is the pinned copy of the shadcn/ui components that the React templates use (Q41, PRD-CORE-048). The React generator writes the files of `ui/` into `src/shared/ui/` and the files of `lib/` into `src/shared/lib/` of each `react` application. These are create-once files, thus a developer owns them (PRD-APP-212).

## Source

- Repository: `shadcn-ui/ui`, release tag `shadcn@4.21.4`.
- Commit: `3464245c4513b7998b1d11fa9c67b71cc1534dc7`.
- Folder: `apps/v4/registry/new-york-v4/`. The style in `components.json` is `new-york`.
- License: MIT. `LICENSE.md` is the license of the repository.

The items `shadcn-ui` and `shadcn-ui-commit` of `src/dsml/versions.toml` give the same release and commit. A test makes sure that they agree.

## Files

| File | Source file |
| --- | --- |
| `lib/utils.ts` | `lib/utils.ts` (the function `cn`) |
| `ui/alert.tsx` | `ui/alert.tsx` |
| `ui/alert-dialog.tsx` | `ui/alert-dialog.tsx` |
| `ui/button.tsx` | `ui/button.tsx` |
| `ui/card.tsx` | `ui/card.tsx` |
| `ui/field.tsx` | `ui/field.tsx` |
| `ui/input.tsx` | `ui/input.tsx` |
| `ui/label.tsx` | `ui/label.tsx` |
| `ui/native-select.tsx` | `ui/native-select.tsx` |
| `ui/separator.tsx` | `ui/separator.tsx` |
| `ui/table.tsx` | `ui/table.tsx` |
| `ui/textarea.tsx` | `ui/textarea.tsx` |

These components use only the dependencies of the version baseline: `@radix-ui/react-alert-dialog`, `@radix-ui/react-label`, `@radix-ui/react-separator`, `@radix-ui/react-slot`, `class-variance-authority`, `clsx`, `lucide-react` and `tailwind-merge`.

Story #172 added `alert-dialog`, `field`, `label`, `native-select` and `separator` for the forms and the confirmation dialog of the features layer.

## Changes to the source files

The shadcn CLI makes the first three changes when it copies a component into a project. The copy has the result, thus the generator does not run the CLI.

1. The import of `cn` is from `@/shared/lib/utils`, the alias `utils` of `components.json`.
2. The directive `"use client"` is removed, because `components.json` has `"rsc": false`.
3. The files have the Prettier format of the generated project.
4. `ui/button.tsx` imports `Slot` from `@radix-ui/react-slot`, not `Slot.Root` from `radix-ui`. The version baseline pins `@radix-ui/react-slot` (story #190).
5. `ui/alert-dialog.tsx`, `ui/label.tsx` and `ui/separator.tsx` import the primitive from its own Radix UI package, for example `import * as LabelPrimitive from "@radix-ui/react-label"`, not from `radix-ui`.
6. A component imports an other component of the copy with a relative path, for example `./button`. The shadcn CLI writes `@/shared/ui/button`. The test of the copy accepts no other import with the alias `@/` than `@/shared/lib/utils`.
7. `ui/field.tsx` compares `uniqueErrors.length === 1`, not `uniqueErrors?.length == 1`. The rule `no-unnecessary-condition` of `typescript-eslint` refuses the optional chain on a value that is not nullable.

## Update the copy

A generator release can update the copy. Do these steps:

1. Change the items `shadcn-ui` and `shadcn-ui-commit` in `src/dsml/versions.toml`.
2. Copy the files from the new commit and make the changes of the section above.
3. Change the release and the commit in this file.
4. Write the golden files again with `uv run python scripts/write_golden_react.py`.

To add a component, add its file to `ui/` and a row to the table above. If the component needs a package that is not in the version baseline, add the package to the baseline and to `RUNTIME_PACKAGES` of `src/dsml/generate/react.py`.
