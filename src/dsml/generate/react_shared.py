# trace: PRD-APP-202
"""The shared layer of the React generator.

The generator calls `shared_files` for each `react` application. The
function gives the files in `src/shared/`: `api/client.gen.ts`,
`auth/amplify.gen.ts`, `config/runtime-config.gen.ts` and the shadcn/ui
components in `ui/`. Story #167 added the frame of the function. Story #169
writes its files.
"""

from dsml.generate.react_common import ReactContext
from dsml.generate.writer import OutputFile


# trace: PRD-APP-202
def shared_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the layer `shared` of one application."""
    del context
    return []
