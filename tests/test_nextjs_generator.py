"""Tests of the Next.js generator: project files and generator frame (story #180).

The golden files in `tests/golden/nextjs/order-web/` are the output of the
Next.js generator for the order web model. The folder is the project folder
of the application orderWeb. The configuration of the tests is in the parent
folder, with the output folder `order-web`. Write the files again with
`uv run python scripts/write_golden_nextjs.py`. The CI job "Next.js golden
project" runs Prettier, tsc, ESLint, Steiger, Vitest, `next build` and
`docker build` on the golden project.

The test of the golden files compares only the project files. The test of
each part story compares the files of its part. The phase 3 exit story
(#189) adds the manifests in `.dsml/`.
"""

import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from dsml.config import Configuration, parse_configuration
from dsml.errors import ToolchainError
from dsml.generate import generators, nextjs
from dsml.generate.generators import collect
from dsml.generate.header import FileType, file_type_of, header
from dsml.generate.nextjs import (
    FIXED_NAMES,
    PART_FUNCTIONS,
    PUBLIC_CONFIG_VARIABLES,
    NextjsGenerator,
    applications,
)
from dsml.generate.react import dependencies
from dsml.generate.react_common import NEXTJS_LAYOUT, ReactContext
from dsml.generate.react_shared import SHADCN_SEGMENTS, shadcn_files
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import LOCKFILES, Kind, OutputFile, application_part, is_generated_name
from dsml.ir.model import Attribute, Element, EnumValue, Ir, Location
from dsml.versions import load_baseline, pinned_version

ROOT = Path(__file__).resolve().parent.parent
WEB_MODEL = ROOT / "docs" / "model" / "examples" / "order-web" / "order-web.sysml"
GOLDEN = ROOT / "tests" / "golden" / "nextjs" / "order-web"
APP = "OrderWeb::orderWeb"
PROJECT_FILES = [
    ".dockerignore",
    "Dockerfile",
    "app/healthz/route.ts",
    "app/layout.tsx",
    "components.json",
    "drizzle.config.ts",
    "eslint.config.js",
    "next.config.ts",
    "package.json",
    "src/_app/api-routes/healthz.gen.ts",
    "src/_app/layout/root-layout.gen.tsx",
    "src/shared/config/index.gen.ts",
    "src/shared/config/index.server.gen.ts",
    "src/shared/config/index.server.ts",
    "src/shared/config/index.ts",
    "src/shared/config/public-config.gen.tsx",
    "src/shared/config/public-config.server.gen.ts",
    "src/shared/log/index.gen.ts",
    "src/shared/log/index.server.gen.ts",
    "src/shared/log/index.server.ts",
    "src/shared/log/index.ts",
    "src/shared/log/logger.server.gen.ts",
    "src/shared/log/request-id.gen.ts",
    "steiger.config.ts",
    "tsconfig.json",
    "vitest.config.ts",
]
CONFIGURATION = '[applications.orderWeb]\noutput = "order-web"\n'
OUTPUT = "order-web/"
"""The output folder of the order web. The tests compare the paths in this folder."""
DATABASE_FILES = [
    ".dsml/schema-snapshot.json",
    "migrate.gen.mjs",
    "migrations/meta/_journal.json",
    "src/shared/db/client.server.gen.ts",
    "src/shared/db/index.gen.ts",
    "src/shared/db/index.server.gen.ts",
    "src/shared/db/index.server.ts",
    "src/shared/db/index.ts",
    "src/shared/db/schema.gen.ts",
    "standalone-migrate.gen.mjs",
]
"""The files of the database part (story #182) for an application with no entity."""

AUTH_FILES = [
    "app/auth/callback/page.tsx",
    "app/auth/login/page.tsx",
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
"""The files of the auth part (story #183) for an application with no view.

With no view that needs a session, the generator writes no `proxy.ts`.
"""

SLICE_FILES = [
    "src/shared/api/client.gen.ts",
    "src/shared/api/index.gen.ts",
    "src/shared/api/index.ts",
    *(
        f"src/shared/{segment}/{name}"
        for segment in SHADCN_SEGMENTS
        for name in [*shadcn_files(segment), "index.gen.ts", "index.ts"]
    ),
]
"""The files of the slices part (story #184) for an application with no entity and no view."""

PART_FOLDERS = (
    "app/api/",
    "app/auth/",
    "migrate.gen.mjs",
    "migrations/",
    "proxy.ts",
    "src/_app/api-routes/",
    "src/_app/providers/",
    "src/_pages/",
    "src/entities/",
    "src/features/",
    "src/shared/api/",
    "src/shared/auth/",
    "src/shared/db/",
    "src/shared/lib/",
    "src/shared/ui/",
    "src/widgets/",
    "standalone-migrate.gen.mjs",
)
"""The paths of the files of the part stories. The test of each part story tests them."""


def configuration(text: str = CONFIGURATION) -> Configuration:
    return parse_configuration(f"schema = 1\n\n{text}", Path("dsml.toml"))


def part_file(path: str) -> bool:
    """Tell if a path is a file of a part story or a manifest in `.dsml/`."""
    if path == "src/_app/api-routes/healthz.gen.ts":
        return False
    return path.startswith((*PART_FOLDERS, ".dsml/"))


def project_files(files: dict[str, bytes]) -> dict[str, bytes]:
    return {path: content for path, content in files.items() if not part_file(path)}


def output_files(files: Sequence[OutputFile]) -> dict[str, bytes]:
    """Give the content of each output file by its path in the output folder of the order web."""
    return {file.path.removeprefix(OUTPUT): file.content for file in files}


def golden_files() -> dict[str, bytes]:
    return {
        path.relative_to(GOLDEN).as_posix(): path.read_bytes()
        for path in sorted(GOLDEN.rglob("*"))
        if path.is_file()
    }


def golden_text(path: str) -> str:
    return (GOLDEN / path).read_text(encoding="utf-8")


def application(name: str = "orderWeb", target: str = "nextjs") -> Element:
    location = Location(file="model.sysml", line=1, column=1)
    return Element(
        identity=f"Shop::{name}",
        kind="Application",
        name=name,
        qualified_name=f"Shop::{name}",
        location=location,
        attributes=(Attribute("target", EnumValue("DSML::Target", target), location),),
    )


def small_ir(*elements: Element) -> Ir:
    return Ir(elements=elements)


@pytest.fixture(scope="module")
def web_ir() -> Ir:
    """Make the IR of the order web model one time for the tests of this module."""
    from dsml.adapter.convert import make_ir

    return make_ir([WEB_MODEL], ROOT)


# trace: PRD-CORE-030, PRD-APP-002, PRD-APP-334
def test_project_files_of_the_order_web_agree_with_the_golden_files(web_ir: Ir) -> None:
    files = collect([NextjsGenerator()], web_ir, configuration(), None)
    output = project_files(output_files(files))
    assert output == project_files(golden_files()), (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_nextjs.py and examine the differences."
    )
    assert sorted(output) == PROJECT_FILES


# trace: PRD-CORE-028
def test_output_is_the_same_at_each_run(web_ir: Ir) -> None:
    first = collect([NextjsGenerator()], web_ir, configuration(), None)
    second = collect([NextjsGenerator()], web_ir, configuration(), None)
    assert first == second


def test_nextjs_generator_is_in_the_list_of_generators() -> None:
    assert any(isinstance(generator, NextjsGenerator) for generator in generators.GENERATORS)


# trace: PRD-APP-001
def test_generator_selects_only_the_applications_with_the_target_nextjs(web_ir: Ir) -> None:
    assert [element.identity for element in applications(web_ir)] == [APP]
    ir = small_ir(application("orderApi", "fastapi"), application("portal", "react"))
    assert applications(ir) == []
    assert NextjsGenerator().generate(ir, configuration(""), None) == []


# trace: PRD-APP-334, PRD-CORE-036, PRD-CORE-039
def test_fixed_names_and_no_lockfile(web_ir: Ir) -> None:
    assert set(FIXED_NAMES) == {
        "package.json",
        "tsconfig.json",
        "next.config.ts",
        "app/",
        "middleware.ts",
        "proxy.ts",
        "drizzle.config.ts",
        "components.json",
        "steiger.config.ts",
        "eslint.config.js",
        "vitest.config.ts",
        "migrations/meta/_journal.json",
        "Dockerfile",
        ".dockerignore",
    }
    files = collect([NextjsGenerator()], web_ir, configuration(), None)
    # Only the public API index.ts and index.server.ts of a segment, and the
    # shadcn/ui copy, are create-once files (PRD-APP-204, PRD-APP-212,
    # PRD-APP-305).
    assert all(
        file.kind is Kind.GENERATED
        or Path(file.path).name in ("index.ts", "index.server.ts")
        or file.path.startswith(("order-web/src/shared/lib/", "order-web/src/shared/ui/"))
        for file in files
    )
    assert not [file.path for file in files if Path(file.path).name in LOCKFILES]
    # The only file in .dsml/ is the schema snapshot. The phase 3 exit story
    # (#189) adds the manifests.
    assert [path for path in output_files(files) if path.startswith(".dsml/")] == [
        ".dsml/schema-snapshot.json"
    ]


# trace: PRD-APP-302, PRD-CORE-039
def test_files_in_the_app_folder_are_fixed_name_files() -> None:
    assert is_generated_name("app/layout.tsx", FIXED_NAMES)
    assert is_generated_name("app/orders/[id]/page.tsx", FIXED_NAMES)
    assert is_generated_name("apps/web/app/healthz/route.ts", FIXED_NAMES)
    assert not is_generated_name("src/_app/layout/root-layout.tsx", FIXED_NAMES)


# trace: PRD-APP-302
def test_route_files_only_re_export_from_src() -> None:
    routes = [path for path in project_files(golden_files()) if path.startswith("app/")]
    assert routes == ["app/healthz/route.ts", "app/layout.tsx"]
    for path in routes:
        lines = golden_text(path).removeprefix(header(FileType.TYPESCRIPT, [APP])).splitlines()
        assert lines, path
        for line in lines:
            assert re.fullmatch(r'export \{ [^}]+ \} from "@/_app/[^"]+";', line), line


# trace: PRD-APP-303
def test_layers_app_and_pages_have_the_names_of_next_js(web_ir: Ir) -> None:
    files = collect([NextjsGenerator()], web_ir, configuration(), None)
    paths = list(output_files(files))
    assert not [path for path in paths if path.startswith(("src/app/", "src/pages/"))]
    assert "src/_app/layout/root-layout.gen.tsx" in paths


# trace: PRD-APP-017, PRD-TRACE-005
def test_each_typescript_and_javascript_file_has_the_trace_header() -> None:
    for path, content in project_files(golden_files()).items():
        file_type = file_type_of(path)
        if Path(path).name in ("index.ts", "index.server.ts"):
            assert not content.startswith(b"// Generated"), path
        elif file_type in (
            FileType.TYPESCRIPT,
            FileType.JAVASCRIPT,
            FileType.DOCKERFILE,
            FileType.IGNORE,
        ):
            assert content.decode().startswith(header(file_type, [APP])), path
        else:
            assert not content.startswith(b"// Generated"), path


# trace: PRD-APP-301, PRD-TOP-008, PRD-CORE-046
def test_package_json_pins_the_versions_of_the_baseline() -> None:
    package = json.loads(golden_text("package.json"))
    pinned = {**package["dependencies"], **package["devDependencies"]}
    items = {**nextjs.RUNTIME_PACKAGES, **nextjs.DEV_PACKAGES}
    assert set(pinned) == set(items)
    for name, version in pinned.items():
        assert version == pinned_version(items[name]), name
    for key in ("dependencies", "devDependencies"):
        assert list(package[key]) == sorted(package[key]), key
    assert package["packageManager"] == f"pnpm@{pinned_version('pnpm')}"
    assert package["devEngines"]["runtime"]["version"] == pinned_version("node")
    assert package["type"] == "module"
    assert package["scripts"]["build"] == "next build"
    assert package["postcss"] == {"plugins": {"@tailwindcss/postcss": {}}}


# trace: PRD-APP-301
@pytest.mark.parametrize(
    "package",
    [
        "next",
        "react",
        "@tanstack/react-query",
        "@tanstack/react-form",
        "zod",
        "tailwindcss",
        "drizzle-orm",
        "pg",
        "aws-amplify",
        "@aws-amplify/adapter-nextjs",
        "typescript",
        "eslint",
        "typescript-eslint",
        "vitest",
        "steiger",
    ],
)
def test_package_json_has_the_stack_of_the_target(package: str) -> None:
    data = json.loads(golden_text("package.json"))
    assert package in {**data["dependencies"], **data["devDependencies"]}


# trace: PRD-APP-301, PRD-APP-303
def test_tsconfig_is_strict_and_gives_the_path_alias() -> None:
    options = json.loads(golden_text("tsconfig.json"))["compilerOptions"]
    assert options["strict"] is True
    assert options["paths"] == {"@/*": ["./src/*"]}
    assert 'alias: [{ find: /^@\\//, replacement: "/src/" }]' in golden_text("vitest.config.ts")


# trace: PRD-APP-333
def test_build_uses_the_standalone_output() -> None:
    assert 'output: "standalone",' in golden_text("next.config.ts")
    dockerfile = golden_text("Dockerfile")
    assert "COPY --from=build /srv/.next/standalone ./" in dockerfile
    assert "EXPOSE 3000\n" in dockerfile
    assert "PORT=3000" in dockerfile
    assert dockerfile.endswith('CMD ["node", "server.js"]\n')


# trace: PRD-APP-013
def test_dockerfile_is_multi_stage_with_a_pinned_image_and_a_user_that_is_not_root() -> None:
    dockerfile = golden_text("Dockerfile")
    images = re.findall(r"^FROM (\S+) AS (\w+)$", dockerfile, re.MULTILINE)
    assert [stage for _, stage in images] == ["build", "runtime"]
    image = load_baseline()["node-image"].value
    assert image is not None
    assert re.fullmatch(r"node:[\w.-]+@sha256:[0-9a-f]{64}", image)
    assert {name for name, _ in images} == {image}
    runtime = dockerfile.split(" AS runtime\n", 1)[1]
    assert "USER node\n" in runtime
    assert "USER root" not in dockerfile
    ignore = golden_text(".dockerignore").splitlines()
    assert "**" in ignore
    assert not [line for line in ignore if ".env" in line]


# trace: PRD-APP-010, PRD-APP-325
def test_root_layout_gives_the_public_runtime_values_from_the_server() -> None:
    files = project_files(golden_files())
    for path, content in files.items():
        assert b"NEXT_PUBLIC_" not in content, path
    server = golden_text("src/shared/config/public-config.server.gen.ts")
    assert server.count('import "server-only";') == 1
    for key, variable in PUBLIC_CONFIG_VARIABLES:
        assert f'  {key}: "{variable}",\n' in server
        assert f"    {key}: process.env.{variable}" in server
    client = golden_text("src/shared/config/public-config.gen.tsx")
    assert client.removeprefix(header(FileType.TYPESCRIPT, [APP])).startswith('"use client";\n')
    layout = golden_text("src/_app/layout/root-layout.gen.tsx")
    assert "await connection();" in layout
    assert "<PublicConfigProvider config={config}>" in layout
    keys = [key for key, _ in PUBLIC_CONFIG_VARIABLES]
    assert keys == ["region", "userPoolId", "appClientId", "loginDomain"]


# trace: PRD-APP-012
def test_health_route_needs_no_token() -> None:
    assert golden_text("app/healthz/route.ts").endswith(
        'export { GET } from "@/_app/api-routes/healthz.gen";\n'
    )
    handler = golden_text("src/_app/api-routes/healthz.gen.ts")
    assert 'Response.json({ status: "ok" } satisfies Health)' in handler
    assert "auth" not in handler.lower()


# trace: PRD-APP-015
def test_logs_are_json_lines_with_a_request_id() -> None:
    logger = golden_text("src/shared/log/logger.server.gen.ts")
    assert "process.stdout.write(`${JSON.stringify(entry)}\\n`);" in logger
    assert "requestId: requestIds.getStore() ?? null," in logger
    assert "response.headers.set(REQUEST_ID_HEADER, requestId);" in logger
    assert 'export const REQUEST_ID_HEADER = "X-Request-ID";' in golden_text(
        "src/shared/log/request-id.gen.ts"
    )


# trace: PRD-APP-305
def test_server_only_modules_go_through_index_server() -> None:
    for segment in ("config", "log"):
        public = golden_text(f"src/shared/{segment}/index.gen.ts")
        server = golden_text(f"src/shared/{segment}/index.server.gen.ts")
        assert ".server.gen" not in public, segment
        assert ".server.gen" in server, segment
        assert golden_text(f"src/shared/{segment}/index.server.ts").endswith(
            'export * from "./index.server.gen";\n'
        )


# trace: PRD-CORE-046
def test_extra_dependencies_come_from_the_configuration() -> None:
    settings = configuration(CONFIGURATION + 'dependencies = ["date-fns@4.1.0"]\n')
    runtime, _ = dependencies(
        application(),
        settings,
        load_baseline(),
        (nextjs.RUNTIME_PACKAGES, nextjs.DEV_PACKAGES),
        "Next.js",
    )
    assert runtime["date-fns"] == "4.1.0"
    assert list(runtime) == sorted(runtime)


# trace: PRD-CORE-046, PRD-TOP-008
@pytest.mark.parametrize("dependency", ["next@15.0.0", "drizzle-orm@0.44.0"])
def test_extra_dependency_must_not_be_a_package_of_the_target(dependency: str) -> None:
    settings = configuration(CONFIGURATION + f'dependencies = ["{dependency}"]\n')
    with pytest.raises(ToolchainError, match=r"is a package of the Next\.js target"):
        NextjsGenerator().generate(small_ir(application()), settings, None)


# trace: PRD-APP-002
def test_generator_writes_into_the_output_folder_of_each_application() -> None:
    ir = small_ir(application("orderApi", "fastapi"), application())
    settings = configuration('[applications.orderWeb]\noutput = "apps/web"\n')
    files = NextjsGenerator().generate(ir, settings, None)
    paths = sorted(file.path for file in files)
    assert paths == sorted(
        f"apps/web/{path}" for path in [*PROJECT_FILES, *DATABASE_FILES, *AUTH_FILES, *SLICE_FILES]
    )
    assert {file.part for file in files} == {application_part("orderWeb")}


def test_generator_needs_the_output_folder() -> None:
    with pytest.raises(ToolchainError, match=r"applications\.orderWeb\.output"):
        NextjsGenerator().generate(small_ir(application()), configuration(""), None)


# trace: PRD-CORE-005
def test_generator_skips_the_parts_that_the_run_does_not_select() -> None:
    files = NextjsGenerator().generate(small_ir(application()), configuration(""), ["pipelines"])
    assert files == []


def test_generator_calls_each_part_module(monkeypatch: pytest.MonkeyPatch) -> None:
    names = ("database", "auth", "slices", "routes", "pages")
    called: list[str] = []

    def part(name: str) -> Callable[[ReactContext], list[OutputFile]]:
        def files(item: ReactContext) -> list[OutputFile]:
            assert item.layout == NEXTJS_LAYOUT
            called.append(name)
            path = f"{item.folder}src/{name}.gen.ts"
            return [OutputFile(path, b"x\n", Kind.GENERATED, item.part)]

        return files

    monkeypatch.setattr(nextjs, "PART_FUNCTIONS", tuple(part(name) for name in names))
    files = NextjsGenerator().generate(small_ir(application()), configuration(), None)
    assert called == list(names)
    assert {f"src/{name}.gen.ts" for name in names} <= set(output_files(files))


def test_part_modules_after_the_slices_give_no_file_yet() -> None:
    item = application()
    context = ReactContext(
        TemplateEngine(),
        small_ir(item),
        item,
        configuration(),
        "",
        application_part(item.name),
        NEXTJS_LAYOUT,
    )
    modules = [function.__module__ for function in PART_FUNCTIONS]
    assert modules == [
        "dsml.generate.nextjs_database",
        "dsml.generate.nextjs_auth",
        "dsml.generate.nextjs_slices",
        "dsml.generate.nextjs_routes",
        "dsml.generate.nextjs_pages",
    ]
    for function in PART_FUNCTIONS[3:]:
        assert function(context) == [], function.__module__
