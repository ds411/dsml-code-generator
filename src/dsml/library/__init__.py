# trace: PRD-DSML-001, PRD-DSML-006, PRD-CORE-048
"""The DSML library: the SysML v2 model library package `DSML`.

The toolchain package contains the library source, so a model needs no
download (PRD-DSML-006). The IR adapter parses the library together with the
files of the model.
"""

from importlib import resources

LIBRARY_FILE = "DSML.sysml"
"""The name of the library source file in the package."""

# trace: PRD-DSML-056
LIBRARY_VERSION = "1.0.0"
"""The semantic version of the library. `@DsmlVersion` in the source must agree."""


# trace: PRD-DSML-006
def library_text() -> str:
    """Read the library source from the package data."""
    return resources.files(__name__).joinpath(LIBRARY_FILE).read_text(encoding="utf-8")


def library_document() -> tuple[str, str]:
    """Give the library as a (name, text) pair for `Engine.parse_texts()`.

    The name is relative, so a diagnostic does not contain an absolute path
    (PRD-CORE-033).
    """
    return (f"dsml/{LIBRARY_FILE}", library_text())
