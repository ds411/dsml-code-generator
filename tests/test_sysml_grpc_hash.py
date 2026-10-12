# trace: PRD-CORE-049, PRD-CORE-019
"""Tests of the SHA-256 check of `sysml-grpc` before each start (story #135).

The tests use a fake binary: a small shell script. The toolchain must stop
before it starts the fake binary.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dsml import versions
from dsml.adapter import binary
from dsml.adapter.binary import BinaryHashError, check_binary, checked, expected_hash

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs" / "model" / "examples"
FAKE_TEXT = b"#!/bin/sh\nexit 1\n"
FAKE_HASH = hashlib.sha256(FAKE_TEXT).hexdigest()
OTHER_HASH = "0" * 64


def _fake_binary(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "sysml-grpc"
    path.write_bytes(FAKE_TEXT)
    path.chmod(0o755)
    return path


def _baseline(sha256: str) -> dict[str, versions.Pin]:
    return versions.load_baseline(
        f'schema = 1\n[sysml-grpc-sha256-linux-amd64]\nvalue = "{sha256}"\n'
    )


def test_baseline_has_a_hash_for_each_platform_of_q50() -> None:
    baseline = versions.load_baseline()
    for name in ("darwin-arm64", "linux-amd64", "linux-arm64"):
        assert len(expected_hash(name, baseline)) == 64


def test_platform_of_ci_has_a_hash() -> None:
    assert expected_hash(binary.platform_name())


def test_correct_hash_passes(tmp_path: Path) -> None:
    path = _fake_binary(tmp_path)
    assert check_binary(path, "linux-amd64", _baseline(FAKE_HASH)) == FAKE_HASH


def test_different_hash_stops_and_gives_the_expected_hash(tmp_path: Path) -> None:
    path = _fake_binary(tmp_path)
    with pytest.raises(BinaryHashError) as raised:
        check_binary(path, "linux-amd64", _baseline(OTHER_HASH))
    assert FAKE_HASH in str(raised.value)
    assert f"must use a binary with the hash {OTHER_HASH}" in str(raised.value)


def test_platform_with_no_hash_stops(tmp_path: Path) -> None:
    path = _fake_binary(tmp_path)
    with pytest.raises(BinaryHashError, match="no SHA-256 hash of sysml-grpc for the platform"):
        check_binary(path, "windows-amd64", _baseline(FAKE_HASH))


def test_missing_binary_stops(tmp_path: Path) -> None:
    with pytest.raises(BinaryHashError, match="Cannot read sysml-grpc"):
        check_binary(tmp_path / "sysml-grpc", "linux-amd64", _baseline(FAKE_HASH))


@pytest.mark.parametrize("source", ["OPENSYSML_BINARY", "cache", "PATH"])
def test_checked_resolver_stops_a_binary_from_each_source(tmp_path: Path, source: str) -> None:
    # The client gives the path of the binary from each source. The check
    # does not depend on the source.
    path = _fake_binary(tmp_path / source)

    def resolve_source(**_: object) -> str:
        return str(path)

    resolve = checked(resolve_source)
    with pytest.raises(BinaryHashError, match=FAKE_HASH):
        resolve(version="v0.9.2")


def test_install_hash_check_is_in_place_after_a_second_call() -> None:
    binary.install_hash_check()
    binary.install_hash_check()
    assert binary.hash_check_installed()


def _validate(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "dsml", "validate", "--date", "2026-10-12"],
        cwd=EXAMPLE,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_stops_a_binary_from_opensysml_binary(tmp_path: Path) -> None:
    path = _fake_binary(tmp_path)
    result = _validate({"OPENSYSML_BINARY": str(path)})
    assert result.returncode == 2
    expected = expected_hash(binary.platform_name())
    assert f"must use a binary with the hash {expected}" in result.stderr


def test_cli_stops_a_binary_from_the_cache(tmp_path: Path) -> None:
    # The client accepts a cache file with a record of the pinned release and
    # of its own hash, with no network. The toolchain must stop it.
    home = tmp_path / "home"
    cache = home / ".opensysml" / "bin"
    _fake_binary(cache)
    record = {
        "version": f"v{versions.pinned_version('opensysml')}",
        "sha256": FAKE_HASH,
        "repo": "Open-MBEE/OpenSysML",
    }
    (cache / "sysml-grpc.json").write_text(json.dumps(record), encoding="utf-8")
    env = {"HOME": str(home), "OPENSYSML_BINARY": ""}
    result = _validate(env)
    assert result.returncode == 2
    assert "has the SHA-256 hash" in result.stderr
    assert FAKE_HASH in result.stderr
