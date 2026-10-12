"""Tests of the React generator: project files and generator frame (story #167).

The golden files in `tests/golden/react/order-portal/` are the output of the
React generator for the order portal model. The folder is the project
folder of the application orderPortal. Write the files again with
`uv run python scripts/write_golden_react.py`. The CI job "React golden
project" runs Prettier, tsc, ESLint, Steiger, Vitest and `pnpm build` on
the golden project.

The test of the golden files compares only the project files. The test of
each layer story compares the folder of its layer in `src/`. The test of the
full output (story #177) compares all files and the manifests in `.dsml/`.
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from dsml.config import Configuration, parse_configuration
from dsml.errors import ToolchainError
from dsml.generate import generators, react
from dsml.generate.generators import collect
from dsml.generate.header import FileType, file_type_of, header
from dsml.generate.manifest import MANIFEST_PATH
from dsml.generate.react import FIXED_NAMES, ReactGenerator, dependencies
from dsml.generate.react_common import (
    LAYERS,
    ReactContext,
    file_name,
    public_api_files,
    slice_folder,
    slice_name,
)
from dsml.generate.templates import TemplateEngine
from dsml.generate.trace import TRACE_PATH
from dsml.generate.writer import (
    LOCKFILES,
    Kind,
    OutputFile,
    application_part,
    apply_plan,
    make_plan,
)
from dsml.ir.model import Attribute, Element, EnumValue, Ir, Location
from dsml.versions import load_baseline, pinned_version

ROOT = Path(__file__).resolve().parent.parent
PORTAL_MODEL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
GOLDEN = ROOT / "tests" / "golden" / "react" / "order-portal"
APP = "OrderPortal::orderPortal"
PROJECT_FILES = [
    "components.json",
    "eslint.config.js",
    "index.html",
    "package.json",
    "src/main.gen.tsx",
    "steiger.config.ts",
    "tsconfig.json",
    "vite.config.ts",
]
CONFIGURATION = '[applications.orderPortal]\noutput = "."\n'


def configuration(text: str = CONFIGURATION) -> Configuration:
    return parse_configuration(f"schema = 1\n\n{text}", Path("dsml.toml"))


def layer_folder(path: str) -> bool:
    """Tell if a path is in the folder of an FSD layer. The layer stories test these files."""
    return any(path.startswith(f"src/{layer}/") for layer in LAYERS)


def manifest_file(path: str) -> bool:
    """Tell if a path is a manifest in `.dsml/`. The test of the full output tests these files."""
    return path.startswith(".dsml/")


def project_files(files: dict[str, bytes]) -> dict[str, bytes]:
    return {
        path: content
        for path, content in files.items()
        if not layer_folder(path) and not manifest_file(path)
    }


def folder_files(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def golden_files() -> dict[str, bytes]:
    return folder_files(GOLDEN)


def application(name: str = "orderPortal", target: str = "react") -> Element:
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


def context(folder: str = "web/") -> ReactContext:
    item = application()
    return ReactContext(
        TemplateEngine(),
        small_ir(item),
        item,
        configuration(),
        folder,
        application_part(item.name),
    )


@pytest.fixture(scope="module")
def portal_ir() -> Ir:
    """Make the IR of the order portal model one time for the tests of this module."""
    from dsml.adapter.convert import make_ir

    return make_ir([PORTAL_MODEL], ROOT)


# trace: PRD-CORE-030, PRD-APP-002, PRD-APP-235
def test_project_files_of_the_order_portal_agree_with_the_golden_files(portal_ir: Ir) -> None:
    files = collect([ReactGenerator()], portal_ir, configuration(), None)
    output = project_files({file.path: file.content for file in files})
    assert output == project_files(golden_files()), (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_react.py and examine the differences."
    )
    assert sorted(output) == PROJECT_FILES


# trace: PRD-CORE-029, PRD-CORE-030, PRD-CORE-040, PRD-TRACE-006
def test_full_output_of_the_order_portal_agrees_with_the_golden_files(
    portal_ir: Ir, tmp_path: Path
) -> None:
    """Write the output with the manifests, as `dsml generate` does, and compare all bytes."""
    files = collect([ReactGenerator()], portal_ir, configuration(), None)
    apply_plan(tmp_path, make_plan(tmp_path, files, None))
    output = folder_files(tmp_path)
    golden = golden_files()
    assert sorted(output) == sorted(golden)
    different = sorted(path for path in output if output[path] != golden[path])
    assert different == [], (
        "The output is different from the golden files. If the change is correct, run "
        "uv run python scripts/write_golden_react.py and examine the differences."
    )
    assert MANIFEST_PATH in output
    assert TRACE_PATH in output


# trace: PRD-CORE-040, PRD-TRACE-006, PRD-TRACE-008
def test_manifests_of_the_order_portal_give_each_file_and_its_symbols() -> None:
    """Each generated file is in `generated.json` with its hash. Each symbol has a line range."""
    golden = golden_files()
    manifest = json.loads(golden[MANIFEST_PATH])
    generated = {item["path"]: item["sha256"] for item in manifest["generated"]}
    create_once = {item["path"] for item in manifest["createOnce"]}
    on_disk = {path for path in golden if not manifest_file(path)}
    assert generated.keys() | create_once == on_disk
    assert not generated.keys() & create_once
    for path, sha256 in generated.items():
        assert hashlib.sha256(golden[path]).hexdigest() == sha256, path
    trace = json.loads(golden[TRACE_PATH])
    elements = [item["element"] for item in trace["elements"]]
    assert elements == sorted(elements)
    traced: set[str] = set()
    for item in trace["elements"]:
        paths = [file["path"] for file in item["files"]]
        assert paths == sorted(paths)
        for file in item["files"]:
            assert file["path"] in generated
            assert file["symbols"]
            lines = golden[file["path"]].count(b"\n")
            for symbol in file["symbols"]:
                assert 1 <= symbol["firstLine"] <= symbol["lastLine"] <= lines, symbol
            traced.add(file["path"])
    # Each TypeScript module with a top-level declaration has symbols. A public
    # API file only re-exports other modules, and the entry module and the
    # tool configurations export no declaration.
    no_symbols = sorted(
        path for path in generated if path.endswith((".ts", ".tsx")) and path not in traced
    )
    assert no_symbols == sorted(
        [
            *(path for path in generated if path.endswith("/index.gen.ts")),
            "src/main.gen.tsx",
            "steiger.config.ts",
            "vite.config.ts",
        ]
    )
    assert "OrderPortal::orderPortal" in elements


# trace: PRD-CORE-028
def test_output_is_the_same_at_each_run(portal_ir: Ir) -> None:
    first = collect([ReactGenerator()], portal_ir, configuration(), None)
    second = collect([ReactGenerator()], portal_ir, configuration(), None)
    assert first == second


def test_react_generator_is_in_the_list_of_generators() -> None:
    assert any(isinstance(generator, ReactGenerator) for generator in generators.GENERATORS)


# trace: PRD-APP-235, PRD-CORE-036, PRD-CORE-039
def test_fixed_names_and_no_lockfile(portal_ir: Ir) -> None:
    assert set(FIXED_NAMES) == {
        "package.json",
        "tsconfig.json",
        "vite.config.ts",
        "index.html",
        "components.json",
        "steiger.config.ts",
        "eslint.config.js",
    }
    files = collect([ReactGenerator()], portal_ir, configuration(), None)
    # Only the public API index.ts of a slice or a segment, the shadcn/ui
    # copy in src/shared/ and the theme src/app/styles/index.css are
    # create-once files (PRD-APP-204, PRD-APP-212).
    assert all(
        file.kind is Kind.GENERATED
        or Path(file.path).name == "index.ts"
        or file.path.startswith(("src/shared/ui/", "src/shared/lib/"))
        or file.path == "src/app/styles/index.css"
        for file in files
    )
    assert not [file.path for file in files if Path(file.path).name in LOCKFILES]
    assert not [file.path for file in files if file.path.startswith(".dsml/")]


# trace: PRD-APP-017, PRD-TRACE-005
def test_each_typescript_and_javascript_file_has_the_trace_header() -> None:
    for path, content in project_files(golden_files()).items():
        file_type = file_type_of(path)
        if file_type in (FileType.TYPESCRIPT, FileType.JAVASCRIPT):
            assert content.decode().startswith(header(file_type, [APP])), path
        else:
            assert not content.startswith(b"// Generated"), path


# trace: PRD-APP-201, PRD-TOP-008, PRD-CORE-046
def test_package_json_pins_the_versions_of_the_baseline() -> None:
    package = json.loads((GOLDEN / "package.json").read_bytes())
    pinned = {**package["dependencies"], **package["devDependencies"]}
    items = {**react.RUNTIME_PACKAGES, **react.DEV_PACKAGES}
    assert set(pinned) == set(items)
    for name, version in pinned.items():
        assert version == pinned_version(items[name]), name
    for key in ("dependencies", "devDependencies"):
        assert list(package[key]) == sorted(package[key]), key
    assert package["packageManager"] == f"pnpm@{pinned_version('pnpm')}"
    assert package["devEngines"]["runtime"]["version"] == pinned_version("node")
    assert package["type"] == "module"
    assert package["scripts"]["build"] == "vite build"


# trace: PRD-APP-201
@pytest.mark.parametrize(
    "package",
    [
        "@tanstack/react-router",
        "@tanstack/react-query",
        "@tanstack/react-form",
        "zod",
        "aws-amplify",
        "react",
        "vite",
        "tailwindcss",
        "typescript",
        "eslint",
        "typescript-eslint",
        "vitest",
        "steiger",
    ],
)
def test_package_json_has_the_stack_of_the_target(package: str) -> None:
    data = json.loads((GOLDEN / "package.json").read_bytes())
    assert package in {**data["dependencies"], **data["devDependencies"]}


# trace: PRD-APP-201, PRD-APP-205
def test_tsconfig_is_strict_and_gives_the_path_alias() -> None:
    options = json.loads((GOLDEN / "tsconfig.json").read_bytes())["compilerOptions"]
    assert options["strict"] is True
    assert options["paths"] == {"@/*": ["./src/*"]}
    vite = (GOLDEN / "vite.config.ts").read_text(encoding="utf-8")
    assert 'alias: [{ find: /^@\\//, replacement: "/src/" }]' in vite


# trace: PRD-APP-233
def test_build_writes_dist_and_reads_no_environment_value() -> None:
    vite = (GOLDEN / "vite.config.ts").read_text(encoding="utf-8")
    assert 'outDir: "dist"' in vite
    for path, content in project_files(golden_files()).items():
        text = content.decode()
        assert "import.meta.env" not in text, path
        assert "process.env" not in text, path
        assert "loadEnv" not in text, path


# trace: PRD-CORE-046
def test_extra_dependencies_come_from_the_configuration() -> None:
    settings = configuration(
        CONFIGURATION + 'dependencies = ["date-fns@4.1.0", "@scope/tool@1.2.3"]\n'
    )
    runtime, dev = dependencies(application(), settings, load_baseline())
    assert runtime["date-fns"] == "4.1.0"
    assert runtime["@scope/tool"] == "1.2.3"
    assert list(runtime) == sorted(runtime)
    assert "date-fns" not in dev


# trace: PRD-CORE-046, PRD-TOP-008
@pytest.mark.parametrize(
    ("dependency", "message"),
    [
        ("date-fns", 'must have the form "<package>@<version>"'),
        ("date-fns@", 'must have the form "<package>@<version>"'),
        ("@scope/tool", 'must have the form "<package>@<version>"'),
        ("zod@3.0.0", "is a package of the React target"),
        ("vite@7.0.0", "is a package of the React target"),
    ],
)
def test_extra_dependency_errors(dependency: str, message: str) -> None:
    settings = configuration(CONFIGURATION + f'dependencies = ["{dependency}"]\n')
    with pytest.raises(ToolchainError, match=message):
        dependencies(application(), settings, load_baseline())


# trace: PRD-APP-002
def test_generator_writes_into_the_output_folder_of_each_application() -> None:
    ir = small_ir(application("orderApi", "fastapi"), application())
    settings = configuration('[applications.orderPortal]\noutput = "apps/portal"\n')
    files = ReactGenerator().generate(ir, settings, None)
    paths = sorted(file.path for file in files)
    assert all(path.startswith("apps/portal/") for path in paths)
    assert [path for path in paths if not layer_folder(path.removeprefix("apps/portal/"))] == [
        f"apps/portal/{path}" for path in PROJECT_FILES
    ]
    assert {file.part for file in files} == {application_part("orderPortal")}


def test_generator_needs_the_output_folder() -> None:
    with pytest.raises(ToolchainError, match=r"applications\.orderPortal\.output"):
        ReactGenerator().generate(small_ir(application()), configuration(""), None)


# trace: PRD-CORE-005
def test_generator_skips_the_parts_that_the_run_does_not_select() -> None:
    files = ReactGenerator().generate(small_ir(application()), configuration(""), ["pipelines"])
    assert files == []


# trace: PRD-APP-202
def test_generator_calls_each_layer_module(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    def layer(name: str) -> Callable[[ReactContext], list[OutputFile]]:
        def files(item: ReactContext) -> list[OutputFile]:
            called.append(name)
            path = f"{item.folder}src/{name}/x.gen.ts"
            return [OutputFile(path, b"x\n", Kind.GENERATED, item.part)]

        return files

    monkeypatch.setattr(react, "LAYER_FUNCTIONS", tuple(layer(name) for name in reversed(LAYERS)))
    files = ReactGenerator().generate(small_ir(application()), configuration(), None)
    assert called == list(reversed(LAYERS))
    assert {f"src/{name}/x.gen.ts" for name in LAYERS} <= {file.path for file in files}


# trace: PRD-APP-202
def test_each_layer_module_writes_only_into_its_layer() -> None:
    item = context()
    for layer, function in zip(reversed(LAYERS), react.LAYER_FUNCTIONS, strict=True):
        assert function.__module__ == f"dsml.generate.react_{layer}"
        for file in function(item):
            assert file.path.startswith(f"web/src/{layer}/"), file.path
    assert LAYERS == ("app", "pages", "widgets", "features", "entities", "shared")


# trace: PRD-APP-206
@pytest.mark.parametrize(
    ("name", "expected"),
    [("orderList", "order-list"), ("Order", "order"), ("cancelOrder", "cancel-order")],
)
def test_slice_names_are_kebab_case(name: str, expected: str) -> None:
    assert slice_name(name) == expected


# trace: PRD-APP-206
def test_file_names_are_kebab_case() -> None:
    assert file_name("orderList", "page") == "order-list-page"
    assert file_name("Order") == "order"
    assert slice_folder("pages", "orderList") == "src/pages/order-list"
    assert slice_folder("entities", "Order") == "src/entities/order"


@pytest.mark.parametrize("layer", ["app", "shared", "processes"])
def test_slice_folder_needs_a_layer_with_slices(layer: str) -> None:
    with pytest.raises(ValueError, match="has no slices"):
        slice_folder(layer, "order")


# trace: PRD-APP-204, PRD-APP-017, PRD-CORE-044
def test_public_api_of_a_slice() -> None:
    files = public_api_files(
        context(),
        "src/pages/order-list",
        ["ui/order-list-page.gen", "model/order-list.gen"],
        ["Shop::orderList"],
    )
    generated, public = files
    assert generated.path == "web/src/pages/order-list/index.gen.ts"
    assert generated.kind is Kind.GENERATED
    assert generated.content.decode() == (
        header(FileType.TYPESCRIPT, ["Shop::orderList"])
        + 'export * from "./model/order-list.gen";\n'
        + 'export * from "./ui/order-list-page.gen";\n'
    )
    assert public.path == "web/src/pages/order-list/index.ts"
    assert public.kind is Kind.CREATE_ONCE
    assert public.content.decode().endswith('export * from "./index.gen";\n')
    assert not public.content.startswith(b"// Generated")
