"""Tests of the authentication of the Next.js generator (story #183).

The golden files in `tests/golden/nextjs/order-web/` hold the auth files of
the order web: `src/shared/auth/`, `app/auth/` and `proxy.ts`. Write them
again with `uv run python scripts/write_golden_nextjs.py`.

The Vitest tests in `tests/nextjs/auth/` examine the role check, the server
helper `authorize` with test tokens and the redirect of the request
interceptor. The CI job "Next.js golden project" runs them in the golden
project, and gets a protected page from the container with no session.
"""

from pathlib import Path

import pytest

from dsml.adapter.convert import build_ir, make_ir
from dsml.adapter.engine import Engine
from dsml.config import parse_configuration
from dsml.errors import ToolchainError
from dsml.generate.generators import collect
from dsml.generate.header import FileType, header
from dsml.generate.infrastructure.modules import CALLBACK_PATH, LOGOUT_PATH
from dsml.generate.nextjs import FIXED_NAMES, NextjsGenerator
from dsml.generate.nextjs_auth import LOGIN_PATH, PROXY
from dsml.generate.writer import Kind, OutputFile, is_generated_name
from dsml.ir.model import Ir
from dsml.library import library_document

ROOT = Path(__file__).resolve().parent.parent
WEB_MODEL = ROOT / "docs" / "model" / "examples" / "order-web" / "order-web.sysml"
GOLDEN = ROOT / "tests" / "golden" / "nextjs" / "order-web"
APP = "OrderWeb::orderWeb"

AUTH_PATHS = ("app/auth/", "proxy.ts", "src/shared/auth/")
"""The paths of the files of the auth part in the output folder."""

MODEL = """package Shop {
    private import DSML::*;
    private import ScalarValues::*;
    @DsmlVersion { major = 1; minor = 1; }
    #Roles enum def ShopRoles { clerk; }
    #Entity part def Order { #Key attribute id : Uuid [1]; }
    #Entity part def Product {
        #Key attribute code : String [1] { @FieldRules { maxLength = 20; } }
    }
    #Application part shopWeb {
        :>> target = Target::nextjs;
        #Exposed part orders : Order [*] {
            :>> crud = (CrudKind::read, CrudKind::list);
            :>> allowedRoles = (ShopRoles::clerk);
        }
        #Exposed part catalogItems : Product [*] {
            :>> crud = (CrudKind::read, CrudKind::list);
            :>> public = true;
        }
        #View part orderList {
            :>> kind = ViewKind::list;
            ref :>> entity : Order;
            ORDER_LIST_ACCESS
        }
        #View part productList {
            :>> kind = ViewKind::list;
            ref :>> entity : Product;
            :>> public = true;
        }
        #View part productDetail {
            :>> kind = ViewKind::detail;
            ref :>> entity : Product;
            :>> public = true;
        }
    }
}
"""
"""A model with two public views. The access of the view `orderList` is a parameter."""


@pytest.fixture(scope="module")
def web_ir() -> Ir:
    """Make the IR of the order web model one time for the tests of this module."""
    return make_ir([WEB_MODEL], ROOT)


def _auth_files(files: dict[str, bytes]) -> dict[str, bytes]:
    return {path: content for path, content in files.items() if path.startswith(AUTH_PATHS)}


def _generate(ir: Ir, tmp_path: Path, name: str, output: str) -> dict[str, OutputFile]:
    configuration = parse_configuration(
        f'schema = 1\n\n[applications.{name}]\noutput = "{output}"\n', tmp_path / "dsml.toml"
    )
    files = collect([NextjsGenerator()], ir, configuration, None)
    return {file.path.removeprefix(f"{output}/"): file for file in files}


def _shop(engine: Engine, protected: bool) -> Ir:
    access = ":>> allowedRoles = (ShopRoles::clerk);" if protected else ":>> public = true;"
    text = MODEL.replace("ORDER_LIST_ACCESS", access)
    parsed = engine.parse_texts([library_document(), ("shop.sysml", text)])
    assert [str(item) for item in parsed.diagnostics] == []
    return build_ir(parsed, ["shop.sysml"])


# trace: PRD-CORE-030, PRD-APP-322, PRD-APP-323, PRD-APP-324
def test_auth_files_of_the_order_web_agree_with_the_golden_files(
    web_ir: Ir, tmp_path: Path
) -> None:
    files = _generate(web_ir, tmp_path, "orderWeb", "order-web")
    output = _auth_files({path: file.content for path, file in files.items()})
    golden = _auth_files(
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
    assert sorted(output) == [
        "app/auth/callback/page.tsx",
        "app/auth/login/page.tsx",
        "proxy.ts",
        "src/shared/auth/access.gen.ts",
        "src/shared/auth/amplify.gen.ts",
        "src/shared/auth/callback-page.gen.tsx",
        "src/shared/auth/index.gen.ts",
        "src/shared/auth/index.server.gen.ts",
        "src/shared/auth/index.server.ts",
        "src/shared/auth/index.ts",
        "src/shared/auth/login-page.gen.tsx",
        "src/shared/auth/session.server.gen.ts",
    ]
    for path, file in files.items():
        if path.startswith(AUTH_PATHS):
            create_once = path.endswith(("/index.ts", "/index.server.ts"))
            assert file.kind == (Kind.CREATE_ONCE if create_once else Kind.GENERATED)
            assert create_once or is_generated_name(path, NextjsGenerator.fixed_names), path


# trace: PRD-APP-007, PRD-APP-322, PRD-APP-302
def test_amplify_uses_managed_login_with_pkce_and_cookies() -> None:
    amplify = (GOLDEN / "src/shared/auth/amplify.gen.ts").read_text(encoding="utf-8")
    assert amplify.startswith(header(FileType.TYPESCRIPT, [APP]))
    for line in (
        f'export const CALLBACK_PATH = "{CALLBACK_PATH}";',
        f'export const LOGOUT_PATH = "{LOGOUT_PATH}";',
        f'export const LOGIN_PATH = "{LOGIN_PATH}";',
        'export const SCOPES = ["email", "openid", "profile"];',
        'responseType: "code",',
        "{ ssr: true },",
    ):
        assert line in amplify
    login = (GOLDEN / "app/auth/login/page.tsx").read_text(encoding="utf-8")
    assert login.endswith('export { LoginPage as default } from "@/shared/auth";\n')
    callback = (GOLDEN / "app/auth/callback/page.tsx").read_text(encoding="utf-8")
    assert callback.endswith('export { CallbackPage as default } from "@/shared/auth";\n')


# trace: PRD-APP-008, PRD-APP-011, PRD-APP-305, PRD-APP-324
def test_session_helper_is_server_only_and_uses_the_adapter() -> None:
    session = (GOLDEN / "src/shared/auth/session.server.gen.ts").read_text(encoding="utf-8")
    for line in (
        'import "server-only";',
        'import { createServerRunner } from "@aws-amplify/adapter-nextjs";',
        'import { fetchAuthSession } from "aws-amplify/auth/server";',
        'import { readPublicConfig } from "@/shared/config/index.server";',
        '{ status, headers: { "Content-Type": "application/problem+json" } },',
        "export async function authorize(access: Access): Promise<Authorization> {",
    ):
        assert line in session
    server_api = (GOLDEN / "src/shared/auth/index.server.gen.ts").read_text(encoding="utf-8")
    assert server_api.endswith('export * from "./session.server.gen";\n')
    public_api = (GOLDEN / "src/shared/auth/index.gen.ts").read_text(encoding="utf-8")
    assert "session.server" not in public_api
    for path in sorted((GOLDEN / "src/shared/auth").iterdir()):
        text = path.read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_" not in text
        assert "process.env" not in text


# trace: PRD-APP-323, PRD-TRACE-005
def test_proxy_matches_the_protected_views_of_the_order_web() -> None:
    proxy = (GOLDEN / PROXY).read_text(encoding="utf-8")
    views = [f"{APP}::cancelOrderForm", f"{APP}::orderDetail", f"{APP}::orderList"]
    assert proxy.startswith(header(FileType.TYPESCRIPT, [APP, *views]))
    assert 'matcher: ["/cancel-order", "/orders", "/orders/:id"],' in proxy
    assert "export function proxy(request: NextRequest)" in proxy
    assert PROXY in FIXED_NAMES


# trace: PRD-APP-008, PRD-APP-323
def test_proxy_does_not_match_a_public_view(rule_engine: Engine, tmp_path: Path) -> None:
    files = _generate(_shop(rule_engine, protected=True), tmp_path, "shopWeb", "web")
    proxy = files[PROXY].content.decode("utf-8")
    assert 'matcher: ["/orders"],' in proxy
    assert proxy.startswith(
        header(FileType.TYPESCRIPT, ["Shop::shopWeb", "Shop::shopWeb::orderList"])
    )


# trace: PRD-APP-323
def test_no_proxy_if_each_view_is_public(rule_engine: Engine, tmp_path: Path) -> None:
    files = _generate(_shop(rule_engine, protected=False), tmp_path, "shopWeb", "web")
    assert PROXY not in files
    assert "src/shared/auth/session.server.gen.ts" in files


def test_view_of_an_entity_that_the_application_does_not_expose_is_an_error(
    rule_engine: Engine, tmp_path: Path
) -> None:
    text = MODEL.replace("ORDER_LIST_ACCESS", ":>> allowedRoles = (ShopRoles::clerk);")
    text = text.replace(
        "#Exposed part orders : Order [*] {", "#Exposed part orders : Product [*] {"
    ).replace("#Exposed part catalogItems : Product [*] {", "#Exposed part catalog : Product [*] {")
    parsed = rule_engine.parse_texts([library_document(), ("shop.sysml", text)])
    ir = build_ir(parsed, ["shop.sysml"])
    with pytest.raises(ToolchainError, match="The view orderList of the application shopWeb"):
        _generate(ir, tmp_path, "shopWeb", "web")
