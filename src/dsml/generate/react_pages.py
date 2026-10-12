# trace: PRD-APP-202
"""The pages layer of the React generator.

The generator calls `pages_files` for each `react` application. The function
gives the files in `src/pages/`: the page of each view. Story #167 added the
frame of the function. Story #174 writes its files.
"""

from dsml.generate.react_common import ReactContext
from dsml.generate.writer import OutputFile


# trace: PRD-APP-202
def pages_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the layer `pages` of one application."""
    del context
    return []
