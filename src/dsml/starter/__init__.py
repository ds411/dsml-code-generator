# trace: PRD-CORE-001, PRD-CORE-044, PRD-DSML-008, PRD-DSML-056
"""The starter files of `dsml init`: a configuration file and a model.

The starter files of each target are package data in the folder
`dsml/starter/<target>/`. They are create-once files. The developer owns them
after `dsml init` writes them.

The starter model imports the DSML library with `private import DSML::*;`
(PRD-DSML-008) and gives the version of the library with `@DsmlVersion`
(PRD-DSML-056). It has one stakeholder, one need and one requirement.

The starter model of the target `react` also has a FastAPI application and a
React application that calls it (PRD-DSML-030, PRD-DSML-031, PRD-DSML-039).
It also has the infrastructure and the environments, because the validation
rules need them. The model validates with no finding, and `dsml generate`
writes the two projects.
"""

from importlib import resources
from typing import Final

TARGETS: Final = ("fastapi", "react")
"""The targets that `dsml init --target` accepts. M11 adds Next.js."""

DEFAULT_TARGET: Final = "fastapi"
"""The target of `dsml init` if the command line gives no `--target`."""

CONFIG_FILE: Final = "dsml.toml"
"""The name of the starter configuration file in the package data."""

MODEL_FILE: Final = "model/model.sysml"
"""The path of the starter model, relative to the folder of the configuration file."""


# trace: PRD-CORE-001, PRD-DSML-030, PRD-DSML-031, PRD-DSML-039
def starter_files(target: str) -> dict[str, bytes]:
    """Give the bytes of each starter file of a target, by its path in the package data.

    The paths use "/" as the separator. The path of the configuration file is
    `CONFIG_FILE`.
    """
    if target not in TARGETS:
        raise ValueError(f'The target "{target}" has no starter files.')
    folder = resources.files(__name__).joinpath(target)
    return {
        path: folder.joinpath(*path.split("/")).read_bytes() for path in (CONFIG_FILE, MODEL_FILE)
    }
