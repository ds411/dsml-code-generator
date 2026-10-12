# trace: PRD-APP-314, PRD-APP-320, PRD-APP-321
"""The pages and navigation of the Next.js generator (story #188).

The Next.js generator (`dsml.generate.nextjs`) calls the function of this
module for each `nextjs` application. Story #180 added the module with a
function that gives no file. Story #188 writes the pages and navigation.
"""

from dsml.generate.react_common import ReactContext
from dsml.generate.writer import OutputFile


# trace: PRD-APP-314, PRD-APP-320, PRD-APP-321
def pages_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the pages and navigation of one application."""
    del context
    return []
