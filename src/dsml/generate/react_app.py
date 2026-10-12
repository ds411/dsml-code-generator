# trace: PRD-APP-202
"""The app layer of the React generator.

The generator calls `app_files` for each `react` application. The function
gives the files in `src/app/`: the route tree, the navigation and the
providers. Story #167 added the frame of the function. Story #174 writes its
files.
"""

from dsml.generate.react_common import ReactContext
from dsml.generate.writer import OutputFile


# trace: PRD-APP-202
def app_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the layer `app` of one application."""
    del context
    return []
