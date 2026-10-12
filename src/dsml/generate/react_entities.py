# trace: PRD-APP-202
"""The entities layer of the React generator.

The generator calls `entities_files` for each `react` application. The
function gives the files in `src/entities/`: the TypeScript types, the Zod
schemas and the query options of each entity. Story #167 added the frame of
the function. Story #168 writes its files.
"""

from dsml.generate.react_common import ReactContext
from dsml.generate.writer import OutputFile


# trace: PRD-APP-202
def entities_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the layer `entities` of one application."""
    del context
    return []
