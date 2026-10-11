# trace: PRD-TRACE-018, PRD-TOP-004
"""The model commit of the trace reports.

The model commit is the commit `HEAD` of the local Git repository of the
model. The function runs the local command `git`. It does not use the network
(PRD-TOP-004). If there is no commit, the report gives a text that tells why.
"""

import subprocess
from pathlib import Path
from typing import Final

NOT_IN_REPOSITORY: Final = "none: the folder is not in a Git repository"
NO_COMMIT: Final = "none: the Git repository has no commit"
NO_GIT: Final = "none: the command git is not available"


# trace: PRD-TRACE-018
def model_commit(root: Path) -> str:
    """Give the full hash of the commit `HEAD` of the Git repository of the folder.

    If the folder is not in a Git repository, if the repository has no
    commit, or if there is no command `git`, give a text that starts with
    "none:" and tells why.
    """
    head = _git(root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if head is None:
        return NO_GIT
    if head.returncode == 0:
        return head.stdout.strip()
    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    if inside is None or inside.returncode != 0:
        return NOT_IN_REPOSITORY
    return NO_COMMIT


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    """Run a local `git` command in the folder. Give `None` if there is no command `git`."""
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError:
        return None
