# trace: PRD-AI-001, PRD-AI-004, PRD-AI-005, PRD-AI-006
"""The skills for AI agents and the command `dsml skills install`.

Each skill is a folder in this package, in the Agent Skills format: a
`SKILL.md` file and reference files (Q68). The command copies each folder
that has a `SKILL.md` file. Thus a new skill needs no change to a list.

The command owns only the skill folders of this package. In the destination
folder, it replaces each of these folders and does not change a different
file or folder (PRD-AI-005). It copies the bytes of each file, so two runs
write byte-identical files (PRD-AI-006).
"""

import shutil
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath
from typing import Final

from dsml.errors import ToolchainError

DEFAULT_OUTPUT: Final = Path(".claude") / "skills"
"""The destination folder of `dsml skills install` if there is no `--output` (PRD-AI-004)."""

SKILL_FILE: Final = "SKILL.md"
"""The file that each skill folder must have."""

_SKIPPED: Final = frozenset({"__pycache__"})
"""Names in the package that the command does not copy."""


@dataclass(frozen=True)
class Skill:
    """One skill of the package: its folder name and its files."""

    name: str
    files: tuple[tuple[PurePosixPath, bytes], ...]
    """The path of each file in the skill folder and its bytes, sorted by path."""


def _files(folder: Traversable, prefix: PurePosixPath) -> list[tuple[PurePosixPath, bytes]]:
    found: list[tuple[PurePosixPath, bytes]] = []
    for item in folder.iterdir():
        if item.name in _SKIPPED:
            continue
        if item.is_dir():
            found.extend(_files(item, prefix / item.name))
        elif item.is_file():
            found.append((prefix / item.name, item.read_bytes()))
    return found


# trace: PRD-AI-001, PRD-AI-006
def package_skills(source: Traversable | None = None) -> list[Skill]:
    """Give the skills in the folder `source`, sorted by name.

    The default folder is this package. A skill is a folder with a
    `SKILL.md` file.
    """
    folder = resources.files(__name__) if source is None else source
    skills = [
        Skill(item.name, tuple(sorted(_files(item, PurePosixPath()))))
        for item in folder.iterdir()
        if item.is_dir() and item.name not in _SKIPPED and item.joinpath(SKILL_FILE).is_file()
    ]
    return sorted(skills, key=lambda skill: skill.name)


# trace: PRD-AI-004, PRD-AI-005, PRD-AI-006, PRD-CORE-034
def install(output: Path, skills: list[Skill]) -> None:
    """Write each skill into its folder in `output`.

    The function removes the skill folder in `output` if it exists, then
    writes all files of the skill. It does not change a different file or
    folder in `output`.
    """
    try:
        output.mkdir(parents=True, exist_ok=True)
        for skill in skills:
            folder = output / skill.name
            if folder.is_symlink() or folder.is_file():
                folder.unlink()
            elif folder.is_dir():
                shutil.rmtree(folder)
            for path, content in skill.files:
                target = folder.joinpath(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
    except OSError as error:
        name = error.filename or output
        message = f"Cannot write the skill files in {name}: {error.strerror}."
        raise ToolchainError(message) from error
