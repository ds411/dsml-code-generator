# trace: PRD-TOP-013, PRD-AI-007, PRD-CORE-028
"""Write the reference pages of the user guide.

Story #240 added this script. It writes these pages in
`docs/guide/reference/` with the module `dsml.assist.reference`:

- `keywords.md`: each DSML keyword.
- `rules.md`: each validation rule, with its correction.
- `commands.md`: each `dsml` subcommand.

The skills and the MCP resources use the same text. Thus the guide, the
skills and the MCP resources always agree with the toolchain (Q68, Q71).
Run this script from the root of the repository after a change of the DSML
library, the rule catalog or the CLI:

    uv run python scripts/write_guide_reference.py

Then examine the differences with `git diff` before you commit them. The
test `tests/test_guide_reference.py` fails if a page is not current.
"""

import argparse
import sys
from pathlib import Path

from dsml.assist.reference import GENERATED_NOTE, part

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "docs" / "guide" / "reference"

PAGES = ("commands", "keywords", "rules")
"""The reference parts that the guide gives, one page for each part."""

PAGE_NOTE = (
    "<!-- The script scripts/write_guide_reference.py writes this page "
    "from the installed toolchain. Do not change it. -->"
)
"""The first line of each reference page."""

BACK_LINK = "[Reference](README.md) | [User guide](../README.md)"
"""The links at the top of each reference page."""


# trace: PRD-TOP-013, PRD-CORE-028
def page(name: str) -> str:
    """Give the text of the reference page of one part.

    The page is the text of the part, with the note of this script and links
    back to the index pages.
    """
    text = part(name)
    if not text.startswith(GENERATED_NOTE + "\n"):
        raise ValueError(f'The reference part "{name}" does not start with the generated note.')
    body = text.removeprefix(GENERATED_NOTE + "\n").replace("This part gives", "This page gives", 1)
    return f"{PAGE_NOTE}\n\n{BACK_LINK}\n{body}"


# trace: PRD-TOP-013, PRD-CORE-028
def pages(folder: Path = FOLDER) -> dict[Path, bytes]:
    """Give the bytes of each reference page in `folder`, sorted by path."""
    return {folder / f"{name}.md": page(name).encode("utf-8") for name in sorted(PAGES)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the reference pages of the user guide.")
    parser.add_argument(
        "--folder",
        type=Path,
        default=FOLDER,
        help="the folder of the reference pages (default: docs/guide/reference)",
    )
    args = parser.parse_args(argv)
    for path, content in pages(args.folder).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        try:
            shown = path.relative_to(ROOT).as_posix()
        except ValueError:
            shown = path.as_posix()
        print(f"Wrote {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
