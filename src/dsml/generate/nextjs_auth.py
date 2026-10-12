# trace: PRD-APP-322, PRD-APP-323, PRD-APP-324
"""The authentication of the Next.js generator (story #183).

The Next.js generator (`dsml.generate.nextjs`) calls the function of this
module for each `nextjs` application. Story #180 added the module with a
function that gives no file. Story #183 writes the authentication.
"""

from dsml.generate.react_common import ReactContext
from dsml.generate.writer import OutputFile


# trace: PRD-APP-322, PRD-APP-323, PRD-APP-324
def auth_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the authentication of one application."""
    del context
    return []
