# trace: PRD-AI-015
"""MCP resources: the DSML reference, the rule catalog and the example models.

The server has these resources:

| URI | Name | Contents |
| --- | --- | --- |
| `dsml://reference/keywords` | `keywords` | The DSML keywords, their forms and attributes. |
| `dsml://reference/rules` | `rules` | The rule catalog of the validator. |
| `dsml://reference/commands` | `commands` | The subcommands of `dsml` and their options. |
| `dsml://reference/examples` | `examples` | The example models with their keywords. |
| `dsml://reference/patterns` | `patterns` | A short model pattern for each layer. |
| `dsml://examples/<target>` | `example-<target>` | The starter model of the target. |

Each resource of the reference is the text of a reference file in a skill
folder of the package. Thus the resources and the skills always agree (Q68,
Q69). The example models are the starter models of the package.
"""

from dataclasses import dataclass
from importlib import resources
from typing import Any, Final

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.resources import TextResource

from dsml import starter
from dsml.mcp.project import Project

SKILLS_PACKAGE: Final = "dsml.skills"
"""The package that contains the skill folders."""

MARKDOWN: Final = "text/markdown"
"""The MIME type of a reference file."""

SYSML: Final = "text/plain"
"""The MIME type of a model. SysML v2 text has no registered MIME type."""


@dataclass(frozen=True)
class ReferenceFile:
    """One resource of the reference: a reference file in a skill folder."""

    name: str
    """The name of the resource and of the file `references/<name>.md`."""
    skill: str
    """The skill folder that contains the file."""
    description: str


# trace: PRD-AI-015
REFERENCE: Final[tuple[ReferenceFile, ...]] = (
    ReferenceFile(
        "keywords",
        "dsml-modeling",
        "Each DSML keyword with its layer, its form and its attributes. Also the enumerations.",
    ),
    ReferenceFile(
        "rules",
        "dsml-modeling",
        "Each validation rule with its ID, severity, message and correction.",
    ),
    ReferenceFile(
        "commands",
        "dsml-cli",
        "Each subcommand of the dsml CLI and its options. Each MCP tool has the name "
        "of a subcommand.",
    ),
    ReferenceFile(
        "examples",
        "dsml-modeling",
        "The example models of the toolchain package, with the keywords that they use.",
    ),
    ReferenceFile(
        "patterns",
        "dsml-modeling",
        "A short model pattern for each layer of a DSML model. Start a new model here.",
    ),
)
"""The resources of the reference, in the order of the list of resources."""


def reference_uri(name: str) -> str:
    """Give the URI of the resource of the reference file `references/<name>.md`."""
    return f"dsml://reference/{name}"


def example_uri(target: str) -> str:
    """Give the URI of the resource of the starter model of a target."""
    return f"dsml://examples/{target}"


# trace: PRD-AI-015
def reference_text(file: ReferenceFile) -> str:
    """Give the text of a reference file in its skill folder of the package."""
    path = resources.files(SKILLS_PACKAGE).joinpath(file.skill, "references", f"{file.name}.md")
    return path.read_bytes().decode("utf-8")


# trace: PRD-AI-015
def example_text(target: str) -> str:
    """Give the text of the starter model of a target."""
    return starter.starter_files(target)[starter.MODEL_FILE].decode("utf-8")


# trace: PRD-AI-015
def register(server: MCPServer[Any], project: Project) -> None:
    """Add the resources of the reference and the example models to the server.

    The resources do not read the project folder. They are the same for each project.
    """
    for file in REFERENCE:
        server.add_resource(
            TextResource(
                uri=reference_uri(file.name),
                name=file.name,
                title=f"DSML reference: {file.name}",
                description=file.description,
                mime_type=MARKDOWN,
                text=reference_text(file),
            )
        )
    for target in starter.TARGETS:
        server.add_resource(
            TextResource(
                uri=example_uri(target),
                name=f"example-{target}",
                title=f"Starter model of the target {target}",
                description=f"The model that dsml init --target {target} writes in "
                f"{starter.MODEL_FILE}. The model validates with no finding.",
                mime_type=SYSML,
                text=example_text(target),
            )
        )
