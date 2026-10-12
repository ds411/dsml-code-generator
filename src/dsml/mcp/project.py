# trace: PRD-AI-014
"""The project folder of the MCP server.

The user gives the project folder when the server starts. The MCP tools
operate only in this folder (Q70). Each tool must get each path through
`Project.path`, so the server refuses a path outside the folder.
"""

from dataclasses import dataclass
from pathlib import Path

from dsml.errors import ToolchainError


# trace: PRD-AI-014
@dataclass(frozen=True)
class Project:
    """The project folder of the MCP server."""

    root: Path
    """The absolute path of the project folder, with no symbolic link."""

    @classmethod
    def open(cls, folder: Path) -> Project:
        """Give the project of `folder`. The folder must exist."""
        if not folder.is_dir():
            raise ToolchainError(f"The project folder {folder} does not exist.")
        return cls(folder.resolve())

    def path(self, text: str | Path) -> Path:
        """Give the absolute path of `text` in the project folder.

        A relative path starts at the project folder. The function follows
        symbolic links. If the path is not in the project folder, the
        function raises `ToolchainError`.
        """
        path = (self.root / text).resolve()
        if not path.is_relative_to(self.root):
            raise ToolchainError(f'The path "{text}" is not in the project folder.')
        return path
