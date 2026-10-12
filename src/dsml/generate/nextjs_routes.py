# trace: PRD-APP-310, PRD-APP-311, PRD-APP-312, PRD-APP-313
"""The route handlers and server functions of the Next.js generator (story #186).

The Next.js generator (`dsml.generate.nextjs`) calls the function of this
module for each `nextjs` application. Story #180 added the module with a
function that gives no file. Story #186 writes the route handlers and server functions.
"""

from dsml.generate.react_common import ReactContext
from dsml.generate.writer import OutputFile


# trace: PRD-APP-310, PRD-APP-311, PRD-APP-312, PRD-APP-313
def routes_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the route handlers and server functions of one application."""
    del context
    return []
