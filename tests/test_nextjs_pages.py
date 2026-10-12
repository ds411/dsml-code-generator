"""Tests of the pages and navigation of the Next.js generator (story #188).

The golden files in `tests/golden/nextjs/order-web/` hold the page files of
the order web: `src/_pages/`, the route files of the pages in `app/`, the
layout files and the providers in `src/_app/`, and `src/shared/access/`.
Write them again with `uv run python scripts/write_golden_nextjs.py`.

The Vitest tests in `tests/nextjs/pages/` render the pages and the
navigation. The CI job "Next.js golden project" runs them.
"""

from pathlib import Path

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import parse_configuration
from dsml.errors import ToolchainError
from dsml.generate.generators import collect
from dsml.generate.nextjs import NextjsGenerator
from dsml.generate.writer import Kind, OutputFile
from dsml.ir.model import Ir

ROOT = Path(__file__).resolve().parent.parent
WEB_MODEL = ROOT / "docs" / "model" / "examples" / "order-web" / "order-web.sysml"
GOLDEN = ROOT / "tests" / "golden" / "nextjs" / "order-web"
CONFIGURATION = 'schema = 1\n\n[applications.orderWeb]\noutput = "order-web"\n'

APP_FILES = (
    "src/_app/layout/app-layout.gen.tsx",
    "src/_app/layout/logout-button.gen.tsx",
    "src/_app/layout/navigation.gen.tsx",
    "src/_app/layout/status-pages.gen.tsx",
    "src/_app/providers/",
    "src/_app/styles/",
    "src/_pages/",
    "src/shared/access/",
)
"""The files of the pages part in `src/`."""

ROUTES = {
    "app/cancel-order/page.tsx": "@/_pages/cancel-order-form/index.server",
    "app/orders/[id]/page.tsx": "@/_pages/order-detail/index.server",
    "app/orders/page.tsx": "@/_pages/order-list/index.server",
}
"""The route file of each view of the order web and the module that it re-exports."""


def page_file(path: str) -> bool:
    """Tell if a path in the output folder is a file of the pages part."""
    if path.startswith("app/") and path.rsplit("/", 1)[-1] in ("page.tsx", "not-found.tsx"):
        return not path.startswith("app/auth/")
    return path.startswith(APP_FILES)


def generate(text: str, folder: Path) -> dict[str, OutputFile]:
    """Give the output of the Next.js generator for a model text, by the path in its folder."""
    model = folder / "order-web.sysml"
    model.write_text(text, encoding="utf-8")
    configuration = parse_configuration(CONFIGURATION, folder / "dsml.toml")
    files = collect([NextjsGenerator()], make_ir([model], folder), configuration, None)
    return {file.path.removeprefix("order-web/"): file for file in files}


@pytest.fixture(scope="module")
def web_ir() -> Ir:
    return make_ir([WEB_MODEL], ROOT)


@pytest.fixture(scope="module")
def web_files(web_ir: Ir, tmp_path_factory: pytest.TempPathFactory) -> dict[str, OutputFile]:
    """Give the output of the Next.js generator for the order web, by the path in its folder."""
    folder = tmp_path_factory.mktemp("order-web")
    configuration = parse_configuration(CONFIGURATION, folder / "dsml.toml")
    files = collect([NextjsGenerator()], web_ir, configuration, None)
    return {file.path.removeprefix("order-web/"): file for file in files}


def text_of(files: dict[str, OutputFile], path: str) -> str:
    return files[path].content.decode("utf-8")


# trace: PRD-APP-320, PRD-CORE-030
def test_page_files_of_the_order_web_agree_with_the_golden_files(
    web_files: dict[str, OutputFile],
) -> None:
    output = {path: file.content for path, file in web_files.items() if page_file(path)}
    golden = {
        path.relative_to(GOLDEN).as_posix(): path.read_bytes()
        for path in sorted(GOLDEN.rglob("*"))
        if path.is_file() and page_file(path.relative_to(GOLDEN).as_posix())
    }
    assert output == golden, (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_nextjs.py and examine the differences."
    )


# trace: PRD-APP-221, PRD-APP-302, PRD-APP-305, PRD-APP-320
def test_each_view_has_a_page_slice_and_a_route_file(web_files: dict[str, OutputFile]) -> None:
    for route, source in ROUTES.items():
        assert f'as default }} from "{source}";' in text_of(web_files, route), route
    slices = sorted({path.split("/")[2] for path in web_files if path.startswith("src/_pages/")})
    assert slices == ["cancel-order-form", "order-detail", "order-list"]
    for name in slices:
        api = text_of(web_files, f"src/_pages/{name}/index.server.gen.ts")
        assert api.endswith(f'export * from "./ui/{name}-page.server.gen";\n'), name
        assert web_files[f"src/_pages/{name}/index.server.ts"].kind == Kind.CREATE_ONCE
        assert f"src/_pages/{name}/index.ts" not in web_files, name
    assert text_of(web_files, "app/page.tsx").endswith(
        'export { HomePage as default } from "@/_app/layout/status-pages.gen";\n'
    )


# trace: PRD-APP-314, PRD-APP-321
def test_list_and_detail_pages_call_the_server_functions(web_files: dict[str, OutputFile]) -> None:
    pages = "src/_pages"
    listing = text_of(web_files, f"{pages}/order-list/ui/order-list-page.server.gen.tsx")
    assert 'import { handleListOrder } from "@/features/list-order/index.server";' in listing
    assert "handleListOrder(queryKey[2].limit, queryKey[2].offset)" in listing
    assert "<HydrationBoundary state={dehydrate(queryClient)}>" in listing
    detail = text_of(web_files, f"{pages}/order-detail/ui/order-detail-page.server.gen.tsx")
    assert "queryFn: () => handleReadOrder(key)," in detail
    assert "const key = id;" in detail
    for path, file in web_files.items():
        text = file.content.decode("utf-8")
        if path.startswith(f"{pages}/") and path.endswith("-content.gen.tsx"):
            assert '"use client";' in text, path
            assert ".server" not in text, path
        if path.startswith(f"{pages}/") and path.endswith(".server.gen.tsx"):
            assert '"use client"' not in text, path
            assert "apiRequest" not in text, path


# trace: PRD-APP-009, PRD-APP-324, PRD-DSML-033
def test_each_page_checks_the_roles_of_its_view(web_files: dict[str, OutputFile]) -> None:
    for name, roles in (
        ("cancel-order-form", '["admin"]'),
        ("order-detail", '["admin", "clerk"]'),
        ("order-list", '["admin", "clerk"]'),
    ):
        text = text_of(web_files, f"src/_pages/{name}/ui/{name}-page.server.gen.tsx")
        assert f"  public: false,\n  roles: {roles},\n" in text, name
        assert "return <NotPermittedPage />;" in text, name
    access = text_of(web_files, "src/shared/access/view-access.server.gen.ts")
    assert 'import "server-only";' in access
    assert "redirect(`${LOGIN_PATH}?${query.toString()}`);" in access


# trace: PRD-APP-009, PRD-DSML-032
def test_navigation_has_the_views_of_the_model(web_files: dict[str, OutputFile]) -> None:
    text = text_of(web_files, "src/_app/layout/navigation.gen.tsx")
    assert (
        "export const NAVIGATION: readonly NavigationView[] = [\n"
        "  {\n"
        '    path: "/orders",\n'
        '    title: "Order list",\n'
        "    public: false,\n"
        '    roles: ["admin", "clerk"],\n'
        "  },\n"
        "];\n"
    ) in text
    assert "checkAccess(session, view) === 200" in text
    layout = text_of(web_files, "src/_app/layout/root-layout.gen.tsx")
    assert "<AppLayout>{children}</AppLayout>" in layout
    assert 'import "../styles/index.css";' in layout
    assert web_files["src/_app/styles/index.css"].kind == Kind.CREATE_ONCE


# trace: PRD-APP-221, PRD-APP-314
def test_detail_page_of_an_integer_key_gives_a_number(tmp_path: Path) -> None:
    text = WEB_MODEL.read_text(encoding="utf-8")
    text = text.replace("#Key attribute id : Uuid [1];", "#Key attribute id : Integer [1];")
    text = text.replace("in orderId : Uuid;", "in orderId : Integer;")
    text = text.replace("CrudKind::create, ", "")
    files = generate(text, tmp_path)
    detail = text_of(files, "src/_pages/order-detail/ui/order-detail-page.server.gen.tsx")
    assert "const key = Number(id);" in detail
    assert "<OrderDetails id={key} />" in detail


# trace: PRD-APP-009, PRD-DSML-033
def test_public_view_needs_no_session(tmp_path: Path) -> None:
    text = WEB_MODEL.read_text(encoding="utf-8").replace(
        "doc /* The list of the orders. */",
        "doc /* The list of the orders. */\n            :>> public = true;",
    )
    files = generate(text, tmp_path)
    listing = text_of(files, "src/_pages/order-list/ui/order-list-page.server.gen.tsx")
    assert "  public: true,\n" in listing
    navigation = text_of(files, "src/_app/layout/navigation.gen.tsx")
    assert "    public: true,\n" in navigation


def test_navigation_must_not_contain_a_detail_view(tmp_path: Path) -> None:
    text = WEB_MODEL.read_text(encoding="utf-8").replace(
        ":>> navigation = (orderList);", ":>> navigation = (orderList, orderDetail);"
    )
    with pytest.raises(ToolchainError, match="contains the detail view orderDetail"):
        generate(text, tmp_path)


# trace: PRD-APP-221, PRD-APP-302
def test_route_of_a_view_must_not_use_the_segment_of_an_other_part(tmp_path: Path) -> None:
    text = WEB_MODEL.read_text(encoding="utf-8")
    text = text.replace("#Exposed action cancelOrder :", "#Exposed action api :")
    with pytest.raises(ToolchainError, match=r'The first segment "/api"'):
        generate(text, tmp_path)
