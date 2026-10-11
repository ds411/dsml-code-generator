"""The command line interface of the toolchain: the command `dsml`."""

import argparse
import sys
from collections.abc import Sequence
from importlib import metadata

from dsml import versions
from dsml.errors import ToolchainError

PROG = "dsml"


# trace: PRD-TOP-002, PRD-CORE-001
def build_parser() -> argparse.ArgumentParser:
    """Make the argument parser of the command `dsml`."""
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Validate a DSML model, generate code from it and trace it.",
        allow_abbrev=False,
        color=False,
    )
    subcommands = parser.add_subparsers(dest="command", metavar="<subcommand>", required=True)
    subcommands.add_parser(
        "version",
        help="write the versions of the toolchain and of OpenSysML",
        description="Write the versions of the toolchain and of OpenSysML.",
        allow_abbrev=False,
        color=False,
    )
    return parser


def toolchain_version() -> str:
    """Give the version of the installed toolchain package."""
    return metadata.version(PROG)


# trace: PRD-CORE-001
def run_version() -> int:
    """Write the versions, one line for each component."""
    lines = [
        f"toolchain: {toolchain_version()}",
        f"OpenSysML: {versions.pinned_version('opensysml')}",
    ]
    sys.stdout.write("".join(f"{line}\n" for line in lines))
    return 0


# trace: PRD-TOP-002, PRD-CORE-002, PRD-CORE-019
def main(argv: Sequence[str] | None = None) -> int:
    """Run the command `dsml` and give its exit code.

    A `ToolchainError`, for example a different version of `sysml-grpc`, gives
    exit code 2 and a message on standard error, not a traceback.
    """
    args = build_parser().parse_args(argv)
    try:
        return run_command(args.command)
    except ToolchainError as error:
        sys.stderr.write(f"{PROG}: error: {error}\n")
        return 2


def run_command(command: str) -> int:
    """Run one subcommand and give its exit code."""
    match command:
        case "version":
            return run_version()
        case _:
            raise AssertionError(f"Unknown subcommand: {command}")
