# trace: PRD-APP-330, PRD-APP-331, PRD-APP-332
"""The Drizzle schema and migrations of the Next.js generator (story #182).

The Next.js generator (`dsml.generate.nextjs`) calls the function of this
module for each `nextjs` application. Story #180 added the module with a
function that gives no file. Story #182 writes the Drizzle schema and migrations.
"""

from dsml.generate.react_common import ReactContext
from dsml.generate.writer import OutputFile


# trace: PRD-APP-330, PRD-APP-331, PRD-APP-332
def database_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the Drizzle schema and migrations of one application."""
    del context
    return []
