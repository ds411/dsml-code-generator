# trace: PRD-APP-001, PRD-APP-002, PRD-APP-010, PRD-APP-012, PRD-APP-013, PRD-APP-015
# trace: PRD-APP-017, PRD-APP-301, PRD-APP-302, PRD-APP-303, PRD-APP-325, PRD-APP-333
# trace: PRD-APP-334, PRD-CORE-036, PRD-CORE-039, PRD-CORE-046, PRD-TOP-008
"""The Next.js generator (phase 3).

The generator reads only the IR and the configuration (PRD-APP-001,
PRD-CORE-026). For each application with the target `nextjs`, it writes the
project files into the output folder of the application (PRD-APP-002):

- The fixed-name files of PRD-APP-334: `package.json`, `tsconfig.json`,
  `next.config.ts`, `components.json`, `steiger.config.ts`,
  `eslint.config.js`, `vitest.config.ts`, `drizzle.config.ts`, `Dockerfile`
  and `.dockerignore`.
- The route files of the root layout and of `GET /healthz` in `app/`. The
  generator owns the full `app/` folder (PRD-APP-302).
- The root layout and the health handler in `src/_app/` (PRD-APP-012,
  PRD-APP-303).
- The segment `src/shared/config`: the public runtime values of
  PRD-APP-325.
- The segment `src/shared/log`: the JSON log lines with a request ID of
  PRD-APP-015.

Then it calls one module for each part, in this order: `nextjs_database`,
`nextjs_auth`, `nextjs_slices`, `nextjs_routes` and `nextjs_pages`. Each
module gives the files of its part. The generator gives the Next.js layout
`NEXTJS_LAYOUT` to the modules: the layers `_app` and `_pages`, and the
server-only public API `index.server.ts` (PRD-APP-303, PRD-APP-305).

The versions come from the version baseline `versions.toml` (PRD-APP-301,
PRD-TOP-008). The generator does not write `pnpm-lock.yaml` (PRD-CORE-036).
"""

from collections.abc import Callable, Collection, Sequence
from typing import Final

from dsml.config import Configuration
from dsml.database.snapshot import SNAPSHOT_PATH
from dsml.generate.fastapi import output_folder
from dsml.generate.names import kebab_case
from dsml.generate.nextjs_auth import auth_files
from dsml.generate.nextjs_database import database_files
from dsml.generate.nextjs_pages import pages_files
from dsml.generate.nextjs_routes import routes_files
from dsml.generate.nextjs_slices import slices_files
from dsml.generate.react import dependencies
from dsml.generate.react_common import NEXTJS_LAYOUT, ReactContext, public_api_files
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import OutputFile, application_part
from dsml.ir.model import Element, EnumValue, Ir
from dsml.versions import load_baseline, pinned_version

TARGET: Final = "nextjs"
"""The literal of `DSML::Target` that selects this generator."""

FIXED_NAMES: Final = (
    ".dockerignore",
    "Dockerfile",
    "app/",
    "components.json",
    "drizzle.config.ts",
    "eslint.config.js",
    "middleware.ts",
    "migrations/meta/_journal.json",
    "next.config.ts",
    "package.json",
    "proxy.ts",
    "steiger.config.ts",
    "tsconfig.json",
    "vitest.config.ts",
)
"""The fixed-name generated files of the Next.js target (PRD-APP-334).

The item `app/` is the full Next.js `app/` folder (PRD-APP-302). The list
has `middleware.ts` and `proxy.ts`, because PRD-APP-334 gives the two names.
The pinned Next.js version uses `proxy.ts` (PRD-APP-323).
"""

STATE_FILES: Final = (SNAPSHOT_PATH,)
"""The generated files of the toolchain state that have a fixed path (PRD-APP-124).

The name of the schema snapshot does not end with `.gen.json`, because
PRD-APP-124 gives its path. The generator owns the file.
"""

PROJECT_VERSION: Final = "0.1.0"
"""The version of the generated project."""

PORT: Final = 3000
"""The port of the server in the container (PRD-APP-333)."""

RUNTIME_PACKAGES: Final = {
    "@aws-amplify/adapter-nextjs": "aws-amplify-adapter-nextjs",
    "@radix-ui/react-alert-dialog": "radix-ui-react-alert-dialog",
    "@radix-ui/react-label": "radix-ui-react-label",
    "@radix-ui/react-separator": "radix-ui-react-separator",
    "@radix-ui/react-slot": "radix-ui-react-slot",
    "@tanstack/react-form": "tanstack-react-form",
    "@tanstack/react-query": "tanstack-react-query",
    "aws-amplify": "aws-amplify",
    "class-variance-authority": "class-variance-authority",
    "clsx": "clsx",
    "drizzle-orm": "drizzle-orm",
    "lucide-react": "lucide-react",
    "next": "next",
    "pg": "pg",
    "react": "react",
    "react-dom": "react-dom",
    "server-only": "server-only",
    "tailwind-merge": "tailwind-merge",
    "zod": "zod",
}
"""The run-time dependencies and their baseline items (PRD-APP-301)."""

DEV_PACKAGES: Final = {
    "@eslint/js": "eslint-js",
    "@feature-sliced/steiger-plugin": "feature-sliced-steiger-plugin",
    "@steiger/toolkit": "steiger-toolkit",
    "@tailwindcss/postcss": "tailwindcss-postcss",
    "@testing-library/dom": "testing-library-dom",
    "@testing-library/react": "testing-library-react",
    "@testing-library/user-event": "testing-library-user-event",
    "@types/node": "types-node",
    "@types/pg": "types-pg",
    "@types/react": "types-react",
    "@types/react-dom": "types-react-dom",
    "eslint": "eslint",
    "jsdom": "jsdom",
    "prettier": "prettier",
    "steiger": "steiger",
    "tailwindcss": "tailwindcss",
    "typescript": "typescript",
    "typescript-eslint": "typescript-eslint",
    "vitest": "vitest",
}
"""The dev dependencies and their baseline items (PRD-APP-301, PRD-CORE-011).

The Steiger plugin does not declare `@steiger/toolkit`, thus the project
adds it (story #190). Next.js runs Tailwind CSS through PostCSS, thus the
project adds `@tailwindcss/postcss`.
"""

PUBLIC_CONFIG_VARIABLES: Final = (
    ("region", "AWS_REGION"),
    ("userPoolId", "COGNITO_USER_POOL_ID"),
    ("appClientId", "COGNITO_APP_CLIENT_ID"),
    ("loginDomain", "COGNITO_LOGIN_DOMAIN"),
)
"""The public runtime values and their server-side environment variables (PRD-APP-325).

The root layout reads the variables at run time and gives the values to
client components (PRD-APP-010). The build reads no `NEXT_PUBLIC_` variable.
"""

ROOT_LAYOUT: Final = "src/_app/layout/root-layout.gen.tsx"
"""The root layout. `app/layout.tsx` re-exports it (PRD-APP-302)."""

HEALTH_HANDLER: Final = "src/_app/api-routes/healthz.gen.ts"
"""The handler of `GET /healthz`. `app/healthz/route.ts` re-exports it (PRD-APP-012)."""

CONFIG_SEGMENT: Final = "src/shared/config"
"""The segment of the public runtime values (PRD-APP-325)."""

LOG_SEGMENT: Final = "src/shared/log"
"""The segment of the JSON logs (PRD-APP-015)."""

# The template of each project file, by the path in the output folder.
_TEMPLATES: Final = {
    ".dockerignore": "nextjs/project/dockerignore.j2",
    "Dockerfile": "nextjs/project/Dockerfile.j2",
    "app/healthz/route.ts": "nextjs/project/healthz-route.ts.j2",
    "app/layout.tsx": "nextjs/project/layout.tsx.j2",
    "components.json": "nextjs/project/components.json.j2",
    "drizzle.config.ts": "nextjs/project/drizzle.config.ts.j2",
    "eslint.config.js": "nextjs/project/eslint.config.js.j2",
    "next.config.ts": "nextjs/project/next.config.ts.j2",
    "package.json": "nextjs/project/package.json.j2",
    "steiger.config.ts": "nextjs/project/steiger.config.ts.j2",
    "tsconfig.json": "nextjs/project/tsconfig.json.j2",
    "vitest.config.ts": "nextjs/project/vitest.config.ts.j2",
    HEALTH_HANDLER: "nextjs/project/healthz.gen.ts.j2",
    ROOT_LAYOUT: "nextjs/project/root-layout.gen.tsx.j2",
    f"{CONFIG_SEGMENT}/public-config.gen.tsx": "nextjs/project/public-config.gen.tsx.j2",
    f"{CONFIG_SEGMENT}/public-config.server.gen.ts": (
        "nextjs/project/public-config.server.gen.ts.j2"
    ),
    f"{LOG_SEGMENT}/logger.server.gen.ts": "nextjs/project/logger.server.gen.ts.j2",
    f"{LOG_SEGMENT}/request-id.gen.ts": "nextjs/project/request-id.gen.ts.j2",
}

PART_FUNCTIONS: Final[tuple[Callable[[ReactContext], list[OutputFile]], ...]] = (
    database_files,
    auth_files,
    slices_files,
    routes_files,
    pages_files,
)
"""The function of each part module, in the order of the milestone M11 (#156)."""


# trace: PRD-APP-001, PRD-APP-002, PRD-APP-017, PRD-CORE-039
class NextjsGenerator:
    """The generator of the target `nextjs`."""

    name = "nextjs"
    fixed_names: Collection[str] = (*FIXED_NAMES, *STATE_FILES)

    def generate(
        self, ir: Ir, configuration: Configuration, parts: Collection[str] | None
    ) -> Sequence[OutputFile]:
        files: list[OutputFile] = []
        engine: TemplateEngine | None = None
        for application in applications(ir):
            part = application_part(application.name)
            if parts is not None and part not in parts:
                continue
            if engine is None:
                engine = TemplateEngine()
            context = ReactContext(
                engine,
                ir,
                application,
                configuration,
                output_folder(application, configuration),
                part,
                NEXTJS_LAYOUT,
            )
            files.extend(application_files(context))
        return files


# trace: PRD-APP-001
def applications(ir: Ir) -> list[Element]:
    """Give the applications of the IR with the target `nextjs`, sorted by identity."""
    return sorted(
        (
            element
            for element in ir.elements
            if element.kind == "Application" and _target(element) == TARGET
        ),
        key=lambda element: element.identity,
    )


def _target(application: Element) -> str | None:
    for attribute in application.attributes:
        if attribute.name == "target" and isinstance(attribute.value, EnumValue):
            return attribute.value.literal
    return None


# trace: PRD-APP-002, PRD-APP-010, PRD-APP-012, PRD-APP-013, PRD-APP-015, PRD-APP-017
# trace: PRD-APP-301, PRD-APP-302, PRD-APP-325, PRD-APP-333, PRD-CORE-036, PRD-CORE-046
# trace: PRD-TRACE-005
def application_files(context: ReactContext) -> list[OutputFile]:
    """Give the project files and the files of each part of one application."""
    baseline = load_baseline()
    application = context.application
    runtime, dev = dependencies(
        application, context.configuration, baseline, (RUNTIME_PACKAGES, DEV_PACKAGES), "Next.js"
    )
    data: dict[str, object] = {
        "application": application.name,
        "project": kebab_case(application.name),
        "version": PROJECT_VERSION,
        "dependencies": runtime,
        "dev_dependencies": dev,
        "node_version": pinned_version("node", baseline),
        "pnpm_version": pinned_version("pnpm", baseline),
        "node_image": baseline["node-image"].value,
        "port": PORT,
        "variables": PUBLIC_CONFIG_VARIABLES,
    }
    files = [
        context.generated_file(path, template, data, context.elements)
        for path, template in sorted(_TEMPLATES.items())
    ]
    files.extend(
        public_api_files(
            context,
            CONFIG_SEGMENT,
            ["public-config.gen"],
            context.elements,
            ["public-config.server.gen"],
        )
    )
    files.extend(
        public_api_files(
            context,
            LOG_SEGMENT,
            ["request-id.gen"],
            context.elements,
            ["logger.server.gen"],
        )
    )
    for part_files in PART_FUNCTIONS:
        files.extend(part_files(context))
    return sorted(files, key=lambda file: file.path)
