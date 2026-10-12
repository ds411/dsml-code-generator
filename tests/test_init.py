"""Tests of the subcommand `dsml init` (stories #38, #171 and #185).

Some tests start a private `sysml-grpc` child process. If the binary is not
in the cache, the `opensysml` client downloads it one time.
"""

from pathlib import Path

import pytest

from dsml import starter
from dsml.adapter.engine import Engine
from dsml.cli import main
from dsml.config import load_configuration
from dsml.errors import ToolchainError
from dsml.generate.manifest import MANIFEST_PATH
from dsml.generate.writer import Kind, OutputFile, write_create_once
from dsml.library import LIBRARY_VERSION, library_document

CONFIG = "dsml.toml"
MODEL = "model/model.sysml"


def _files(folder: Path) -> dict[str, bytes]:
    """Give the bytes of each file in a folder and its subfolders, by relative path."""
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


# trace: PRD-CORE-001, PRD-CORE-044
def test_init_in_an_empty_folder_writes_the_two_files(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init"]) == 0
    captured = capsys.readouterr()
    assert captured.out == f"add {CONFIG}\nadd {MODEL}\n"
    assert captured.err == ""
    assert _files(folder) == starter.starter_files("fastapi")


# trace: PRD-CORE-001
def test_init_accepts_the_target_fastapi(folder: Path) -> None:
    assert main(["init", "--target", "fastapi"]) == 0
    assert _files(folder) == starter.starter_files("fastapi")


# trace: PRD-CORE-001
def test_init_accepts_the_target_react(folder: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["init", "--target", "react"]) == 0
    assert capsys.readouterr().out == f"add {CONFIG}\nadd {MODEL}\n"
    assert _files(folder) == starter.starter_files("react")


# trace: PRD-CORE-001
def test_init_accepts_the_target_nextjs(folder: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["init", "--target", "nextjs"]) == 0
    assert capsys.readouterr().out == f"add {CONFIG}\nadd {MODEL}\n"
    assert _files(folder) == starter.starter_files("nextjs")


# trace: PRD-CORE-001
def test_init_refuses_a_target_that_has_no_starter_files(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init", "--target", "unknown"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("usage: dsml init")
    assert _files(folder) == {}


# trace: PRD-CORE-042, PRD-CORE-044
def test_init_in_a_folder_with_the_files_changes_no_file(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (folder / "model").mkdir()
    (folder / CONFIG).write_bytes(b"schema = 1\n")
    (folder / MODEL).write_bytes(b"package Mine;\n")
    before = _files(folder)
    assert main(["init"]) == 0
    captured = capsys.readouterr()
    assert captured.out == (
        f"keep {CONFIG}: The file exists. The command did not change it.\n"
        f"keep {MODEL}: The file exists. The command did not change it.\n"
    )
    assert captured.err == ""
    assert _files(folder) == before


# trace: PRD-CORE-044
def test_init_writes_only_the_file_that_does_not_exist(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (folder / CONFIG).write_bytes(b"schema = 1\n")
    assert main(["init"]) == 0
    assert capsys.readouterr().out == (
        f"keep {CONFIG}: The file exists. The command did not change it.\nadd {MODEL}\n"
    )
    assert _files(folder) == {
        CONFIG: b"schema = 1\n",
        MODEL: starter.starter_files("fastapi")[MODEL],
    }


# trace: PRD-CORE-044
def test_init_two_times_gives_the_same_files(folder: Path) -> None:
    assert main(["init"]) == 0
    first = _files(folder)
    assert main(["init"]) == 0
    assert _files(folder) == first


# trace: PRD-CORE-040, PRD-CORE-042
def test_init_writes_no_manifest(folder: Path) -> None:
    assert main(["init"]) == 0
    assert not (folder / MANIFEST_PATH).exists()


# trace: PRD-CORE-006, PRD-CORE-012
def test_init_with_config_writes_the_files_in_the_folder_of_the_file(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = folder / "report.txt"
    assert main(["init", "--config", "repo/other.toml", "--output", str(report)]) == 0
    assert capsys.readouterr().out == ""
    assert report.read_text(encoding="utf-8") == "add repo/model/model.sysml\nadd repo/other.toml\n"
    files = starter.starter_files("fastapi")
    assert _files(folder / "repo") == {"other.toml": files[CONFIG], MODEL: files[MODEL]}


# trace: PRD-CORE-013, PRD-CORE-014
@pytest.mark.parametrize("target", starter.TARGETS)
def test_starter_configuration_passes_the_checks(target: str, folder: Path) -> None:
    assert main(["init", "--target", target]) == 0
    configuration = load_configuration(folder / CONFIG)
    assert [path.as_posix() for path in configuration.model] == ["model"]


# trace: PRD-CORE-034
@pytest.mark.parametrize("target", starter.TARGETS)
@pytest.mark.parametrize("name", [CONFIG, MODEL])
def test_starter_file_is_utf8_with_lf_line_ends(target: str, name: str) -> None:
    content = starter.starter_files(target)[name]
    text = content.decode("utf-8")
    assert "\r" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


# trace: PRD-DSML-004, PRD-DSML-008
def test_starter_model_parses_and_resolves_with_the_library(folder: Path) -> None:
    assert main(["init"]) == 0
    with Engine() as engine:
        model = engine.parse_texts(
            [library_document(), (MODEL, (folder / MODEL).read_text(encoding="utf-8"))]
        )
        assert [str(item) for item in model.diagnostics] == []
        for element, keyword in [
            ("Owner", "Stakeholder"),
            ("firstNeed", "Need"),
            ("firstRequirement", "Requirement"),
        ]:
            assert model.has_metadata(element, f"DSML::{keyword}", "StarterModel")


# trace: PRD-DSML-056
@pytest.mark.parametrize("target", starter.TARGETS)
def test_starter_model_gives_the_major_and_minor_version_of_the_library(target: str) -> None:
    major, minor, _ = LIBRARY_VERSION.split(".")
    text = starter.starter_files(target)[MODEL].decode("utf-8")
    assert f"@DsmlVersion {{ major = {major}; minor = {minor}; }}" in text


# trace: PRD-CORE-001
def test_ir_of_the_starter_files_has_no_finding(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init"]) == 0
    capsys.readouterr()
    assert main(["ir"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert '"findings": []' in captured.out


# trace: PRD-CORE-001, PRD-DSML-030, PRD-DSML-031, PRD-DSML-039
@pytest.mark.parametrize("target", ["react", "nextjs"])
def test_starter_model_with_applications_validates_with_no_finding(
    target: str, folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init", "--target", target]) == 0
    capsys.readouterr()
    assert main(["validate"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == "Findings: 0 errors, 0 warnings, 0 info.\n"


# trace: PRD-CORE-001, PRD-APP-002
def test_generate_on_the_react_starter_writes_the_two_projects(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init", "--target", "react"]) == 0
    assert main(["generate"]) == 0
    capsys.readouterr()
    for path in [
        "apps/item-portal/package.json",
        "apps/item-portal/src/main.gen.tsx",
        "apps/item-portal/src/entities/item/model/item.gen.ts",
        "apps/item-portal/src/shared/api/client.gen.ts",
        "services/item-api/pyproject.toml",
        "services/item-api/app/features/item/read_item/endpoint_gen.py",
    ]:
        assert (folder / path).is_file(), path
    assert _files(folder / "model") == {"model.sysml": starter.starter_files("react")[MODEL]}


# trace: PRD-CORE-001, PRD-APP-002
def test_generate_on_the_nextjs_starter_writes_the_project(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init", "--target", "nextjs"]) == 0
    assert main(["generate"]) == 0
    capsys.readouterr()
    for path in [
        "apps/item-web/package.json",
        "apps/item-web/steiger.config.ts",
        "apps/item-web/proxy.ts",
        "apps/item-web/src/entities/item/model/item.gen.ts",
        "apps/item-web/src/shared/db/schema.gen.ts",
    ]:
        assert (folder / path).is_file(), path
    assert _files(folder / "model") == {"model.sysml": starter.starter_files("nextjs")[MODEL]}


# trace: PRD-CORE-044
def test_write_create_once_refuses_a_generated_file(tmp_path: Path) -> None:
    file = OutputFile("api_gen.py", b"x = 1\n", Kind.GENERATED, "init")
    with pytest.raises(ToolchainError, match="is not a create-once file"):
        write_create_once(tmp_path, [file])
    assert _files(tmp_path) == {}
