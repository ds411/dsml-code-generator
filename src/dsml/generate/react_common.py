# trace: PRD-APP-017, PRD-APP-202, PRD-APP-204, PRD-APP-206, PRD-APP-303, PRD-APP-305
"""The common parts of the React generator and its layer modules.

The React generator (`dsml.generate.react`) calls one module for each FSD
layer. Each layer module gets a `ReactContext` and gives the output files of
its layer. This module holds the context and the rules that all layers use:

- The names of the FSD layers in `src/` (PRD-APP-202).
- The layout of the layers: the folder names of the layers, the path alias
  and the server-only public API. The React target and the Next.js target
  use different layouts (PRD-APP-303, PRD-APP-305).
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
"""The FSD layers in `src/`, from the highest to the lowest layer (PRD-APP-202).

These are the standard names of the layers. A layout gives the folder name
of each layer.
"""

SLICED_LAYERS: Final = ("pages", "widgets", "features", "entities")
"""The FSD layers that have slices. The layers `app` and `shared` have segments only."""

PUBLIC_API: Final = "index.ts"
"""The create-once public API file of a slice (PRD-APP-204)."""

GENERATED_API: Final = "index.gen.ts"
"""The generated public API file of a slice. `index.ts` re-exports it (PRD-APP-204)."""

SERVER_API: Final = "index.server.ts"
"""The create-once server-only public API file of a slice (PRD-APP-305)."""

GENERATED_SERVER_API: Final = "index.server.gen.ts"
"""The generated server-only public API file of a slice. `index.server.ts` re-exports it."""


# trace: PRD-APP-202, PRD-APP-205, PRD-APP-206, PRD-APP-303, PRD-APP-304, PRD-APP-305
@dataclass(frozen=True, slots=True)
class FsdLayout:
    """The layout of the FSD layers in `src/` for one target.

    The layer modules use the standard layer names of `LAYERS`. The layout
    gives the folder name of each layer, the path alias of `src/` and the
    public API files of a slice. Thus the React target and the Next.js
    target can use the same layer writers.
    """

    app: str
    """The folder name of the layer `app`: `app` (React) or `_app` (Next.js)."""
    pages: str
    """The folder name of the layer `pages`: `pages` (React) or `_pages` (Next.js)."""
    alias: str = "@/"
    """The path alias that refers to `src/` (PRD-APP-205)."""
    server_api: bool = False
    """Tell if a slice exports its server-only modules through `index.server.ts` (PRD-APP-305)."""

    def layer_name(self, layer: str) -> str:
        """Give the folder name of a layer, for example `_pages` for `pages` in Next.js."""
        if layer not in LAYERS:
            raise ValueError(f'The layer "{layer}" is not an FSD layer.')
        return {"app": self.app, "pages": self.pages}.get(layer, layer)

    def layer_folder(self, layer: str) -> str:
        """Give the folder of a layer in the project, for example `src/_app`."""
        return f"{SOURCE_FOLDER}/{self.layer_name(layer)}"

    def slice_folder(self, layer: str, name: str) -> str:
        """Give the folder of a slice in the project, for example `src/_pages/order-list`.

        The name is a model element name. The folder name is its kebab case
        (PRD-APP-206).
        """
        if layer not in SLICED_LAYERS:
            raise ValueError(f'The layer "{layer}" has no slices.')
        return f"{self.layer_folder(layer)}/{slice_name(name)}"

    def import_path(self, layer: str, name: str = "") -> str:
        """Give the import path of a layer or of a slice with the path alias.

        For example, `import_path("pages", "order-list")` gives
        `@/_pages/order-list` in Next.js. An empty name gives the path of
        the layer, for example `@/shared`.
        """
        path = f"{self.alias}{self.layer_name(layer)}"
        return f"{path}/{name}" if name else path


REACT_LAYOUT: Final = FsdLayout(app="app", pages="pages")
"""The layout of the React target: the standard layer names (PRD-APP-202)."""

NEXTJS_LAYOUT: Final = FsdLayout(app="_app", pages="_pages", server_api=True)
"""The layout of the Next.js target (PRD-APP-303, PRD-APP-305).

The layers `app` and `pages` have the names `_app` and `_pages`, because
the Next.js `app/` folder holds the routes. A slice exports its server-only
modules through `index.server.ts`.
"""


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
    layout: FsdLayout = REACT_LAYOUT
    """The layout of the FSD layers. The generator of the target gives it."""

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
        data, the layout, the file type of the path and the elements of the
        header.
        """
        content = self.engine.render_bytes(
            template,
            {
                "layout": self.layout,
                **data,
                "file_type": file_type_of(path).value,
                "elements": sorted(set(elements)),
            },
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
    """Give the folder of a slice in the React layout, for example `src/pages/order-list`."""
    return REACT_LAYOUT.slice_folder(layer, name)


# trace: PRD-APP-017, PRD-APP-204, PRD-APP-305, PRD-CORE-044, PRD-TRACE-005
def public_api_files(
    context: ReactContext,
    folder: str,
    modules: Sequence[str],
    elements: Sequence[str],
    server_modules: Sequence[str] = (),
) -> list[OutputFile]:
    """Give the public API files of one slice or segment folder.

    `index.gen.ts` re-exports each module, in sorted order. A module is a
    path relative to the folder with no extension, for example
    `ui/order-list-page.gen`. `index.ts` is a create-once file that
    re-exports `index.gen.ts`. A developer can add exports to it.

    The server-only modules go into `index.server.gen.ts` and the
    create-once `index.server.ts` in the same manner (PRD-APP-305). Only a
    layout with a server-only public API accepts server-only modules.
    """
    files = _api_files(context, folder, modules, elements, GENERATED_API, PUBLIC_API)
    if server_modules:
        if not context.layout.server_api:
            raise ValueError(f'The layout of the folder "{folder}" has no server-only public API.')
        files.extend(
            _api_files(context, folder, server_modules, elements, GENERATED_SERVER_API, SERVER_API)
        )
    return files


def _api_files(
    context: ReactContext,
    folder: str,
    modules: Sequence[str],
    elements: Sequence[str],
    generated_name: str,
    public_name: str,
) -> list[OutputFile]:
    generated = context.generated_file(
        f"{folder}/{generated_name}",
        "react/project/index.gen.ts.j2",
        {"modules": sorted(set(modules))},
        elements,
    )
    content = context.engine.render_bytes(
        "react/project/index.ts.j2",
        {"generated": generated_name.removesuffix(".ts"), "server": public_name == SERVER_API},
    )
    public = OutputFile(
        f"{context.folder}{folder}/{public_name}", content, Kind.CREATE_ONCE, context.part
    )
    return [generated, public]
