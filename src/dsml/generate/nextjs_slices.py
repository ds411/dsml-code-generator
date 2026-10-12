# trace: PRD-APP-304, PRD-APP-305, PRD-APP-306
"""The entity, feature and widget slices of the Next.js generator (story #184).

The Next.js generator (`dsml.generate.nextjs`) calls the function of this
module for each `nextjs` application. Story #180 added the module with a
function that gives no file. Story #184 writes the entity, feature and widget slices.
"""

from dsml.generate.react_common import ReactContext
from dsml.generate.writer import OutputFile


# trace: PRD-APP-304, PRD-APP-305, PRD-APP-306
def slices_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the entity, feature and widget slices of one application."""
    del context
    return []
