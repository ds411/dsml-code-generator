"""Tests of the entity, feature and widget slices of the Next.js generator (story #184).

The golden files in `tests/golden/nextjs/order-web/` hold the slice files of
the order web: `src/entities/`, `src/features/`, `src/widgets/` and the
segments `api`, `lib` and `ui` of `src/shared/`. Write them again with
`uv run python scripts/write_golden_nextjs.py`.

The Vitest tests in `tests/nextjs/features/` and `tests/nextjs/widgets/`
render the forms and the widgets. They examine the requests to the route
handlers under `/api`. The CI job "Next.js golden project" runs them in the
golden project, and runs Steiger on it (PRD-APP-306).
"""

import re
from pathlib import Path

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import parse_configuration
from dsml.generate.generators import collect
from dsml.generate.header import FileType, header
from dsml.generate.nextjs import NextjsGenerator
from dsml.generate.nextjs_slices import API_PREFIX, CLIENT_COMPONENTS, CLIENT_DIRECTIVE
from dsml.generate.react_entities import api_applications, called_applications
from dsml.generate.react_shared import shadcn_files
from dsml.generate.writer import Kind, OutputFile, is_generated_name
from dsml.ir.model import Ir

ROOT = Path(__file__).resolve().parent.parent
WEB_MODEL = ROOT / "docs" / "model" / "examples" / "order-web" / "order-web.sysml"
PORTAL_MODEL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
GOLDEN = ROOT / "tests" / "golden" / "nextjs" / "order-web"
APP = "OrderWeb::orderWeb"

SLICE_PATHS = (
    "src/entities/",
    "src/features/",
    "src/shared/api/",
    "src/shared/lib/",
    "src/shared/ui/",
    "src/widgets/",
)
"""The paths of the files of the slices part in the output folder."""

CLIENT_MODULES = (
    "src/features/cancel-order/ui/cancel-order-form.gen.tsx",
    "src/features/create-order/ui/create-order-form.gen.tsx",
    "src/features/delete-order/ui/delete-order-button.gen.tsx",
    "src/features/update-order/ui/update-order-form.gen.tsx",
    "src/widgets/order-details/ui/order-details.gen.tsx",
    "src/widgets/order-list/ui/order-table.gen.tsx",
)
"""The generated client components of the order web: the forms, the button and the widgets."""

_IMPORT = re.compile(r'from "(@/[^"]+)"')


@pytest.fixture(scope="module")
def web_ir() -> Ir:
    """Make the IR of the order web model one time for the tests of this module."""
    return make_ir([WEB_MODEL], ROOT)


@pytest.fixture(scope="module")
def web_files(web_ir: Ir, tmp_path_factory: pytest.TempPathFactory) -> dict[str, OutputFile]:
    """Give the output of the Next.js generator for the order web, by the path in its folder."""
    folder = tmp_path_factory.mktemp("order-web")
    configuration = parse_configuration(
        'schema = 1\n\n[applications.orderWeb]\noutput = "order-web"\n', folder / "dsml.toml"
    )
    files = collect([NextjsGenerator()], web_ir, configuration, None)
    return {file.path.removeprefix("order-web/"): file for file in files}


def _slice_files(files: dict[str, bytes]) -> dict[str, bytes]:
    """Give the files of the slices part. The server files of a feature belong to story #186."""
    return {
        path: content
        for path, content in files.items()
        if path.startswith(SLICE_PATHS) and ".server" not in path
    }


def _text(path: str) -> str:
    return (GOLDEN / path).read_text(encoding="utf-8")


# trace: PRD-CORE-030, PRD-APP-304, PRD-APP-305
def test_slice_files_of_the_order_web_agree_with_the_golden_files(
    web_files: dict[str, OutputFile],
) -> None:
    output = _slice_files({path: file.content for path, file in web_files.items()})
    golden = _slice_files(
        {
            path.relative_to(GOLDEN).as_posix(): path.read_bytes()
            for path in sorted(GOLDEN.rglob("*"))
            if path.is_file()
        }
    )
    assert output == golden, (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_nextjs.py and examine the differences."
    )
    layers = ("src/entities/", "src/features/", "src/widgets/")
    slices = sorted(path for path in output if path.startswith(layers))
    assert slices == [
        "src/entities/order/api/order-queries.gen.ts",
        "src/entities/order/index.gen.ts",
        "src/entities/order/index.ts",
        "src/entities/order/model/order.gen.ts",
        *(
            f"src/features/{name}/{module}"
            for name, ui in (
                ("cancel-order", "cancel-order-form.gen.tsx"),
                ("create-order", "create-order-form.gen.tsx"),
                ("delete-order", "delete-order-button.gen.tsx"),
                ("update-order", "update-order-form.gen.tsx"),
            )
            for module in (f"api/{name}.gen.ts", "index.gen.ts", "index.ts", f"ui/{ui}")
        ),
        "src/widgets/order-details/index.gen.ts",
        "src/widgets/order-details/index.ts",
        "src/widgets/order-details/ui/order-details.gen.tsx",
        "src/widgets/order-list/index.gen.ts",
        "src/widgets/order-list/index.ts",
        "src/widgets/order-list/ui/order-table.gen.tsx",
    ]
    for path in output:
        file = web_files[path]
        shadcn = path.startswith(("src/shared/lib/", "src/shared/ui/"))
        create_once = path.endswith(("/index.ts", "/index.server.ts")) or (
            shadcn and not path.endswith("/index.gen.ts")
        )
        assert file.kind == (Kind.CREATE_ONCE if create_once else Kind.GENERATED), path
        assert create_once or is_generated_name(path, NextjsGenerator.fixed_names), path


# trace: PRD-APP-305
def test_each_server_only_module_imports_server_only(web_files: dict[str, OutputFile]) -> None:
    """Each server-only module imports `server-only`. Only `index.server.ts` exports it."""
    server_modules = [
        path
        for path in web_files
        if ".server." in path and not path.rsplit("/", 1)[-1].startswith("index.")
    ]
    assert server_modules, "The output has no server-only module."
    for path in server_modules:
        text = web_files[path].content.decode("utf-8")
        assert 'import "server-only";' in text, path
        folder, name = path.rsplit("/", 1)
        module = name.rsplit(".", 1)[0]
        if folder.endswith("/api") and folder.startswith("src/features/"):
            # The server function of a feature slice is in its segment api.
            folder = folder.removesuffix("/api")
            module = f"api/{module}"
        if folder.endswith("/ui") and folder.startswith("src/_pages/"):
            # The page of a page slice is in its segment ui (story #188).
            folder = folder.removesuffix("/ui")
            module = f"ui/{module}"
        server_api = web_files[f"{folder}/index.server.gen.ts"].content.decode("utf-8")
        assert f'export * from "./{module}";' in server_api, path
        public_api = web_files.get(f"{folder}/index.gen.ts")
        if public_api is not None:
            assert module not in public_api.content.decode("utf-8"), path
        assert web_files[f"{folder}/index.server.ts"].kind == Kind.CREATE_ONCE
    for path, file in web_files.items():
        if path.endswith("/index.gen.ts"):
            assert ".server" not in file.content.decode("utf-8"), path
        if path.startswith(SLICE_PATHS) and not path.startswith("src/features/"):
            assert ".server." not in path, "The slices part must have no server-only module."


# trace: PRD-APP-321
def test_forms_and_widgets_are_client_components() -> None:
    for path in CLIENT_MODULES:
        text = _text(path)
        head = header(FileType.TYPESCRIPT, _header_elements(text))
        assert text.startswith(head + '"use client";\n\nimport '), path
    for path in (
        "src/entities/order/model/order.gen.ts",
        "src/entities/order/api/order-queries.gen.ts",
        "src/features/cancel-order/api/cancel-order.gen.ts",
    ):
        assert '"use client"' not in _text(path), path
    form = _text("src/features/cancel-order/ui/cancel-order-form.gen.tsx")
    assert 'import { useForm } from "@tanstack/react-form";' in form
    assert "onSubmit: cancelOrderInputSchema," in form


# trace: PRD-APP-212, PRD-APP-321
def test_shadcn_copy_keeps_the_client_directive() -> None:
    for name, content in shadcn_files("ui").items():
        golden = (GOLDEN / "src/shared/ui" / name).read_bytes()
        if name in CLIENT_COMPONENTS:
            assert golden == CLIENT_DIRECTIVE + content, name
        else:
            assert golden == content, name


# trace: PRD-APP-014, PRD-APP-311, PRD-APP-314, PRD-APP-322
def test_api_client_calls_the_route_handlers_on_the_same_origin() -> None:
    client = _text("src/shared/api/client.gen.ts")
    assert client.startswith(header(FileType.TYPESCRIPT, [APP]))
    for line in (
        f'export const API_PREFIX = "{API_PREFIX}";',
        'export const PROBLEM_MEDIA_TYPE = "application/problem+json";',
        'credentials: "same-origin",',
        "export async function apiRequest(request: ApiRequest): Promise<unknown> {",
    ):
        assert line in client
    assert "Authorization" not in client
    assert "process.env" not in client
    assert "NEXT_PUBLIC_" not in client
    queries = _text("src/entities/order/api/order-queries.gen.ts")
    assert 'import { apiRequest } from "@/shared/api";' in queries


# trace: PRD-APP-203, PRD-APP-303, PRD-APP-306
def test_slices_import_only_lower_layers() -> None:
    allowed = {
        "entities": ("@/shared/",),
        "features": ("@/entities/", "@/shared/"),
        "widgets": ("@/entities/", "@/shared/"),
    }
    for layer, prefixes in allowed.items():
        for path in sorted((GOLDEN / "src" / layer).rglob("*.ts*")):
            text = path.read_text(encoding="utf-8")
            for source in _IMPORT.findall(text):
                assert source.startswith(prefixes), f"{path}: {source}"
                public_api = source.removesuffix("/index.server")
                assert public_api.count("/") == 2, f"{path}: {source} is not a public API"


# trace: PRD-APP-005, PRD-APP-304
def test_a_nextjs_application_uses_its_own_api(web_ir: Ir) -> None:
    application = next(item for item in web_ir.elements if item.identity == APP)
    assert called_applications(web_ir, application) == []
    assert api_applications(web_ir, application) == [application]


# trace: PRD-APP-005
def test_a_react_application_uses_the_called_applications() -> None:
    ir = make_ir([PORTAL_MODEL], ROOT)
    portal = next(item for item in ir.elements if item.identity == "OrderPortal::orderPortal")
    assert api_applications(ir, portal) == called_applications(ir, portal)
    assert [item.identity for item in api_applications(ir, portal)] == ["OrderPortal::orderApi"]


def _header_elements(text: str) -> list[str]:
    line = text.splitlines()[1]
    return line.removeprefix("// Elements: ").split(", ")
