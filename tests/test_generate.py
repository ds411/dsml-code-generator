"""Tests of the file writer, the manifest and `dsml generate` (story #36).

The real generators come in later milestones. These tests use the test
generator `StaticGenerator`, which gives a fixed list of output files.
"""

import json
import os
import shutil
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.generate import generators
from dsml.generate.generators import collect
from dsml.generate.manifest import MANIFEST_PATH, read_manifest, sha256
from dsml.generate.writer import (
    INFRASTRUCTURE,
    PIPELINES,
    Change,
    Conflict,
    Kind,
    OutputFile,
    application_part,
    apply_plan,
    check_files,
    is_generated_name,
    make_plan,
)
from dsml.ir.model import Ir

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
SYN_001_REJECT = ROOT / "tests" / "models" / "rules" / "SYN-001" / "reject.sysml"
APP = application_part("orderApi")
FASTAPI_FIXED_NAMES = (
    "pyproject.toml",
    "Dockerfile",
    ".dockerignore",
    "alembic.ini",
    "migrations/env.py",
    "__init__.py",
)


# trace: PRD-CORE-005, PRD-CORE-039
@dataclass
class StaticGenerator:
    """The test generator. It gives a fixed list of output files."""

    files: list[OutputFile] = field(default_factory=list[OutputFile])
    fixed_names: Collection[str] = FASTAPI_FIXED_NAMES
    name: str = "test"

    def generate(
        self, ir: Ir, configuration: Configuration, parts: Collection[str] | None
    ) -> Sequence[OutputFile]:
        return [file for file in self.files if parts is None or file.part in parts]


def generated(path: str, text: str = "x = 1\n", part: str = APP) -> OutputFile:
    return OutputFile(path, text.encode(), Kind.GENERATED, part)


def create_once(path: str, text: str = "stub\n", part: str = APP) -> OutputFile:
    return OutputFile(path, text.encode(), Kind.CREATE_ONCE, part)


def run(
    root: Path,
    files: Sequence[OutputFile],
    parts: Collection[str] | None = None,
    overwrite: bool = False,
) -> tuple[list[str], list[Conflict]]:
    """Run the writer like `dsml generate`. Give the changes and the conflicts."""
    check_files(files, FASTAPI_FIXED_NAMES)
    plan = make_plan(root, files, parts)
    if overwrite or not plan.conflicts:
        apply_plan(root, plan)
    return [str(change) for change in plan.changes], list(plan.conflicts)


def files_on_disk(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


# The manifest.


def test_first_run_writes_the_files_and_the_manifest(tmp_path: Path) -> None:
    files = [
        generated("app/orders/api_gen.py", "a = 1\n"),
        create_once("app/orders/handler.py"),
        generated("infra/main.gen.tf", "b = 2\n", INFRASTRUCTURE),
    ]
    changes, conflicts = run(tmp_path, files)
    assert conflicts == []
    assert changes == [
        "add .dsml/generated.json",
        "add app/orders/api_gen.py",
        "add app/orders/handler.py",
        "add infra/main.gen.tf",
    ]
    assert files_on_disk(tmp_path)["app/orders/api_gen.py"] == b"a = 1\n"
    manifest = (tmp_path / MANIFEST_PATH).read_bytes()
    assert json.loads(manifest) == {
        "createOnce": [{"part": APP, "path": "app/orders/handler.py"}],
        "generated": [
            {"part": APP, "path": "app/orders/api_gen.py", "sha256": sha256(b"a = 1\n")},
            {"part": INFRASTRUCTURE, "path": "infra/main.gen.tf", "sha256": sha256(b"b = 2\n")},
        ],
        "manifestVersion": 1,
    }


def test_manifest_is_canonical_json(tmp_path: Path) -> None:
    files = [generated(f"z/{name}_gen.py") for name in ("c", "a", "b")]
    run(tmp_path, files)
    first = (tmp_path / MANIFEST_PATH).read_bytes()
    data = json.loads(first)
    assert [entry["path"] for entry in data["generated"]] == [
        "z/a_gen.py",
        "z/b_gen.py",
        "z/c_gen.py",
    ]
    assert first == (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()
    assert b"\r" not in first

    other = tmp_path / "other"
    other.mkdir()
    run(other, list(reversed(files)))
    assert (other / MANIFEST_PATH).read_bytes() == first


def test_second_run_with_the_same_files_changes_nothing(tmp_path: Path) -> None:
    files = [generated("a_gen.py"), create_once("handler.py")]
    run(tmp_path, files)
    assert run(tmp_path, files) == ([], [])


# trace: PRD-CORE-041
def test_old_generated_file_is_deleted(tmp_path: Path) -> None:
    run(tmp_path, [generated("app/old/api_gen.py"), generated("app/new_gen.py")])
    changes, conflicts = run(tmp_path, [generated("app/new_gen.py")])
    assert conflicts == []
    assert changes == ["change .dsml/generated.json", "delete app/old/api_gen.py"]
    assert not (tmp_path / "app" / "old").exists()
    assert (tmp_path / "app" / "new_gen.py").is_file()
    assert [entry.path for entry in read_manifest(tmp_path).generated] == ["app/new_gen.py"]


def test_folder_with_a_hand_written_file_stays_after_a_delete(tmp_path: Path) -> None:
    run(tmp_path, [generated("app/api_gen.py")])
    (tmp_path / "app" / "notes.md").write_bytes(b"notes\n")
    run(tmp_path, [])
    assert files_on_disk(tmp_path) == {
        "app/notes.md": b"notes\n",
        MANIFEST_PATH: (tmp_path / MANIFEST_PATH).read_bytes(),
    }


def test_old_generated_file_that_is_missing_is_not_an_error(tmp_path: Path) -> None:
    run(tmp_path, [generated("a_gen.py")])
    (tmp_path / "a_gen.py").unlink()
    changes, conflicts = run(tmp_path, [])
    assert (changes, conflicts) == (["change .dsml/generated.json"], [])


# trace: PRD-CORE-044
def test_create_once_file_is_written_one_time(tmp_path: Path) -> None:
    run(tmp_path, [create_once("handler.py", "stub\n")])
    (tmp_path / "handler.py").write_bytes(b"def handle() -> None: ...\n")
    changes, conflicts = run(tmp_path, [create_once("handler.py", "new stub\n")])
    assert (changes, conflicts) == ([], [])
    assert (tmp_path / "handler.py").read_bytes() == b"def handle() -> None: ...\n"


def test_create_once_file_is_not_written_over_a_hand_written_file(tmp_path: Path) -> None:
    (tmp_path / "handler.py").write_bytes(b"mine\n")
    changes, _ = run(tmp_path, [create_once("handler.py")])
    assert changes == ["add .dsml/generated.json"]
    assert (tmp_path / "handler.py").read_bytes() == b"mine\n"
    assert [entry.path for entry in read_manifest(tmp_path).create_once] == ["handler.py"]


def test_deleted_create_once_file_is_written_again(tmp_path: Path) -> None:
    run(tmp_path, [create_once("handler.py")])
    (tmp_path / "handler.py").unlink()
    changes, _ = run(tmp_path, [create_once("handler.py")])
    assert changes == ["add handler.py"]


def test_create_once_file_of_the_old_manifest_is_not_deleted(tmp_path: Path) -> None:
    run(tmp_path, [create_once("handler.py")])
    changes, _ = run(tmp_path, [])
    assert changes == ["change .dsml/generated.json"]
    assert (tmp_path / "handler.py").is_file()


def test_generated_file_that_becomes_create_once_stays(tmp_path: Path) -> None:
    run(tmp_path, [generated("index.gen.ts", "a\n")])
    changes, conflicts = run(tmp_path, [create_once("index.gen.ts", "b\n")])
    assert (changes, conflicts) == (["change .dsml/generated.json"], [])
    assert (tmp_path / "index.gen.ts").read_bytes() == b"a\n"


# trace: PRD-CORE-043
def test_changed_generated_file_stops_the_run(tmp_path: Path) -> None:
    run(tmp_path, [generated("a_gen.py", "a = 1\n"), generated("b_gen.py", "b = 1\n")])
    (tmp_path / "a_gen.py").write_bytes(b"a = 2\n")
    changes, conflicts = run(
        tmp_path, [generated("a_gen.py", "a = 3\n"), generated("b_gen.py", "b = 3\n")]
    )
    assert conflicts == [Conflict("a_gen.py", "changed")]
    assert changes == ["change .dsml/generated.json", "change a_gen.py", "change b_gen.py"]
    assert (tmp_path / "a_gen.py").read_bytes() == b"a = 2\n"
    assert (tmp_path / "b_gen.py").read_bytes() == b"b = 1\n"


# trace: PRD-CORE-043
def test_overwrite_replaces_a_changed_generated_file(tmp_path: Path) -> None:
    run(tmp_path, [generated("a_gen.py", "a = 1\n")])
    (tmp_path / "a_gen.py").write_bytes(b"a = 2\n")
    _, conflicts = run(tmp_path, [generated("a_gen.py", "a = 3\n")], overwrite=True)
    assert conflicts == [Conflict("a_gen.py", "changed")]
    assert (tmp_path / "a_gen.py").read_bytes() == b"a = 3\n"
    assert run(tmp_path, [generated("a_gen.py", "a = 3\n")]) == ([], [])


def test_changed_generated_file_that_the_run_deletes_stops_the_run(tmp_path: Path) -> None:
    run(tmp_path, [generated("a_gen.py")])
    (tmp_path / "a_gen.py").write_bytes(b"changed\n")
    changes, conflicts = run(tmp_path, [])
    assert conflicts == [Conflict("a_gen.py", "changed")]
    assert "delete a_gen.py" in changes
    assert (tmp_path / "a_gen.py").read_bytes() == b"changed\n"
    run(tmp_path, [], overwrite=True)
    assert not (tmp_path / "a_gen.py").exists()


def test_changed_generated_file_with_the_new_bytes_is_not_a_conflict(tmp_path: Path) -> None:
    run(tmp_path, [generated("a_gen.py", "a = 1\n")])
    (tmp_path / "a_gen.py").write_bytes(b"a = 2\n")
    assert run(tmp_path, [generated("a_gen.py", "a = 2\n")]) == (
        ["change .dsml/generated.json"],
        [],
    )


# trace: PRD-CORE-042
def test_file_at_the_path_of_a_new_generated_file_is_a_conflict(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_bytes(b"[project]\n")
    changes, conflicts = run(tmp_path, [generated("pyproject.toml", "[tool]\n")])
    assert conflicts == [Conflict("pyproject.toml", "not-in-manifest")]
    assert "change pyproject.toml" in changes
    assert (tmp_path / "pyproject.toml").read_bytes() == b"[project]\n"
    assert not (tmp_path / MANIFEST_PATH).exists()


# trace: PRD-CORE-042
def test_writer_does_not_touch_a_file_that_is_not_in_a_manifest(tmp_path: Path) -> None:
    hand_written = {
        "app/handler.py": b"hand\n",
        "app/api.py": b"hand\n",
        "infra/extra.tf": b"hand\n",
        "README.md": b"hand\n",
    }
    for path, content in hand_written.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_bytes(content)
    times = {path: (tmp_path / path).stat().st_mtime_ns for path in hand_written}

    run(tmp_path, [generated("app/api_gen.py"), generated("infra/main.gen.tf")])
    run(tmp_path, [generated("app/other_gen.py")])
    run(tmp_path, [], overwrite=True)

    disk = files_on_disk(tmp_path)
    for path, content in hand_written.items():
        assert disk[path] == content
        assert (tmp_path / path).stat().st_mtime_ns == times[path]
    assert set(disk) == {*hand_written, MANIFEST_PATH}


# trace: PRD-CORE-005
def test_run_of_one_part_keeps_the_files_of_the_other_parts(tmp_path: Path) -> None:
    run(
        tmp_path,
        [
            generated("app/api_gen.py"),
            create_once("app/handler.py"),
            generated("infra/main.gen.tf", part=INFRASTRUCTURE),
            generated(".github/workflows/pr.gen.yml", part=PIPELINES),
        ],
    )
    changes, _ = run(
        tmp_path, [generated("infra/other.gen.tf", part=INFRASTRUCTURE)], {INFRASTRUCTURE}
    )
    assert changes == [
        "change .dsml/generated.json",
        "delete infra/main.gen.tf",
        "add infra/other.gen.tf",
    ]
    manifest = read_manifest(tmp_path)
    assert sorted(entry.path for entry in manifest.generated) == [
        ".github/workflows/pr.gen.yml",
        "app/api_gen.py",
        "infra/other.gen.tf",
    ]
    assert [entry.path for entry in manifest.create_once] == ["app/handler.py"]
    assert (tmp_path / "app" / "api_gen.py").is_file()


def test_file_of_a_part_that_the_run_does_not_select_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ToolchainError, match="does not select this part"):
        make_plan(tmp_path, [generated("app/api_gen.py")], {INFRASTRUCTURE})


def test_file_of_an_other_part_in_the_manifest_is_an_error(tmp_path: Path) -> None:
    run(tmp_path, [generated("x/main.gen.tf", part=INFRASTRUCTURE)])
    with pytest.raises(ToolchainError, match='is a file of the part "infrastructure"'):
        make_plan(tmp_path, [generated("x/main.gen.tf", part=PIPELINES)], {PIPELINES})


def test_plan_writes_no_file(tmp_path: Path) -> None:
    run(tmp_path, [generated("old_gen.py")])
    before = files_on_disk(tmp_path)
    plan = make_plan(tmp_path, [generated("new_gen.py"), create_once("handler.py")], None)
    assert [change.path for change in plan.changes] == [
        MANIFEST_PATH,
        "handler.py",
        "new_gen.py",
        "old_gen.py",
    ]
    assert plan.changes[0] == Change("change", MANIFEST_PATH)
    assert files_on_disk(tmp_path) == before


def test_written_files_keep_their_bytes(tmp_path: Path) -> None:
    text = '# Generated by dsml 0. Do not edit.\nname = "Größe"\n'
    run(tmp_path, [generated("a_gen.py", text)])
    assert (tmp_path / "a_gen.py").read_bytes() == text.encode("utf-8")


@pytest.mark.skipif(os.name == "nt", reason="symbolic links need a privilege on Windows")
def test_symbolic_link_out_of_the_folder_is_an_error(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "app").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ToolchainError, match="goes out of the folder"):
        make_plan(root, [generated("app/api_gen.py")], None)


# The manifest reader.


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("{", "is not correct JSON"),
        ("[]", "The top level must be a JSON object"),
        ('{"generated": [], "createOnce": []}', "The keys must be"),
        ('{"generated": [], "createOnce": [], "manifestVersion": 2}', "version 2 is unknown"),
        ('{"generated": {}, "createOnce": [], "manifestVersion": 1}', "must be a list"),
        (
            '{"generated": [{"path": "a_gen.py", "part": "p"}], "createOnce": [],'
            ' "manifestVersion": 1}',
            "must have only the text keys",
        ),
        (
            '{"generated": [{"path": "a_gen.py", "part": "p", "sha256": "abc"}],'
            ' "createOnce": [], "manifestVersion": 1}',
            "is not a SHA-256 hash",
        ),
        (
            '{"generated": [], "createOnce": [{"path": "../x.py", "part": "p"}],'
            ' "manifestVersion": 1}',
            'The path "../x.py" is not a relative path',
        ),
        (
            '{"generated": [], "createOnce": [{"path": "a.py", "part": "p"},'
            ' {"path": "a.py", "part": "q"}], "manifestVersion": 1}',
            "occurs more than one time",
        ),
    ],
)
def test_manifest_that_is_not_correct_is_an_error(tmp_path: Path, text: str, message: str) -> None:
    (tmp_path / ".dsml").mkdir()
    (tmp_path / MANIFEST_PATH).write_text(text, encoding="utf-8")
    with pytest.raises(ToolchainError, match=message):
        read_manifest(tmp_path)


def test_missing_manifest_is_empty(tmp_path: Path) -> None:
    manifest = read_manifest(tmp_path)
    assert (manifest.generated, manifest.create_once) == ((), ())


# The checks of the output files.


@pytest.mark.parametrize(
    "path",
    [
        "src/orders/api_gen.py",
        "src/shared/index.gen.ts",
        "infra/modules/network/main.gen.tf",
        ".github/workflows/pr.gen.yml",
        "services/orders/pyproject.toml",
        "services/orders/Dockerfile",
        "services/orders/migrations/env.py",
        "services/orders/app/__init__.py",
        "web/app/page.tsx",
        "web/app/orders/[id]/page.tsx",
    ],
)
def test_generated_names(path: str) -> None:
    assert is_generated_name(path, (*FASTAPI_FIXED_NAMES, "app/"))


@pytest.mark.parametrize(
    "path",
    [
        "src/orders/api.py",
        "src/orders/gen.py",
        "src/orders/_gen.ts",
        "src/shared/index.ts",
        "infra/extra.tf",
        "services/orders/env.py",
        "services/orders/pyproject.toml.bak",
        "web/page.tsx",
        "web/myapp/page.tsx",
    ],
)
def test_names_that_are_not_generated_names(path: str) -> None:
    assert not is_generated_name(path, (*FASTAPI_FIXED_NAMES, "app/"))


@pytest.mark.parametrize(
    ("file", "message"),
    [
        (generated("src/api.py"), 'must end with ".gen.<ext>" or "_gen.py"'),
        (generated("/abs/a_gen.py"), "is not a relative path"),
        (generated("a/../b_gen.py"), "is not a relative path"),
        (generated("a\\b_gen.py"), "is not a relative path"),
        (generated(".dsml/x_gen.py"), "is not a relative path"),
        (generated("uv.lock"), 'must not write the lockfile "uv.lock"'),
        (create_once("web/pnpm-lock.yaml"), "must not write the lockfile"),
        (generated("a_gen.py", "a = 1\r\n"), "has a line end that is not LF"),
        (generated("a_gen.py", "﻿a = 1\n"), "starts with a byte order mark"),
        (generated("a_gen.py", "a = 1"), "does not end with one LF"),
        (generated("a_gen.py", "a = 1\n\n"), "does not end with one LF"),
        (OutputFile("a_gen.py", b"\xff\n", Kind.GENERATED, APP), "does not have UTF-8 encoding"),
    ],
)
def test_output_file_that_is_not_correct_is_an_error(file: OutputFile, message: str) -> None:
    with pytest.raises(ToolchainError, match=message):
        check_files([file], FASTAPI_FIXED_NAMES)


def test_create_once_file_can_have_any_name() -> None:
    check_files([create_once("src/orders/handler.py")], ())


def test_same_path_two_times_is_an_error() -> None:
    with pytest.raises(ToolchainError, match="more than one time"):
        check_files([generated("a_gen.py"), create_once("a_gen.py")])


def test_collect_checks_the_names_against_the_list_of_the_generator() -> None:
    fastapi = StaticGenerator([generated("svc/pyproject.toml", "[x]\n")], name="fastapi")
    other = StaticGenerator([generated("web/pyproject.toml", "[x]\n")], (), "other")
    assert [file.path for file in collect([fastapi], Ir(), Configuration(), None)] == [
        "svc/pyproject.toml"
    ]
    with pytest.raises(ToolchainError, match="The generator other is not correct"):
        collect([fastapi, other], Ir(), Configuration(), None)


def test_collect_finds_a_file_of_two_generators() -> None:
    one = StaticGenerator([generated("a_gen.py")], name="one")
    two = StaticGenerator([generated("a_gen.py")], name="two")
    with pytest.raises(ToolchainError, match=r'Two generators give the file "a_gen\.py"'):
        collect([one, two], Ir(), Configuration(), None)


# The subcommand `dsml generate`.

CLI_FILES = [
    generated("services/orders/api_gen.py", "api = 1\n"),
    create_once("services/orders/handler.py", "def handle() -> None: ...\n"),
    generated("services/orders/pyproject.toml", "[project]\n"),
    generated("infra/main.gen.tf", "a = 1\n", INFRASTRUCTURE),
    generated(".github/workflows/pr.gen.yml", "on: pull_request\n", PIPELINES),
]


@pytest.fixture(scope="module")
def example_ir() -> Ir:
    """Make the IR of the example model one time for the tests of this module."""
    from dsml.adapter.convert import make_ir

    return make_ir([EXAMPLE_MODEL], ROOT)


@pytest.fixture
def project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example_ir: Ir
) -> Iterator[StaticGenerator]:
    """Make a project folder with a configuration file. Give its test generator."""
    import dsml.adapter.convert

    (tmp_path / "model").mkdir()
    shutil.copy(EXAMPLE_MODEL, tmp_path / "model" / "order-service.sysml")
    (tmp_path / "dsml.toml").write_text('schema = 1\n\n[model]\npaths = ["model"]\n')
    monkeypatch.chdir(tmp_path)

    def make_ir(files: Sequence[Path], root: Path) -> Ir:
        return example_ir

    monkeypatch.setattr(dsml.adapter.convert, "make_ir", make_ir)
    generator = StaticGenerator(list(CLI_FILES))
    monkeypatch.setattr(generators, "GENERATORS", [generator])
    yield generator


def dsml(*argv: str) -> int:
    from dsml.cli import main

    return main(list(argv))


def test_generate_writes_the_files(
    project: StaticGenerator, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert dsml("generate") == 0
    assert capsys.readouterr().out == (
        "add .dsml/generated.json\n"
        "add .github/workflows/pr.gen.yml\n"
        "add infra/main.gen.tf\n"
        "add services/orders/api_gen.py\n"
        "add services/orders/handler.py\n"
        "add services/orders/pyproject.toml\n"
    )
    assert set(files_on_disk(tmp_path)) >= {file.path for file in CLI_FILES}


# trace: PRD-CORE-004
def test_generate_check_lists_the_changes_and_writes_no_file(
    project: StaticGenerator, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = files_on_disk(tmp_path)
    assert dsml("generate", "--check") == 1
    assert capsys.readouterr().out.splitlines() == [
        "add .dsml/generated.json",
        "add .github/workflows/pr.gen.yml",
        "add infra/main.gen.tf",
        "add services/orders/api_gen.py",
        "add services/orders/handler.py",
        "add services/orders/pyproject.toml",
    ]
    assert files_on_disk(tmp_path) == before

    assert dsml("generate") == 0
    capsys.readouterr()
    assert dsml("generate", "--check") == 0
    assert capsys.readouterr().out == ""

    (tmp_path / "infra" / "main.gen.tf").write_bytes(b"a = 2\n")
    project.files = [
        *CLI_FILES[:3],
        CLI_FILES[4],
        generated("infra/new.gen.tf", part=INFRASTRUCTURE),
    ]
    before = files_on_disk(tmp_path)
    assert dsml("generate", "--check") == 1
    assert capsys.readouterr().out.splitlines() == [
        "change .dsml/generated.json",
        "delete infra/main.gen.tf",
        "add infra/new.gen.tf",
    ]
    assert files_on_disk(tmp_path) == before


# trace: PRD-CORE-043
def test_generate_stops_with_the_list_of_changed_files(
    project: StaticGenerator, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert dsml("generate") == 0
    (tmp_path / "services" / "orders" / "api_gen.py").write_bytes(b"api = 2\n")
    project.files = [generated("services/orders/api_gen.py", "api = 3\n"), *CLI_FILES[1:]]
    project.files.append(generated("infra/new.gen.tf", part=INFRASTRUCTURE))
    capsys.readouterr()
    before = files_on_disk(tmp_path)

    assert dsml("generate") == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "dsml: error: services/orders/api_gen.py: "
        "The file is different from its hash in the manifest.\n"
        "dsml: error: No file was written. Use --overwrite to replace or delete these files.\n"
    )
    assert files_on_disk(tmp_path) == before

    assert dsml("generate", "--overwrite") == 0
    assert capsys.readouterr().out == (
        "change .dsml/generated.json\nadd infra/new.gen.tf\nchange services/orders/api_gen.py\n"
    )
    assert (tmp_path / "services" / "orders" / "api_gen.py").read_bytes() == b"api = 3\n"


# trace: PRD-CORE-005
@pytest.mark.parametrize(
    ("argv", "paths"),
    [
        (
            ["--application", "orderApi"],
            [
                "services/orders/api_gen.py",
                "services/orders/handler.py",
                "services/orders/pyproject.toml",
            ],
        ),
        (["--infrastructure"], ["infra/main.gen.tf"]),
        (["--pipelines"], [".github/workflows/pr.gen.yml"]),
        (
            ["--infrastructure", "--pipelines"],
            [".github/workflows/pr.gen.yml", "infra/main.gen.tf"],
        ),
    ],
)
def test_generate_one_part(
    project: StaticGenerator,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    paths: list[str],
) -> None:
    assert dsml("generate", *argv) == 0
    assert capsys.readouterr().out.splitlines() == [
        "add .dsml/generated.json",
        *(f"add {path}" for path in paths),
    ]
    assert sorted(set(files_on_disk(tmp_path)) - {"dsml.toml", "model/order-service.sysml"}) == (
        sorted([MANIFEST_PATH, *paths])
    )


def test_generate_unknown_application_gives_exit_code_2(
    project: StaticGenerator, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert dsml("generate", "--application", "billing") == 2
    assert capsys.readouterr().err == (
        'dsml: error: The model has no application "billing". '
        "The applications of the model are: orderApi.\n"
    )
    assert not (tmp_path / ".dsml").exists()


def test_generate_with_a_wrong_generator_output_gives_exit_code_2(
    project: StaticGenerator, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project.files = [generated("services/orders/api.py")]
    assert dsml("generate") == 2
    assert capsys.readouterr().err == (
        "dsml: error: The generator test is not correct.\n"
        'dsml: error: Generator output: The name of the generated file "services/orders/api.py" '
        'must end with ".gen.<ext>" or "_gen.py", or be on the fixed-name list of the target.\n'
    )
    assert not (tmp_path / ".dsml").exists()


def test_generate_writes_the_report_to_the_output_file(
    project: StaticGenerator, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert dsml("generate", "--check", "--output", "changes.txt") == 1
    assert capsys.readouterr().out == ""
    assert (tmp_path / "changes.txt").read_bytes().startswith(b"add .dsml/generated.json\n")


# trace: PRD-CORE-003
def test_generate_stops_before_it_writes_a_file_if_there_is_an_error_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copy(SYN_001_REJECT, tmp_path / "model.sysml")
    (tmp_path / "dsml.toml").write_text('schema = 1\n\n[model]\npaths = ["model.sysml"]\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(generators, "GENERATORS", [StaticGenerator(list(CLI_FILES))])

    assert dsml("generate") == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert lines[0].startswith("dsml: model.sysml:")
    assert ": error: SYN-001: " in lines[0]
    assert lines[-1].startswith("dsml: error: The model has ")
    assert lines[-1].endswith(". No file was written.")
    assert sorted(files_on_disk(tmp_path)) == ["dsml.toml", "model.sysml"]
