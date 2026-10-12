# trace: PRD-AI-007, PRD-CORE-028, PRD-CORE-030
"""Write the reference files of the skills and the golden files of the reference.

Story #228 added this script. For each folder
`src/dsml/skills/<skill>/references/` with the file `parts.txt`, it writes the
file `<part>.md` of each part that `parts.txt` lists. The module
`dsml.assist.reference` gives the text. A skill folder that does not exist
yet is not an error.

The script also writes the golden file of each part in `tests/golden/assist/`.
Run this script from the root of the repository after a change of the DSML
library, the rule catalog or the CLI:

    uv run python scripts/write_skill_references.py

Then examine the differences with `git diff` before you commit them. The
test `tests/test_assist_reference.py` fails if a file is not current.
"""

import argparse
import sys
from pathlib import Path

from dsml.assist.reference import PARTS, part, skill_reference_files

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "src" / "dsml" / "skills"
GOLDEN = ROOT / "tests" / "golden" / "assist"


def write(path: Path, content: bytes) -> None:
    """Write the file with LF line ends, and tell its path relative to the root."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    try:
        shown = path.relative_to(ROOT).as_posix()
    except ValueError:
        shown = path.as_posix()
    print(f"Wrote {shown}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the reference files of the skills.")
    parser.add_argument(
        "--skills",
        type=Path,
        default=SKILLS,
        help="the folder of the skills (default: src/dsml/skills)",
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=GOLDEN,
        help="the folder of the golden files (default: tests/golden/assist)",
    )
    args = parser.parse_args(argv)
    for name in sorted(PARTS):
        write(args.golden / f"{name}.md", part(name).encode("utf-8"))
    for path, content in skill_reference_files(args.skills).items():
        write(path, content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
