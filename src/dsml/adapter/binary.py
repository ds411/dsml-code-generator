# trace: PRD-CORE-049, PRD-CORE-019, PRD-TOP-004
"""Check the SHA-256 hash of `sysml-grpc` before each start.

The `opensysml` client finds the binary in this sequence: `OPENSYSML_BINARY`,
the cache file, a download, `PATH`. The client checks the hash of a download
only. This module checks the hash of the binary from each source, before the
client starts it. The expected hashes are in `src/dsml/versions.toml`.

Run the module to get and check the binary before the work:

    python -m dsml.adapter.binary

After this step, validation and generation do not use the network.
"""

import hashlib
import platform
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import opensysml
import opensysml.binary
import opensysml.connection

from dsml import versions
from dsml.errors import ToolchainError

# The prefix of the baseline items with the expected hashes. The suffix is the
# platform of the release asset, for example "linux-amd64".
HASH_ITEM_PREFIX = "sysml-grpc-sha256-"
_ASSET_PREFIX = "sysml-grpc-"
_CHUNK = 1024 * 1024

type Resolver = Callable[..., str]


# trace: PRD-CORE-049
class BinaryHashError(ToolchainError):
    """`sysml-grpc` does not have the expected SHA-256 hash.

    The command stops with exit code 2.
    """


# trace: PRD-CORE-049
def platform_name() -> str:
    """Give the platform of the release asset, for example "linux-amd64".

    For a platform that OpenSysML does not release, give the names of
    Python, for example "freebsd-x86_64".
    """
    client: Any = opensysml.binary
    try:
        asset = str(client.release_asset_name())
    except ConnectionError:
        return f"{platform.system().lower()}-{platform.machine().lower()}"
    return asset.removeprefix(_ASSET_PREFIX)


# trace: PRD-CORE-049
def expected_hash(name: str, baseline: dict[str, versions.Pin] | None = None) -> str:
    """Give the expected SHA-256 hash of `sysml-grpc` for the platform `name`."""
    pins = versions.load_baseline() if baseline is None else baseline
    pin = pins.get(f"{HASH_ITEM_PREFIX}{name}")
    if pin is None or pin.value is None:
        supported = sorted(
            item.removeprefix(HASH_ITEM_PREFIX)
            for item in pins
            if item.startswith(HASH_ITEM_PREFIX)
        )
        raise BinaryHashError(
            f"The toolchain has no SHA-256 hash of sysml-grpc for the platform {name}. "
            f"Use one of these platforms: {', '.join(supported)}."
        )
    return pin.value


def file_hash(path: Path) -> str:
    """Give the SHA-256 hash of a file as hexadecimal text."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


# trace: PRD-CORE-049, PRD-CORE-019
def check_binary(
    path: Path, name: str | None = None, baseline: dict[str, versions.Pin] | None = None
) -> str:
    """Make sure that the binary at `path` has the expected SHA-256 hash.

    `name` is the platform. Without `name`, the function finds the platform.
    The function gives the hash.
    """
    expected = expected_hash(platform_name() if name is None else name, baseline)
    try:
        actual = file_hash(path)
    except OSError as error:
        raise BinaryHashError(f"Cannot read sysml-grpc at {path}: {error.strerror}.") from None
    if actual != expected:
        raise BinaryHashError(
            f"sysml-grpc at {path} has the SHA-256 hash {actual}. "
            f"The toolchain must use a binary with the hash {expected}. "
            "Remove the binary, or correct OPENSYSML_BINARY or PATH. "
            "Then run: python -m dsml.adapter.binary"
        )
    return actual


# trace: PRD-CORE-049
def checked(resolve: Resolver) -> Resolver:
    """Give a resolver that checks the hash of the binary that `resolve` finds."""

    def resolve_and_check(*args: Any, **kwargs: Any) -> str:
        path = resolve(*args, **kwargs)
        check_binary(Path(path))
        return path

    resolve_and_check.dsml_checked = True  # pyright: ignore[reportFunctionMemberAccess]
    return resolve_and_check


# trace: PRD-CORE-049
def install_hash_check() -> None:
    """Make the client check the hash of `sysml-grpc` before each start.

    The client finds the binary with `ensure_binary()` immediately before it
    starts the child process. The function puts a resolver that checks the
    hash in place of `ensure_binary()` one time.
    """
    module: Any = opensysml.connection
    if not hash_check_installed():
        module.ensure_binary = checked(module.ensure_binary)


def hash_check_installed() -> bool:
    """True if the client checks the hash of `sysml-grpc` before each start."""
    module: Any = opensysml.connection
    return bool(getattr(module.ensure_binary, "dsml_checked", False))


# trace: PRD-CORE-049, PRD-TOP-004
def fetch_binary() -> Path:
    """Get `sysml-grpc` of the pinned version and check its hash.

    If the cache has no binary, the client downloads it. Then a start does
    not use the network.
    """
    pinned = versions.pinned_version("opensysml")
    client: Any = opensysml.binary
    try:
        path = Path(str(client.ensure_binary(version=f"v{pinned}")))
    except (opensysml.OpenSysMLError, ConnectionError) as error:
        raise ToolchainError(f"Cannot get sysml-grpc: {error}") from None
    check_binary(path)
    return path


def main() -> int:
    """Get and check `sysml-grpc`. Give exit code 0 or 2."""
    try:
        path = fetch_binary()
    except ToolchainError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"sysml-grpc: {path}")
    print(f"sha256: {file_hash(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
