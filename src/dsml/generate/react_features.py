# trace: PRD-APP-202
"""The features layer of the React generator.

The generator calls `features_files` for each `react` application. The
function gives the files in `src/features/`: the mutation and the form or
the button of each operation. Story #167 added the frame of the function.
Story #172 writes its files.
"""

from dsml.generate.react_common import ReactContext
from dsml.generate.writer import OutputFile


# trace: PRD-APP-202
def features_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the layer `features` of one application."""
    del context
    return []
