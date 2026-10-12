# React generator: project files and generator frame

Story #167 added the first part of the React generator (phase 2). The generator writes a project that `tsc`, ESLint, Steiger, Vitest and `pnpm build` accept. The page renders an empty root. The next stories of M10 (#155) write the code of the FSD layers.

- Generator: `src/dsml/generate/react.py`. It is in the list `GENERATORS` of `src/dsml/generate/generators.py`.
- Common parts of the layer modules: `src/dsml/generate/react_common.py`.
- Layer modules: `react_shared.py`, `react_entities.py`, `react_features.py`, `react_widgets.py`, `react_pages.py` and `react_app.py` in `src/dsml/generate/`.
- Templates: `src/dsml/templates/react/project/`.
- Tests: `tests/test_react_generator.py`.
- Golden files: `tests/golden/react/order-portal/`. Write them again with `uv run python scripts/write_golden_react.py`.
- CI: the job "React golden project" in `.github/workflows/ci.yml`.

## Inputs

The generator reads only the IR and the configuration (PRD-APP-001, PRD-CORE-026). It writes files for each application with `target = Target::react`.

- The key `applications.<name>.output` gives the output folder of the application (PRD-APP-002). If the key is missing, `dsml generate` stops with an error.
- The key `applications.<name>.dependencies` gives extra run-time dependencies in the form `<package>@<version>`, for example `date-fns@4.1.0` or `@scope/package@1.2.3`. The generator adds them to `dependencies` in `package.json`, in sorted order (PRD-CORE-046). An extra dependency must not be a package of the target. The version baseline gives the version of these packages (PRD-TOP-008).
- The versions come from `src/dsml/versions.toml` (PRD-APP-201). `docs/notes/typescript-baseline.md` gives the items.

## Output

All files are generated files. The generator writes them again at each run. It does not write `pnpm-lock.yaml` (PRD-CORE-036).

| File | Content | Requirements |
| --- | --- | --- |
| `package.json` | The pinned run-time and dev dependencies, the scripts, `packageManager` (pnpm) and `devEngines` (Node.js). | PRD-APP-201, PRD-CORE-046, PRD-TOP-008 |
| `tsconfig.json` | Strict TypeScript. The path alias `@/*` to `./src/*`. | PRD-APP-201, PRD-APP-205 |
| `vite.config.ts` | The React and Tailwind CSS plugins. The alias `@/` to `/src/`. The output folder `dist/`. The Vitest settings. | PRD-APP-205, PRD-APP-233, Q64 |
| `index.html` | The page. It loads `src/main.gen.tsx`. | PRD-APP-233 |
| `components.json` | The settings of shadcn/ui: the components are in `@/shared/ui`. | PRD-APP-201, Q41 |
| `steiger.config.ts` | The recommended rules of the FSD plugin of Steiger. | PRD-APP-234 |
| `eslint.config.js` | The type-aware rules of `typescript-eslint` (`strictTypeChecked`). | PRD-APP-201, Q64 |
| `src/main.gen.tsx` | The entry module. It renders an empty root. | PRD-APP-202 |

The seven fixed-name files are the list of PRD-APP-235. Each other generated file has a name that ends with `.gen.ts` or `.gen.tsx` (PRD-CORE-039).

## Header

Each generated `.ts`, `.tsx` and `.js` file starts with the trace header in `//` comments (PRD-APP-017, PRD-TRACE-005). The elements of the header of a project file are the application. JSON has no comments, thus `package.json`, `tsconfig.json` and `components.json` have no header. The header has only line comments, thus `index.html` also has no header.

## FSD layers

The generator calls the function of each layer module, from the lowest to the highest layer: `shared_files`, `entities_files`, `features_files`, `widgets_files`, `pages_files` and `app_files`. Each function gets a `ReactContext` and gives the files of its layer in `src/<layer>/` (PRD-APP-202). In story #167, each function gives no file.

`react_common.py` gives the rules that all layers use:

- `slice_name` and `file_name` give the kebab case of a model element name, for example `order-list` and `order-list-page` (PRD-APP-206).
- `slice_folder` gives the folder of a slice, for example `src/pages/order-list`. The layers `app` and `shared` have no slices.
- `public_api_files` gives the public API of a slice: a generated `index.gen.ts` that re-exports the modules of the slice, and a create-once `index.ts` that re-exports `index.gen.ts` (PRD-APP-204, PRD-CORE-044). A create-once file has no header, because a developer owns it.
- `ReactContext.generated_file` renders a template into a generated file with the header.

## Golden files and tests

The golden folder is the project folder of the application `orderPortal` of the order portal model. It has no manifests in `.dsml/`. The phase 2 exit story (#177) adds them.

The test of the project files compares only the files outside the layer folders `src/<layer>/`. The test of each layer story compares the folder of its layer. Thus the stories of one step change different golden files.

The CI job "React golden project" does these steps:

1. It runs Prettier in check mode on `tests/golden/react/` (PRD-CORE-035).
2. It copies the golden project to a temporary folder and runs `pnpm install`. The install makes `pnpm-lock.yaml` in the copy.
3. It runs `tsc --noEmit`, ESLint, Steiger and Vitest.
4. It runs `pnpm build` and makes sure that `dist/index.html` exists (PRD-APP-233).

## Differences from the story text

- The story gives `src/main.tsx` as a generated file. PRD-CORE-039 and PRD-APP-235 permit only names that end with `.gen.<ext>` and the fixed-name list. `main.tsx` is not on that list. Thus the entry module is `src/main.gen.tsx`.

## Items for the next stories

- `components.json` gives `src/app/styles/index.css` as the Tailwind CSS file. The story that writes the app layer must write this file and import it in the entry module.
- The shared layer story (#169) reads `/config.json`. The keys are `apiBaseUrl`, `region`, `userPoolId`, `appClientId` and `loginDomain` (story #165).
- With pnpm 12, `pnpm install` can write `pnpm-workspace.yaml` in the project (the setting `minimumReleaseAgeExclude`). `pnpm-lock.yaml` and this file do not have the Prettier format. Thus `prettier --check .` in the generated pipeline finds them. The project has no `.prettierignore`, because the file is not on the fixed-name list of PRD-APP-235.
