"""Tests of the layout of the FSD layer writers (story #179).

The layer modules of the React generator use a layout: the folder names of
the layers, the path alias and the server-only public API. The React
generator gives the React layout. The Next.js generator gives the Next.js
layout with the layer names `_app` and `_pages` (PRD-APP-303). The golden
tests of the React generator show that the React output does not change.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from dsml.config import parse_configuration
from dsml.generate.react import LAYER_FUNCTIONS
from dsml.generate.react_common import (
    LAYERS,
    NEXTJS_LAYOUT,
    REACT_LAYOUT,
    FsdLayout,
    ReactContext,
    public_api_files,
)
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import Kind, OutputFile, application_part
from dsml.ir.model import Element, Ir, Location

ROOT = Path(__file__).resolve().parent.parent
PORTAL_MODEL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"

# The folder and the import path of each layer that the Next.js layout renames.
RENAMED = {"src/app/": "src/_app/", "src/pages/": "src/_pages/"}
RENAMED_IMPORTS = {'"@/app/': '"@/_app/', '"@/pages/': '"@/_pages/'}


@pytest.fixture(scope="module")
def portal_ir() -> Ir:
    """Make the IR of the order portal model one time for the tests of this module."""
    from dsml.adapter.convert import make_ir

    return make_ir([PORTAL_MODEL], ROOT)


def portal_context(ir: Ir, layout: FsdLayout) -> ReactContext:
    application = next(item for item in ir.elements if item.name == "orderPortal")
    configuration = parse_configuration(
        'schema = 1\n\n[applications.orderPortal]\noutput = "."\n', Path("dsml.toml")
    )
    return ReactContext(
        TemplateEngine(),
        ir,
        application,
        configuration,
        "",
        application_part(application.name),
        layout,
    )


def layer_files(context: ReactContext) -> dict[str, OutputFile]:
    return {file.path: file for function in LAYER_FUNCTIONS for file in function(context)}


def small_context(layout: FsdLayout) -> ReactContext:
    return ReactContext(
        TemplateEngine(),
        Ir(elements=()),
        _application(),
        parse_configuration("schema = 1\n", Path("dsml.toml")),
        "web/",
        "web",
        layout,
    )


def _application() -> Element:
    location = Location(file="model.sysml", line=1, column=1)
    return Element(
        identity="Shop::web",
        kind="Application",
        name="web",
        qualified_name="Shop::web",
        location=location,
        attributes=(),
    )


# trace: PRD-APP-202, PRD-APP-205
def test_react_layout_has_the_standard_layer_names() -> None:
    assert [REACT_LAYOUT.layer_name(layer) for layer in LAYERS] == list(LAYERS)
    assert REACT_LAYOUT.alias == "@/"
    assert not REACT_LAYOUT.server_api
    assert REACT_LAYOUT.slice_folder("pages", "orderList") == "src/pages/order-list"


# trace: PRD-APP-303, PRD-APP-304
def test_nextjs_layout_renames_the_layers_app_and_pages() -> None:
    assert [NEXTJS_LAYOUT.layer_folder(layer) for layer in LAYERS] == [
        "src/_app",
        "src/_pages",
        "src/widgets",
        "src/features",
        "src/entities",
        "src/shared",
    ]
    assert NEXTJS_LAYOUT.alias == "@/"
    assert NEXTJS_LAYOUT.server_api


# trace: PRD-APP-206, PRD-APP-303, PRD-APP-304
def test_paths_of_a_slice_with_the_nextjs_layer_names() -> None:
    assert NEXTJS_LAYOUT.slice_folder("pages", "orderList") == "src/_pages/order-list"
    assert NEXTJS_LAYOUT.slice_folder("features", "cancelOrder") == "src/features/cancel-order"
    assert NEXTJS_LAYOUT.import_path("pages", "order-list") == "@/_pages/order-list"
    assert NEXTJS_LAYOUT.import_path("entities", "order") == "@/entities/order"
    assert NEXTJS_LAYOUT.import_path("app") == "@/_app"


@pytest.mark.parametrize("layer", ["app", "shared"])
def test_a_layer_with_no_slices_has_no_slice_folder(layer: str) -> None:
    with pytest.raises(ValueError, match="has no slices"):
        NEXTJS_LAYOUT.slice_folder(layer, "order")


def test_an_unknown_layer_has_no_name() -> None:
    with pytest.raises(ValueError, match="is not an FSD layer"):
        NEXTJS_LAYOUT.layer_name("processes")


# trace: PRD-APP-210, PRD-APP-303, PRD-APP-304
def test_layer_writers_use_the_layer_names_of_the_layout(portal_ir: Ir) -> None:
    """The Next.js layout moves the files of `app` and `pages` and changes their imports.

    All other paths and all other text are the same as in the React layout.
    """
    react = layer_files(portal_context(portal_ir, REACT_LAYOUT))
    nextjs = layer_files(portal_context(portal_ir, NEXTJS_LAYOUT))
    expected: dict[str, bytes] = {}
    for path, file in react.items():
        for old, new in RENAMED.items():
            if path.startswith(old):
                path = new + path.removeprefix(old)
        content = file.content.decode()
        for old, new in RENAMED_IMPORTS.items():
            content = content.replace(old, new)
        expected[path] = content.encode()
    assert {path: file.content for path, file in nextjs.items()} == expected
    assert any(path.startswith("src/_pages/") for path in nextjs)
    assert any(path.startswith("src/_app/") for path in nextjs)
    assert not any(path.startswith(("src/app/", "src/pages/")) for path in nextjs)
    routes = nextjs["src/_app/router/routes.gen.tsx"].content.decode()
    assert '"@/_pages/order-list"' in routes
    assert '"@/pages/' not in routes


# trace: PRD-APP-305
def test_nextjs_slice_exports_server_only_modules_through_index_server() -> None:
    context = small_context(NEXTJS_LAYOUT)
    files = public_api_files(
        context,
        "src/features/cancel-order",
        ["ui/cancel-order-button.gen"],
        ["Shop::web"],
        ["api/cancel-order.server.gen"],
    )
    by_path = {file.path: file for file in files}
    folder = "web/src/features/cancel-order"
    assert sorted(by_path) == [
        f"{folder}/index.gen.ts",
        f"{folder}/index.server.gen.ts",
        f"{folder}/index.server.ts",
        f"{folder}/index.ts",
    ]
    assert by_path[f"{folder}/index.ts"].kind is Kind.CREATE_ONCE
    assert by_path[f"{folder}/index.server.ts"].kind is Kind.CREATE_ONCE
    assert by_path[f"{folder}/index.server.gen.ts"].kind is Kind.GENERATED
    server = by_path[f"{folder}/index.server.gen.ts"].content.decode()
    assert 'export * from "./api/cancel-order.server.gen";' in server
    assert "ui/cancel-order-button.gen" not in server
    public = by_path[f"{folder}/index.ts"].content.decode()
    assert public.endswith('export * from "./index.gen";\n')
    server_public = by_path[f"{folder}/index.server.ts"].content.decode()
    assert server_public.startswith("// The server-only public API of this slice.")
    assert server_public.endswith('export * from "./index.server.gen";\n')


# trace: PRD-APP-204
def test_slice_with_no_server_only_modules_has_no_index_server() -> None:
    files = public_api_files(
        small_context(NEXTJS_LAYOUT), "src/entities/order", ["model/order.gen"], ["Shop::web"]
    )
    assert [file.path for file in files] == [
        "web/src/entities/order/index.gen.ts",
        "web/src/entities/order/index.ts",
    ]


def test_react_layout_rejects_server_only_modules() -> None:
    with pytest.raises(ValueError, match="no server-only public API"):
        public_api_files(
            small_context(REACT_LAYOUT),
            "src/features/cancel-order",
            ["ui/cancel-order-button.gen"],
            ["Shop::web"],
            ["api/cancel-order.server.gen"],
        )


def test_a_layout_with_an_other_alias_changes_the_import_paths() -> None:
    layout = replace(NEXTJS_LAYOUT, alias="~/")
    assert layout.import_path("pages", "order-list") == "~/_pages/order-list"
    assert layout.import_path("shared", "api") == "~/shared/api"
