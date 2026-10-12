# Check of the TypeScript tools with TypeScript 7.0

Story #190 examined if the tools of the TypeScript targets operate with TypeScript 7.0. Decision Q64 (decision record 09) uses the result to select the TypeScript line: 7.0 if all tools operate, 6.0 if one or more tools do not operate.

Result: three checks fail with TypeScript 7.0. All checks pass with TypeScript 6.0. Thus the TypeScript line of the React and Next.js targets is 6.0.

## Test project and script

- Folder: `scripts/typescript-check/`. It is a pnpm workspace with two small applications, `react-app` (the React target, PRD-APP-201) and `next-app` (the Next.js target, PRD-APP-301).
- `react-app` uses Vite, React, TanStack Router, Query and Form, Zod, Tailwind CSS, a copy of the shadcn/ui button (Q41) and Amplify JS. Its `src/` folder has the FSD layers `app`, `pages` and `shared`.
- `next-app` uses Next.js with `proxy.ts` (PRD-APP-323), the Amplify JS adapter for Next.js, Drizzle ORM with the driver `pg`, and Zod.
- The workspace root has the ESLint configuration with the type-aware rules of `typescript-eslint` (`strictTypeChecked`), and Prettier.
- Each application has a Steiger configuration with the recommended rules of `@feature-sliced/steiger-plugin`, and Vitest tests.

To run the check again, use this command from the repository root:

```sh
scripts/typescript-check/check.sh 7.0.2 6.0.3
```

The script copies the project into a temporary folder for each TypeScript version. It installs the project with a pnpm override of the TypeScript version, and runs the checks. It writes a Markdown table of the results and a log for each check. Set `RESULTS_DIR` to keep the logs in a known folder. The exit code is 1 if a check fails. To check a later TypeScript release, give its version as an argument. To check later releases of the other tools, change their versions in the `package.json` files.

The install uses the network. This is permitted, because the script is not validation, generation or a trace report (PRD-TOP-005). CI does not run the script.

## Tool versions

The script used the newest stable release of each tool on 12 October 2026. The runtime is Node.js 26.11.1 and the package manager is pnpm 12.11.2.

| Tool | Version |
| --- | --- |
| TypeScript 7.0 line | 7.0.2 |
| TypeScript 6.0 line | 6.0.3 |
| React and React DOM | 19.3.0 |
| Vite | 8.3.4 |
| `@vitejs/plugin-react` | 6.1.2 |
| TanStack Router (`@tanstack/react-router`) | 1.170.42 |
| TanStack Query (`@tanstack/react-query`) | 5.104.2 |
| TanStack Form (`@tanstack/react-form`) | 1.33.5 |
| Zod | 4.6.6 |
| Tailwind CSS and `@tailwindcss/vite` | 4.3.3 |
| shadcn/ui button dependencies: `@radix-ui/react-slot`, `class-variance-authority`, `clsx`, `tailwind-merge` | 1.5.0, 0.7.1, 2.1.1, 3.7.0 |
| Amplify JS (`aws-amplify`) | 6.22.1 |
| Amplify JS adapter for Next.js (`@aws-amplify/adapter-nextjs`) | 1.8.0 |
| Next.js | 16.4.0 |
| Drizzle ORM | 0.45.4 |
| `pg` and `@types/pg` | 8.23.1 |
| Steiger | 0.7.0 |
| `@feature-sliced/steiger-plugin` | 0.8.0 |
| `@steiger/toolkit` | 0.2.3 |
| Prettier | 3.9.10 |
| ESLint | 10.12.0 |
| `@eslint/js` | 10.0.1 |
| `typescript-eslint` | 8.71.1 |
| Vitest | 5.0.3 |

The newest stable release of the shadcn CLI was 4.21.4. The test project does not run the CLI, because the targets use a pinned copy of the components (Q41).

## Results

| Check | TypeScript 7.0.2 | TypeScript 6.0.3 |
| --- | --- | --- |
| `tsc --noEmit` (React) | Pass | Pass |
| `tsc --noEmit` (Next.js) | Pass | Pass |
| ESLint with type-aware rules | Fail | Pass |
| Steiger (React) | Fail | Pass |
| Steiger (Next.js) | Fail | Pass |
| Prettier | Pass | Pass |
| Vitest (React) | Pass | Pass |
| Vitest (Next.js) | Pass | Pass |
| `vite build` | Pass | Pass |
| `next build` | Pass | Pass |

## Causes of the failures with TypeScript 7.0

TypeScript 7.0 is the native compiler. Its package does not contain the JavaScript API of TypeScript 6.0. The main export of the `typescript` package gives only the version.

- ESLint: `typescript-eslint` 8.71.1 stops with the message "typescript-eslint does not support TS 7.0". Its peer dependency range is `typescript >=4.8.4 <6.1.0`. The issue typescript-eslint/typescript-eslint#10940 tracks the support of TypeScript 7.
- Steiger: `@feature-sliced/filesystem` 3.1.1, a dependency of the Steiger plugin, reads `ts.ModuleResolutionKind.Node10` from the JavaScript API. With TypeScript 7.0 this value does not exist, and Steiger stops with a `TypeError`.

`next build` passed with TypeScript 7.0. Next.js 16.4.0 ran its type check with TypeScript 7.0 and found no error.

## Other findings

- The type declarations of `@feature-sliced/steiger-plugin` 0.8.0 import `@steiger/toolkit`, but the plugin does not declare this package as a dependency. With pnpm, the type-aware ESLint rules then report `steiger.config.ts` as unsafe. The test project adds `@steiger/toolkit` 0.2.3 as a dev dependency to correct this. The React and Next.js generators must also add it.
- The root `package.json` of the test project must have `"type": "module"`, because `eslint.config.js` uses ES module syntax.

## Later change to TypeScript 7

The TypeScript 7.0 announcement tells how to install TypeScript 6.0 next to TypeScript 7.0 for tools that use the JavaScript API. This test did not examine that configuration, because decision Q64 selects one TypeScript line. When `typescript-eslint` and Steiger support TypeScript 7, a later decision can move to TypeScript 7 in a minor release of the toolchain (#150, option (a)). Run `check.sh` again to make sure that all checks pass.
