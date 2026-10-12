# trace: PRD-CORE-052
"""Write the release notes of one version from `CHANGELOG.md`.

The release workflow `.github/workflows/release.yml` runs this script. The
notes are the text of the section `## <version>`, with no heading. Run it from
the root of the repository:

    uv run python scripts/release_notes.py 0.1.0 --output notes.md

Exit codes:

- 0: the script wrote the notes.
- 2: `CHANGELOG.md` has no section for the version, or the section is empty.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
SEMANTIC_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


# trace: PRD-CORE-052
def release_notes(text: str, version: str) -> str:
    """Give the text of the section `## <version>` of the changelog.

    Raise `ValueError` if the version is not a semantic version, or if the
    section is missing or empty.
    """
    if not SEMANTIC_VERSION.fullmatch(version):
        raise ValueError(f"{version} is not a semantic version <major>.<minor>.<patch>.")
    match = re.search(
        rf"^## {re.escape(version)}\n(.*?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL
    )
    if match is None:
        raise ValueError(f"CHANGELOG.md has no section '## {version}'. Add the section.")
    notes = match.group(1).strip()
    if not notes:
        raise ValueError(f"The section '## {version}' of CHANGELOG.md is empty.")
    return notes + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write the release notes. Give exit code 0 or 2."""
    parser = argparse.ArgumentParser(description="Write the release notes of one version.")
    parser.add_argument("version", help="the version, for example 0.1.0")
    parser.add_argument("--output", type=Path, help="the file of the notes (default: stdout)")
    args = parser.parse_args(argv)
    try:
        notes = release_notes(CHANGELOG.read_text(encoding="utf-8"), args.version)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.output is None:
        sys.stdout.write(notes)
    else:
        args.output.write_text(notes, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
