# trace: PRD-APP-202
"""The widgets layer of the React generator.

The generator calls `widgets_files` for each `react` application. The
function gives the files in `src/widgets/`: the table of each list view and
the details of each detail view. Story #167 added the frame of the function.
Story #173 writes its files.
"""

from dsml.generate.react_common import ReactContext
from dsml.generate.writer import OutputFile


# trace: PRD-APP-202
def widgets_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the layer `widgets` of one application."""
    del context
    return []
