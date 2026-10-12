# Version baseline of the TypeScript targets

Story #158 added the items of the React and Next.js targets to the version baseline `src/dsml/versions.toml`. Decision record 09 (Q64) gives the line of each item. This note gives the source and the license of each exact version. Story #167 added the items `types-react` and `types-react-dom`, because React does not include its type declarations. Story #180 added the items `server-only`, `tailwindcss-postcss` and `types-node` of the Next.js target, and the base image `node-image` of its Dockerfile.

## Rules

- Each version is the newest release of its line on 12 October 2026. The source is the npm registry (`npm view <package> version license`).
- The TypeScript line is 6.0, because `typescript-eslint` and Steiger do not operate with TypeScript 7.0 (story #190, `docs/notes/typescript-check.md`).
- The lines of Node.js, React and Next.js come from decision record 03. The line of pnpm comes from decision record 09.
- A line is the major version. For a package with a major version of 0, the line is the minor version, for example `0.45`.
- The name of an item is the npm package name without `@` and with `-` in place of `/`. For example, the item of `@tanstack/react-router` is `tanstack-react-router`.
- Each version agrees with the versions of the test project of story #190. Thus the checks of `scripts/typescript-check/` apply to this baseline.

## Items and licenses

| Item | npm package | Line | Version | License |
| --- | --- | --- | --- | --- |
| `node` | Node.js runtime | 26 | 26.11.1 | MIT |
| `pnpm` | `pnpm` | 12 | 12.11.2 | MIT |
| `typescript` | `typescript` | 6.0 | 6.0.3 | Apache-2.0 |
| `react` | `react` | 19 | 19.3.0 | MIT |
| `react-dom` | `react-dom` | 19 | 19.3.0 | MIT |
| `types-react` | `@types/react` | 19 | 19.3.0 | MIT |
| `types-react-dom` | `@types/react-dom` | 19 | 19.3.0 | MIT |
| `vite` | `vite` | 8 | 8.3.4 | MIT |
| `vitejs-plugin-react` | `@vitejs/plugin-react` | 6 | 6.1.2 | MIT |
| `tanstack-react-router` | `@tanstack/react-router` | 1 | 1.170.42 | MIT |
| `tanstack-react-query` | `@tanstack/react-query` | 5 | 5.104.2 | MIT |
| `tanstack-react-form` | `@tanstack/react-form` | 1 | 1.33.5 | MIT |
| `zod` | `zod` | 4 | 4.6.6 | MIT |
| `tailwindcss` | `tailwindcss` | 4 | 4.3.3 | MIT |
| `tailwindcss-vite` | `@tailwindcss/vite` | 4 | 4.3.3 | MIT |
| `shadcn-ui` | `shadcn` (the CLI release of the copy) | 4 | 4.21.4 | MIT |
| `radix-ui-react-slot` | `@radix-ui/react-slot` | 1 | 1.5.0 | MIT |
| `radix-ui-react-alert-dialog` | `@radix-ui/react-alert-dialog` | 1 | 1.2.0 | MIT |
| `radix-ui-react-label` | `@radix-ui/react-label` | 2 | 2.1.17 | MIT |
| `radix-ui-react-separator` | `@radix-ui/react-separator` | 1 | 1.2.0 | MIT |
| `lucide-react` | `lucide-react` | 1 | 1.55.0 | ISC |
| `class-variance-authority` | `class-variance-authority` | 0.7 | 0.7.1 | Apache-2.0 |
| `clsx` | `clsx` | 2 | 2.1.1 | MIT |
| `tailwind-merge` | `tailwind-merge` | 3 | 3.7.0 | MIT |
| `aws-amplify` | `aws-amplify` | 6 | 6.22.1 | Apache-2.0 |
| `aws-amplify-adapter-nextjs` | `@aws-amplify/adapter-nextjs` | 1 | 1.8.0 | Apache-2.0 |
| `next` | `next` | 16 | 16.4.0 | MIT |
| `drizzle-orm` | `drizzle-orm` | 0.45 | 0.45.4 | Apache-2.0 |
| `pg` | `pg` | 8 | 8.23.1 | MIT |
| `types-pg` | `@types/pg` | 8 | 8.23.1 | MIT |
| `server-only` | `server-only` | 0.0 | 0.0.1 | MIT |
| `tailwindcss-postcss` | `@tailwindcss/postcss` | 4 | 4.3.3 | MIT |
| `types-node` | `@types/node` | 26 | 26.6.5 | MIT |
| `steiger` | `steiger` | 0.7 | 0.7.0 | MIT |
| `feature-sliced-steiger-plugin` | `@feature-sliced/steiger-plugin` | 0.8 | 0.8.0 | MIT |
| `steiger-toolkit` | `@steiger/toolkit` | 0.2 | 0.2.3 | MIT |
| `prettier` | `prettier` | 3 | 3.9.10 | MIT |
| `eslint` | `eslint` | 10 | 10.12.0 | MIT |
| `eslint-js` | `@eslint/js` | 10 | 10.0.1 | MIT |
| `typescript-eslint` | `typescript-eslint` | 8 | 8.71.1 | MIT |
| `vitest` | `vitest` | 5 | 5.0.3 | MIT |
| `jsdom` | `jsdom` | 30 | 30.1.2 | MIT |
| `testing-library-dom` | `@testing-library/dom` | 10 | 10.4.2 | MIT |
| `testing-library-react` | `@testing-library/react` | 16 | 16.3.3 | MIT |
| `testing-library-user-event` | `@testing-library/user-event` | 14 | 14.6.7 | MIT |

Story #172 added the items of the Radix UI packages, `lucide-react`, `jsdom` and Testing Library. The shadcn/ui components of the features layer need the Radix UI packages and `lucide-react`. The component tests need `jsdom` and Testing Library. Each version is the newest release of its line on 12 October 2026.

MIT, Apache-2.0 and ISC are permissive licenses. The company accepts them for internal software (PRD-TOP-007).

## Copy of shadcn/ui

The generator package holds a pinned copy of the shadcn/ui components (Q41). The copy comes from the release tag `shadcn@4.21.4` of the repository `shadcn-ui/ui`. The item `shadcn-ui-commit` gives the full commit SHA of that tag: `3464245c4513b7998b1d11fa9c67b71cc1534dc7`. The items `radix-ui-react-slot`, `class-variance-authority`, `clsx` and `tailwind-merge` are the dependencies of the components. M10 adds the copy to the package and uses these items.

## Dev tools of the toolchain

The toolchain CI needs the TypeScript tools for the golden checks of M10 and M11 (PRD-CORE-011). `package.json` has these dev tools, with the versions of the baseline:

- `typescript`, `eslint`, `@eslint/js` and `typescript-eslint`.
- `steiger`, `@feature-sliced/steiger-plugin` and `@steiger/toolkit`. The Steiger plugin does not declare `@steiger/toolkit`, thus `package.json` adds it (story #190).
- `prettier`.

`package.json` also gives the versions of pnpm (`packageManager`) and Node.js (`devEngines`). The test `tests/test_versions.py` makes sure that all these versions agree with the baseline.

## Licenses of the transitive dependencies

`pnpm licenses list` gives the licenses of all packages that `pnpm-lock.yaml` installs. All are permissive: MIT, Apache-2.0, ISC, BSD-2-Clause, BSD-3-Clause, BlueOak-1.0.0 (`minimatch`), Python-2.0 (`argparse`) and WTFPL (`prexit`, a dependency of Steiger). The Node.js runtime package `node` gives a list of licenses. The Node.js project uses the MIT license.

## Known warning

`pnpm install` reports an unmet peer dependency: `tsconfck` 3.1.6, a dependency of Steiger, asks for TypeScript `^5.0.0`. The peer dependency is optional. Steiger operates with TypeScript 6.0.3 (story #190).
