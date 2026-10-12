# trace: PRD-APP-017, PRD-APP-202, PRD-APP-204, PRD-APP-206
"""The common parts of the React generator and its layer modules.

The React generator (`dsml.generate.react`) calls one module for each FSD
layer. Each layer module gets a `ReactContext` and gives the output files of
its layer. This module holds the context and the rules that all layers use:

- The names of the FSD layers in `src/` (PRD-APP-202).
- The kebab case of the slice names and the file names (PRD-APP-206).
- The public API of a slice: a create-once `index.ts` that re-exports the
  generated `index.gen.ts` (PRD-APP-204).
- The trace header on each generated `.ts` and `.tsx` file (PRD-APP-017).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from dsml.config import Configuration
from dsml.generate.header import file_type_of
from dsml.generate.names import kebab_case
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import Kind, OutputFile
from dsml.ir.model import Element, Ir

SOURCE_FOLDER: Final = "src"
"""The folder of the code in the project. The path alias `@/` refers to it (PRD-APP-205)."""

LAYERS: Final = ("app", "pages", "widgets", "features", "entities", "shared")
"""The FSD layers in `src/`, from the highest to the lowest layer (PRD-APP-202)."""

PUBLIC_API: Final = "index.ts"
"""The create-once public API file of a slice (PRD-APP-204)."""

GENERATED_API: Final = "index.gen.ts"
"""The generated public API file of a slice. `index.ts` re-exports it (PRD-APP-204)."""


# trace: PRD-APP-001, PRD-APP-002
@dataclass(frozen=True, slots=True)
class ReactContext:
    """The input of the layer modules for one `react` application."""

    engine: TemplateEngine
    ir: Ir
    """The IR. The generator reads only the IR (PRD-APP-001)."""
    application: Element
    configuration: Configuration
    folder: str
    """The output folder of the application: an empty text, or a path that ends with "/"."""
    part: str
    """The part of the output that has the files of the application."""

    @property
    def elements(self) -> tuple[str, ...]:
        """The identities of the header of a file that belongs to the whole application."""
        return (self.application.identity,)

    # trace: PRD-APP-017, PRD-TRACE-005
    def generated_file(
        self, path: str, template: str, data: Mapping[str, object], elements: Sequence[str]
    ) -> OutputFile:
        """Render a template into a generated file of the project.

        The path is relative to the project folder. The template gets the
        data, the file type of the path and the elements of the header.
        """
        content = self.engine.render_bytes(
            template,
            {**data, "file_type": file_type_of(path).value, "elements": sorted(set(elements))},
        )
        return OutputFile(f"{self.folder}{path}", content, Kind.GENERATED, self.part)


# trace: PRD-APP-206
def slice_name(name: str) -> str:
    """Give the slice name of a model element name, for example `order-list`."""
    return kebab_case(name)


# trace: PRD-APP-206
def file_name(name: str, suffix: str = "") -> str:
    """Give the file name of a model element name without the extension.

    For example, `file_name("orderList", "page")` gives `order-list-page`.
    """
    return kebab_case(f"{name} {suffix}" if suffix else name)


# trace: PRD-APP-202, PRD-APP-206
def slice_folder(layer: str, name: str) -> str:
    """Give the folder of a slice in the project, for example `src/pages/order-list`."""
    if layer not in LAYERS or layer in ("app", "shared"):
        raise ValueError(f'The layer "{layer}" has no slices.')
    return f"{SOURCE_FOLDER}/{layer}/{slice_name(name)}"


# trace: PRD-APP-017, PRD-APP-204, PRD-CORE-044, PRD-TRACE-005
def public_api_files(
    context: ReactContext, folder: str, modules: Sequence[str], elements: Sequence[str]
) -> list[OutputFile]:
    """Give the public API files of one slice or segment folder.

    `index.gen.ts` re-exports each module, in sorted order. A module is a
    path relative to the folder with no extension, for example
    `ui/order-list-page.gen`. `index.ts` is a create-once file that
    re-exports `index.gen.ts`. A developer can add exports to it.
    """
    generated = context.generated_file(
        f"{folder}/{GENERATED_API}",
        "react/project/index.gen.ts.j2",
        {"modules": sorted(set(modules))},
        elements,
    )
    content = context.engine.render_bytes("react/project/index.ts.j2", {})
    public = OutputFile(
        f"{context.folder}{folder}/{PUBLIC_API}", content, Kind.CREATE_ONCE, context.part
    )
    return [generated, public]
