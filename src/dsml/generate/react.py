# trace: PRD-APP-001, PRD-APP-002, PRD-APP-017, PRD-APP-201, PRD-APP-202, PRD-APP-233
# trace: PRD-APP-235, PRD-CORE-036, PRD-CORE-046, PRD-TOP-008
"""The React generator (phase 2).

The generator reads only the IR and the configuration (PRD-APP-001,
PRD-CORE-026). For each application with the target `react`, it writes the
project files into the output folder of the application (PRD-APP-002):

- The fixed-name files of PRD-APP-235: `package.json`, `tsconfig.json`,
  `vite.config.ts`, `index.html`, `components.json`, `steiger.config.ts` and
  `eslint.config.js`.
- `src/main.gen.tsx`: the entry module of the page.

Then it calls one module for each FSD layer, from the lowest to the highest
layer (PRD-APP-202): `react_shared`, `react_entities`, `react_features`,
`react_widgets`, `react_pages` and `react_app`. Each module gives the files
of its layer.

The versions come from the version baseline `versions.toml` (PRD-APP-201,
PRD-TOP-008). The generator does not write `pnpm-lock.yaml` (PRD-CORE-036).
"""

from collections.abc import Callable, Collection, Sequence
from typing import Final

from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.generate.fastapi import output_folder
from dsml.generate.names import kebab_case
from dsml.generate.react_app import app_files
from dsml.generate.react_common import ReactContext
from dsml.generate.react_entities import entities_files
from dsml.generate.react_features import features_files
from dsml.generate.react_pages import pages_files
from dsml.generate.react_shared import shared_files
from dsml.generate.react_widgets import widgets_files
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import OutputFile, application_part
from dsml.ir.model import Element, EnumValue, Ir
from dsml.versions import Pin, load_baseline, pinned_version

TARGET: Final = "react"
"""The literal of `DSML::Target` that selects this generator."""

FIXED_NAMES: Final = (
    "components.json",
    "eslint.config.js",
    "index.html",
    "package.json",
    "steiger.config.ts",
    "tsconfig.json",
    "vite.config.ts",
)
"""The fixed-name generated files of the React target (PRD-APP-235)."""

ENTRY_MODULE: Final = "src/main.gen.tsx"
"""The entry module of the page. `index.html` loads it."""

PROJECT_VERSION: Final = "0.1.0"
"""The version of the generated project."""

RUNTIME_PACKAGES: Final = {
    "@radix-ui/react-alert-dialog": "radix-ui-react-alert-dialog",
    "@radix-ui/react-label": "radix-ui-react-label",
    "@radix-ui/react-separator": "radix-ui-react-separator",
    "@radix-ui/react-slot": "radix-ui-react-slot",
    "@tanstack/react-form": "tanstack-react-form",
    "@tanstack/react-query": "tanstack-react-query",
    "@tanstack/react-router": "tanstack-react-router",
    "aws-amplify": "aws-amplify",
    "class-variance-authority": "class-variance-authority",
    "clsx": "clsx",
    "lucide-react": "lucide-react",
    "react": "react",
    "react-dom": "react-dom",
    "tailwind-merge": "tailwind-merge",
    "zod": "zod",
}
"""The run-time dependencies and their baseline items (PRD-APP-201)."""

DEV_PACKAGES: Final = {
    "@eslint/js": "eslint-js",
    "@feature-sliced/steiger-plugin": "feature-sliced-steiger-plugin",
    "@steiger/toolkit": "steiger-toolkit",
    "@tailwindcss/vite": "tailwindcss-vite",
    "@testing-library/dom": "testing-library-dom",
    "@testing-library/react": "testing-library-react",
    "@testing-library/user-event": "testing-library-user-event",
    "@types/react": "types-react",
    "@types/react-dom": "types-react-dom",
    "@vitejs/plugin-react": "vitejs-plugin-react",
    "eslint": "eslint",
    "jsdom": "jsdom",
    "prettier": "prettier",
    "steiger": "steiger",
    "tailwindcss": "tailwindcss",
    "typescript": "typescript",
    "typescript-eslint": "typescript-eslint",
    "vite": "vite",
    "vitest": "vitest",
}
"""The dev dependencies and their baseline items (PRD-APP-201, PRD-CORE-011).

The Steiger plugin does not declare `@steiger/toolkit`, thus the project
adds it (story #190).
"""

# The template of each project file, by the path in the output folder.
_TEMPLATES: Final = {
    "components.json": "react/project/components.json.j2",
    "eslint.config.js": "react/project/eslint.config.js.j2",
    "index.html": "react/project/index.html.j2",
    "package.json": "react/project/package.json.j2",
    "steiger.config.ts": "react/project/steiger.config.ts.j2",
    "tsconfig.json": "react/project/tsconfig.json.j2",
    "vite.config.ts": "react/project/vite.config.ts.j2",
    ENTRY_MODULE: "react/project/main.gen.tsx.j2",
}

LAYER_FUNCTIONS: Final[tuple[Callable[[ReactContext], list[OutputFile]], ...]] = (
    shared_files,
    entities_files,
    features_files,
    widgets_files,
    pages_files,
    app_files,
)
"""The function of each FSD layer module, from the lowest to the highest layer."""


# trace: PRD-APP-001, PRD-APP-002, PRD-APP-017, PRD-CORE-039
class ReactGenerator:
    """The generator of the target `react`."""

    name = "react"
    fixed_names: Collection[str] = FIXED_NAMES

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
            )
            files.extend(application_files(context))
        return files


# trace: PRD-APP-001
def applications(ir: Ir) -> list[Element]:
    """Give the applications of the IR with the target `react`, sorted by identity."""
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


# trace: PRD-APP-201, PRD-CORE-046, PRD-TOP-008
def dependencies(
    application: Element, configuration: Configuration, baseline: dict[str, Pin]
) -> tuple[dict[str, str], dict[str, str]]:
    """Give the run-time and the dev dependencies of an application, each sorted by name.

    The run-time dependencies are the pinned packages of the target and the
    extra dependencies of the key `applications.<name>.dependencies`
    (PRD-CORE-046). An extra dependency has the form `<package>@<version>`,
    for example `date-fns@4.1.0` or `@scope/package@1.2.3`.
    """
    runtime = {name: pinned_version(item, baseline) for name, item in RUNTIME_PACKAGES.items()}
    dev = {name: pinned_version(item, baseline) for name, item in DEV_PACKAGES.items()}
    settings = configuration.application(application.name)
    for text in settings.dependencies if settings is not None else ():
        at = text.rfind("@")
        name, version = text[:at], text[at + 1 :]
        if at <= 0 or not version or name == "@":
            raise ToolchainError(
                f'The dependency "{text}" of the application "{application.name}" must have '
                'the form "<package>@<version>".'
            )
        if name in runtime or name in dev:
            raise ToolchainError(
                f'The dependency "{text}" of the application "{application.name}" is a package '
                "of the React target. The version baseline gives its version. Remove it from "
                f"the key applications.{application.name}.dependencies."
            )
        runtime[name] = version
    return dict(sorted(runtime.items())), dict(sorted(dev.items()))


# trace: PRD-APP-002, PRD-APP-017, PRD-APP-201, PRD-APP-202, PRD-APP-205, PRD-APP-233
# trace: PRD-APP-234, PRD-APP-235, PRD-CORE-036, PRD-CORE-046, PRD-TRACE-005
def application_files(context: ReactContext) -> list[OutputFile]:
    """Give the project files and the files of each FSD layer of one application."""
    baseline = load_baseline()
    application = context.application
    runtime, dev = dependencies(application, context.configuration, baseline)
    data: dict[str, object] = {
        "application": application.name,
        "project": kebab_case(application.name),
        "version": PROJECT_VERSION,
        "dependencies": runtime,
        "dev_dependencies": dev,
        "node_version": pinned_version("node", baseline),
        "pnpm_version": pinned_version("pnpm", baseline),
        "entry_module": ENTRY_MODULE,
    }
    files = [
        context.generated_file(path, template, data, context.elements)
        for path, template in sorted(_TEMPLATES.items())
    ]
    for layer_files in LAYER_FUNCTIONS:
        files.extend(layer_files(context))
    return sorted(files, key=lambda file: file.path)
