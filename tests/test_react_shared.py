"""Tests of the shared layer of the React generator (story #169).

The golden files in `tests/golden/react/order-portal/src/shared/` are the
shared layer of the order portal model. Write them again with
`uv run python scripts/write_golden_react.py`.

The Vitest file `tests/react/shared/shared.test.ts` examines the behavior of
the generated code in the CI job "React golden project": the runtime
configuration, the configuration of Amplify Auth, the bearer token and the
problem details errors of the API client. The same job builds the project
and makes sure that `dist/` contains no environment value (PRD-APP-233).
"""

import json
import re
from importlib import resources
from pathlib import Path

import pytest

from dsml.config import Configuration, parse_configuration
from dsml.generate.generators import collect
from dsml.generate.header import FileType, header
from dsml.generate.pipelines.deploy import CONFIGURATION_KEYS
from dsml.generate.react import ReactGenerator
from dsml.generate.react_common import ReactContext
from dsml.generate.react_shared import (
    SCOPES,
    SHADCN_FOLDER,
    SHADCN_SEGMENTS,
    shadcn_files,
    shared_files,
)
from dsml.generate.templates import TemplateEngine
from dsml.generate.trace import SymbolKind
from dsml.generate.writer import Kind, application_part, apply_plan, make_plan
from dsml.ir.model import Ir
from dsml.versions import load_baseline

ROOT = Path(__file__).resolve().parent.parent
PORTAL_MODEL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
GOLDEN = ROOT / "tests" / "golden" / "react" / "order-portal"
SHARED = "src/shared/"
VITEST = ROOT / "tests" / "react" / "shared" / "shared.test.ts"
USER_DIRECTORY = (
    ROOT / "src" / "dsml" / "templates" / "infrastructure" / "modules" / "user-directory"
)
CONFIGURATION = '[applications.orderPortal]\noutput = "."\n'
APP = "OrderPortal::orderPortal"
COMPONENTS = [
    "alert-dialog",
    "alert",
    "button",
    "card",
    "field",
    "input",
    "label",
    "native-select",
    "separator",
    "table",
    "textarea",
]


def configuration() -> Configuration:
    return parse_configuration(f"schema = 1\n\n{CONFIGURATION}", Path("dsml.toml"))


@pytest.fixture(scope="module")
def portal_ir() -> Ir:
    from dsml.adapter.convert import make_ir

    return make_ir([PORTAL_MODEL], ROOT)


def context(ir: Ir, folder: str = "") -> ReactContext:
    item = next(element for element in ir.elements if element.name == "orderPortal")
    return ReactContext(
        TemplateEngine(), ir, item, configuration(), folder, application_part(item.name)
    )


def shared(files: dict[str, bytes]) -> dict[str, bytes]:
    return {path: content for path, content in files.items() if path.startswith(SHARED)}


def golden_files() -> dict[str, bytes]:
    return {
        path.relative_to(GOLDEN).as_posix(): path.read_bytes()
        for path in sorted(GOLDEN.rglob("*"))
        if path.is_file()
    }


def golden_text(path: str) -> str:
    return (GOLDEN / path).read_text(encoding="utf-8")


# trace: PRD-CORE-030, PRD-APP-202
def test_shared_files_of_the_order_portal_agree_with_the_golden_files(portal_ir: Ir) -> None:
    files = collect([ReactGenerator()], portal_ir, configuration(), None)
    output = shared({file.path: file.content for file in files})
    assert output == shared(golden_files()), (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_react.py and examine the differences."
    )
    segments = {
        "api": ["client.gen.ts"],
        "auth": ["amplify.gen.ts"],
        "config": ["runtime-config.gen.ts"],
        "lib": ["utils.ts"],
        "ui": [f"{name}.tsx" for name in COMPONENTS],
    }
    expected = [
        f"src/shared/{segment}/{name}"
        for segment, modules in segments.items()
        for name in [*modules, "index.gen.ts", "index.ts"]
    ]
    assert sorted(output) == sorted(expected)


# trace: PRD-APP-204, PRD-APP-212, PRD-CORE-044
def test_shadcn_ui_files_and_public_apis_are_create_once_files(portal_ir: Ir) -> None:
    files = {file.path: file for file in shared_files(context(portal_ir, "web/"))}
    for path, file in files.items():
        name = Path(path).name
        shadcn = path.startswith(("web/src/shared/ui/", "web/src/shared/lib/"))
        create_once = name == "index.ts" or (shadcn and name != "index.gen.ts")
        assert file.kind is (Kind.CREATE_ONCE if create_once else Kind.GENERATED), path
        assert path.startswith("web/src/shared/"), path
    assert files["web/src/shared/ui/button.tsx"].content == shadcn_files("ui")["button.tsx"]
    index = files["web/src/shared/ui/index.gen.ts"].content.decode()
    assert [line for line in index.splitlines() if line.startswith("export")] == [
        f'export * from "./{name}";' for name in sorted(COMPONENTS)
    ]
    assert golden_text("src/shared/api/index.ts").endswith('export * from "./index.gen";\n')


# trace: PRD-APP-212, PRD-CORE-042, PRD-CORE-044
def test_second_run_does_not_change_a_create_once_file(portal_ir: Ir, tmp_path: Path) -> None:
    files = collect([ReactGenerator()], portal_ir, configuration(), None)
    apply_plan(tmp_path, make_plan(tmp_path, files, None))
    button = tmp_path / "src" / "shared" / "ui" / "button.tsx"
    utils = tmp_path / "src" / "shared" / "lib" / "utils.ts"
    assert button.read_bytes() == shadcn_files("ui")["button.tsx"]
    button.write_bytes(b"// The developer changed the button.\n")
    utils.unlink()
    plan = make_plan(tmp_path, files, None)
    assert not plan.conflicts
    assert "src/shared/ui/button.tsx" not in [path for path, _ in plan.writes]
    apply_plan(tmp_path, plan)
    assert button.read_bytes() == b"// The developer changed the button.\n"


# trace: PRD-CORE-048, PRD-APP-212
def test_package_contains_the_pinned_copy_of_shadcn_ui() -> None:
    folder = resources.files("dsml").joinpath(SHADCN_FOLDER)
    assert folder.joinpath("LICENSE.md").read_text(encoding="utf-8").startswith("MIT License")
    assert sorted(shadcn_files("ui")) == [f"{name}.tsx" for name in COMPONENTS]
    assert sorted(shadcn_files("lib")) == ["utils.ts"]
    assert SHADCN_SEGMENTS == ("lib", "ui")
    readme = folder.joinpath("README.md").read_text(encoding="utf-8")
    baseline = load_baseline()
    assert f"`shadcn@{baseline['shadcn-ui'].version}`" in readme
    assert f"`{baseline['shadcn-ui-commit'].value}`" in readme
    for segment in SHADCN_SEGMENTS:
        for name in shadcn_files(segment):
            assert f"| `{segment}/{name}` |" in readme, name


# trace: PRD-APP-201, PRD-APP-212
def test_shadcn_ui_copy_imports_only_packages_of_the_baseline() -> None:
    dependencies = json.loads(golden_text("package.json"))["dependencies"]
    imports: set[str] = set()
    for segment in SHADCN_SEGMENTS:
        for content in shadcn_files(segment).values():
            imports.update(re.findall(r'from "([^"]+)"', content.decode()))
    external = {name for name in imports if not name.startswith(("@/", "./"))}
    assert external <= set(dependencies), external - set(dependencies)
    assert {name for name in imports if name.startswith("@/")} == {"@/shared/lib/utils"}
    # A component imports an other component of the copy with a relative path.
    components = {f"./{name}" for name in COMPONENTS}
    assert {name for name in imports if name.startswith("./")} <= components


# trace: PRD-APP-010, PRD-APP-230
def test_runtime_configuration_has_the_keys_of_the_deployment_pipeline() -> None:
    text = golden_text("src/shared/config/runtime-config.gen.ts")
    assert 'export const RUNTIME_CONFIG_PATH = "/config.json";' in text
    keys = re.findall(r"^  (\w+): z\.", text, flags=re.MULTILINE)
    assert tuple(keys) == CONFIGURATION_KEYS
    assert 'fetch(RUNTIME_CONFIG_PATH, { cache: "no-store" })' in text


# trace: PRD-APP-007, PRD-APP-231
def test_amplify_auth_uses_the_values_of_the_app_client() -> None:
    text = golden_text("src/shared/auth/amplify.gen.ts")
    assert 'responseType: "code"' in text
    assert 'export const CALLBACK_PATH = "/auth/callback";' in text
    assert 'export const LOGOUT_PATH = "/";' in text
    scopes = ", ".join(f'"{scope}"' for scope in SCOPES)
    assert f"export const SCOPES = [{scopes}];" in text
    # The app client of the user directory permits the same scopes.
    infrastructure = (USER_DIRECTORY / "main.gen.tf.j2").read_text(encoding="utf-8")
    assert re.search(rf"allowed_oauth_scopes\s+= \[{re.escape(scopes)}\]", infrastructure)
    assert "userPoolClientId: config.appClientId" in text


# trace: PRD-APP-014, PRD-APP-227, PRD-APP-232
def test_api_client_sends_the_bearer_token_and_reads_problem_details() -> None:
    text = golden_text("src/shared/api/client.gen.ts")
    assert 'export const PROBLEM_MEDIA_TYPE = "application/problem+json";' in text
    assert 'headers.set("Authorization", `Bearer ${token}`);' in text
    assert "export async function apiRequest(request: ApiRequest): Promise<unknown> {" in text
    # The Vitest tests examine the behavior in the CI job "React golden project".
    vitest = VITEST.read_text(encoding="utf-8")
    assert '"Bearer the-access-token"' in vitest
    assert 'message: "Not Found: The order 5 does not exist."' in vitest


# trace: PRD-APP-011, PRD-APP-233
def test_shared_files_contain_no_environment_value(portal_ir: Ir) -> None:
    for file in shared_files(context(portal_ir)):
        text = file.content.decode()
        for value in ("import.meta.env", "process.env", "VITE_", "amazoncognito.com"):
            assert value not in text, (file.path, value)
        assert not re.search(r"[a-z]{2}-[a-z]+-\d_[A-Za-z0-9]+", text), file.path


# trace: PRD-APP-017, PRD-TRACE-005, PRD-TRACE-006
def test_generated_shared_files_have_the_header_and_symbols(portal_ir: Ir) -> None:
    files = {file.path: file for file in shared_files(context(portal_ir))}
    for path, file in files.items():
        if file.kind is Kind.GENERATED:
            assert file.content.decode().startswith(header(FileType.TYPESCRIPT, [APP])), path
        else:
            assert not file.content.startswith(b"// Generated"), path
    symbols = {symbol.name: symbol.kind for symbol in files["src/shared/api/client.gen.ts"].symbols}
    assert symbols["apiRequest"] is SymbolKind.FUNCTION
    assert symbols["ApiError"] is SymbolKind.CLASS
    config = {symbol.name for symbol in files["src/shared/config/runtime-config.gen.ts"].symbols}
    assert {"loadRuntimeConfig", "runtimeConfig", "runtimeConfigSchema"} <= config
    auth = {symbol.name for symbol in files["src/shared/auth/amplify.gen.ts"].symbols}
    assert {"configureAuth", "currentSession", "accessToken", "startLogin", "logout"} <= auth
