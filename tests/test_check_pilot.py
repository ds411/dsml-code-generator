"""Tests of the pilot check script (story #23, PRD-DSML-005).

These tests do not start the pilot kernel and do not use the network. The CI
job "Pilot" runs the kernel.
"""

import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_pilot", ROOT / "scripts/check_pilot.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check_pilot: Any = _load_script()


def _stream(text: str, name: str = "stderr") -> dict[str, Any]:
    return {"msg_type": "stream", "content": {"name": name, "text": text}}


OK = {"content": {"status": "ok"}}


def test_pin_is_in_the_version_baseline() -> None:
    release = check_pilot.pinned_release()
    assert release.version == "0.62.0"
    assert release.release == "2026-08"
    assert len(release.sha256) == 64
    assert release.url == (
        "https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation/releases/download/"
        "2026-08/jupyter-sysml-kernel-0.62.0.zip"
    )


def test_cell_with_no_diagnostic_is_accepted() -> None:
    result = check_pilot.cell_result(OK, [_stream("LibraryPackage DSML\n", name="stdout")])
    assert result.accepted
    assert result.errors == ()


def test_error_line_rejects_the_cell() -> None:
    text = "ERROR:Couldn't resolve reference to Classifier 'Undefined'. (1.sysml line : 8)\n"
    result = check_pilot.cell_result(OK, [_stream(text)])
    assert not result.accepted
    assert result.errors == (text.strip(),)


def test_warning_line_does_not_reject_the_cell() -> None:
    result = check_pilot.cell_result(OK, [_stream("WARNING:Something (1.sysml line : 2)\n")])
    assert result.accepted
    assert result.warnings == ("WARNING:Something (1.sysml line : 2)",)


def test_error_message_rejects_the_cell() -> None:
    message = {"msg_type": "error", "content": {"ename": "Exception", "evalue": "Bad"}}
    result = check_pilot.cell_result({"content": {"status": "error"}}, [message])
    assert result.errors == ("Exception: Bad",)


def test_reply_status_that_is_not_ok_rejects_the_cell() -> None:
    result = check_pilot.cell_result({"content": {"status": "aborted"}}, [])
    assert result.errors == ("The kernel reply has the status 'aborted'.",)


def _release(tmp_path: Path) -> tuple[Any, bytes]:
    data = b"archive"
    sha256 = hashlib.sha256(data).hexdigest()
    return check_pilot.Release(version="0.0.1", release="test", sha256=sha256), data


def test_download_keeps_an_archive_with_the_correct_hash(tmp_path: Path) -> None:
    release, data = _release(tmp_path)
    archive = tmp_path / "jupyter-sysml-kernel-0.0.1.zip"
    archive.write_bytes(data)
    assert check_pilot.download(release, tmp_path) == archive


def test_download_refuses_a_wrong_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release, _ = _release(tmp_path)

    def fake_retrieve(url: str, path: Path) -> None:
        Path(path).write_bytes(b"changed")

    monkeypatch.setattr(check_pilot.urllib.request, "urlretrieve", fake_retrieve)
    with pytest.raises(check_pilot.SetupError, match="SHA-256 hash"):
        check_pilot.download(release, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_unpack_finds_the_jar_and_the_library(tmp_path: Path) -> None:
    archive = tmp_path / "kernel.zip"
    with zipfile.ZipFile(archive, "w") as content:
        content.writestr("sysml/jupyter-sysml-kernel-0.0.1-all.jar", b"")
        content.writestr("sysml.library/Kernel Libraries/Base.kerml", b"")
    jar, library = check_pilot.unpack(archive, tmp_path / "kernel")
    assert jar == tmp_path / "kernel/sysml/jupyter-sysml-kernel-0.0.1-all.jar"
    assert library == tmp_path / "kernel/sysml.library"


def test_find_kernel_needs_one_jar(tmp_path: Path) -> None:
    (tmp_path / "sysml.library").mkdir()
    with pytest.raises(check_pilot.SetupError, match="1 kernel JAR file"):
        check_pilot.find_kernel(tmp_path)


def test_kernel_spec_has_no_api_base_path(tmp_path: Path) -> None:
    jar = tmp_path / "k.jar"
    library = tmp_path / "sysml.library"
    check_pilot.write_kernel_spec(tmp_path, "java", jar, library)
    spec = json.loads((tmp_path / "sysml-pilot/kernel.json").read_text(encoding="utf-8"))
    assert spec["argv"][:4] == ["java", "-cp", str(jar), "org.omg.sysml.jupyter.kernel.ISysML"]
    assert "ISYSML_API_BASE_PATH" not in spec["env"]
    assert spec["env"]["ISYSML_LIBRARY_PATH"].startswith(str(library))
