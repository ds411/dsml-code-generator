# trace: PRD-APP-014, PRD-APP-210, PRD-APP-212, PRD-APP-227, PRD-APP-304, PRD-APP-305
# trace: PRD-APP-306, PRD-APP-314, PRD-APP-321
"""The entity, feature and widget slices of the Next.js generator (story #184).

The Next.js generator (`dsml.generate.nextjs`) calls the function
`slices_files` for each `nextjs` application. The function uses the layer
writers of the React target with the Next.js layout of the context
(PRD-APP-304):

- `src/entities/<entity>/`: the types, the Zod schemas and the query
  options of each exposed entity (`dsml.generate.react_entities`).
- `src/features/<operation>/`: the mutation and the form or the button of
  each operation with a change (`dsml.generate.react_features`). A form is
  a client component with TanStack Form and the Zod schema of its operation
  (PRD-APP-321).
- `src/widgets/<widget>/`: the table and the details of the entities of the
  views (`dsml.generate.react_widgets`).

A `nextjs` application holds its own API, thus the slices come from its own
entities and operations (`api_applications` of `react_entities`). A module
with React hooks starts with the directive `"use client"`.

The slices need two segments of the layer `shared`. This module also writes
them:

- `src/shared/api/client.gen.ts`: the function `apiRequest`. It sends each
  request to a route handler under `/api` on the same origin (PRD-APP-311,
  PRD-APP-314). The browser sends the cookies of the Amplify session
  (PRD-APP-322). A problem details response gives an `ApiError` with its
  `title` and `detail` (PRD-APP-014, PRD-APP-227).
- `src/shared/ui/` and `src/shared/lib/`: the pinned copy of shadcn/ui, as
  create-once files (PRD-APP-212, PRD-CORE-048).

Each slice and each segment has the public API `index.ts`. A slice with a
server-only module also has `index.server.ts` (PRD-APP-305). The modules of
this part are not server-only. The route handler story (#186) writes the
server functions in `src/features/<operation>/api/`.
"""

from typing import Final

from dsml.generate.fastapi_openapi import PROBLEM_MEDIA_TYPE
from dsml.generate.react_common import ReactContext, public_api_files
from dsml.generate.react_entities import entities_files
from dsml.generate.react_features import features_files
from dsml.generate.react_shared import SHADCN_SEGMENTS, shadcn_files
from dsml.generate.react_widgets import widgets_files
from dsml.generate.typescript_symbols import typescript_symbols
from dsml.generate.writer import Kind, OutputFile

API_PREFIX: Final = "/api"
"""The path prefix of the route handlers (PRD-APP-311)."""

API_SEGMENT: Final = "src/shared/api"
"""The segment of the client of the route handlers."""

CLIENT_COMPONENTS: Final = ("alert-dialog.tsx", "field.tsx", "label.tsx", "separator.tsx")
"""The files of the shadcn/ui copy that start with `"use client"` in the source.

The copy has no directive, because the React target has no server
components. `components.json` of the Next.js target has `"rsc": true`, thus
the shadcn CLI keeps the directive. The generator adds it again.
"""

CLIENT_DIRECTIVE: Final = b'"use client";\n\n'
"""The directive of a client component, with the empty line after it."""


# trace: PRD-APP-210, PRD-APP-304, PRD-APP-305, PRD-APP-306, PRD-APP-321
def slices_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the entity, feature and widget slices of one application."""
    files = shared_files(context)
    files.extend(entities_files(context))
    files.extend(features_files(context))
    files.extend(widgets_files(context))
    return files


# trace: PRD-APP-014, PRD-APP-212, PRD-APP-227, PRD-APP-314, PRD-CORE-048, PRD-TRACE-005
def shared_files(context: ReactContext) -> list[OutputFile]:
    """Give the segments `api`, `ui` and `lib` of the layer `shared`."""
    elements = context.elements
    data: dict[str, object] = {
        "api_prefix": API_PREFIX,
        "problem_media_type": PROBLEM_MEDIA_TYPE,
    }
    client = context.generated_file(
        f"{API_SEGMENT}/client.gen.ts", "nextjs/slices/client.gen.ts.j2", data, elements
    )
    symbols = typescript_symbols(client.content, elements)
    files = [OutputFile(client.path, client.content, client.kind, client.part, symbols)]
    files.extend(public_api_files(context, API_SEGMENT, ["client.gen"], elements))
    folder = context.layout.layer_folder("shared")
    for segment in SHADCN_SEGMENTS:
        components = shadcn_files(segment)
        for name, content in components.items():
            if name in CLIENT_COMPONENTS:
                content = CLIENT_DIRECTIVE + content
            path = f"{context.folder}{folder}/{segment}/{name}"
            files.append(OutputFile(path, content, Kind.CREATE_ONCE, context.part))
        modules = [name.rsplit(".", 1)[0] for name in components]
        files.extend(public_api_files(context, f"{folder}/{segment}", modules, elements))
    return files
