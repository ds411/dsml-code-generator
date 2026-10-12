# trace: PRD-APP-007, PRD-APP-010, PRD-APP-011, PRD-APP-014, PRD-APP-202, PRD-APP-212
# trace: PRD-APP-227, PRD-APP-230, PRD-APP-231, PRD-APP-232, PRD-APP-233, PRD-CORE-048
"""The shared layer of the React generator.

The generator calls `shared_files` for each `react` application. The
function gives the files in `src/shared/`. The layer `shared` has no
slices. Each segment has a public API: a generated `index.gen.ts` and a
create-once `index.ts` (PRD-APP-204).

- `config/runtime-config.gen.ts`: read `/config.json` before the first
  render (PRD-APP-010, PRD-APP-230). The file has the keys that the
  deployment pipeline writes (`dsml.generate.pipelines.deploy`).
- `auth/amplify.gen.ts`: configure Amplify Auth from the runtime
  configuration, with Cognito managed login and PKCE (PRD-APP-007,
  PRD-APP-231). The callback path, the logout path and the scopes are
  the values of the app client of the user directory (PRD-IAC-019).
- `api/client.gen.ts`: the function `apiRequest`. It adds the access token
  as a bearer token (PRD-APP-232) and converts a problem details response
  to an error with its `title` and `detail` (PRD-APP-014, PRD-APP-227).
- `ui/` and `lib/utils.ts`: the shadcn/ui components and their helper `cn`,
  from the pinned copy in the toolchain package (PRD-APP-212,
  PRD-CORE-048). These are create-once files: a developer owns them.

No file contains an environment value or a secret value. The application
reads all environment values from `/config.json` at run time
(PRD-APP-011, PRD-APP-233).
"""

from importlib import resources
from importlib.resources.abc import Traversable
from typing import Final

from dsml.generate.fastapi_openapi import PROBLEM_MEDIA_TYPE
from dsml.generate.infrastructure.modules import CALLBACK_PATH, LOGOUT_PATH
from dsml.generate.pipelines.deploy import CONFIGURATION_KEYS, RUNTIME_CONFIGURATION
from dsml.generate.react_common import SOURCE_FOLDER, ReactContext, public_api_files
from dsml.generate.typescript_symbols import typescript_symbols
from dsml.generate.writer import Kind, OutputFile

LAYER: Final = "shared"
"""The FSD layer of this module."""

FOLDER: Final = f"{SOURCE_FOLDER}/{LAYER}"
"""The folder of the layer in the project."""

SCOPES: Final = ("email", "openid", "profile")
"""The OAuth scopes of each app client of a user directory (PRD-IAC-019), sorted."""

SHADCN_FOLDER: Final = "templates/react/shadcn-ui"
"""The folder of the pinned copy of shadcn/ui in the package `dsml` (PRD-CORE-048)."""

SHADCN_SEGMENTS: Final = ("lib", "ui")
"""The folders of the copy. The generator writes each one into the segment with its name."""

# The generated module of each segment and its template, by the segment.
_MODULES: Final = {
    "api": ("client.gen", "react/shared/client.gen.ts.j2"),
    "auth": ("amplify.gen", "react/shared/amplify.gen.ts.j2"),
    "config": ("runtime-config.gen", "react/shared/runtime-config.gen.ts.j2"),
}


# trace: PRD-APP-202, PRD-APP-204, PRD-APP-212, PRD-APP-227, PRD-APP-230, PRD-APP-231
# trace: PRD-APP-232, PRD-CORE-044, PRD-TRACE-005, PRD-TRACE-006
def shared_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the layer `shared` of one application."""
    data: dict[str, object] = {
        "path": f"/{RUNTIME_CONFIGURATION}",
        "keys": CONFIGURATION_KEYS,
        "callback_path": CALLBACK_PATH,
        "logout_path": LOGOUT_PATH,
        "scopes": SCOPES,
        "problem_media_type": PROBLEM_MEDIA_TYPE,
    }
    elements = context.elements
    files: list[OutputFile] = []
    for segment, (module, template) in sorted(_MODULES.items()):
        file = context.generated_file(f"{FOLDER}/{segment}/{module}.ts", template, data, elements)
        symbols = typescript_symbols(file.content, elements)
        files.append(OutputFile(file.path, file.content, file.kind, file.part, symbols))
        files.extend(public_api_files(context, f"{FOLDER}/{segment}", [module], elements))
    for segment in SHADCN_SEGMENTS:
        components = shadcn_files(segment)
        for name, content in components.items():
            path = f"{context.folder}{FOLDER}/{segment}/{name}"
            files.append(OutputFile(path, content, Kind.CREATE_ONCE, context.part))
        modules = [name.rsplit(".", 1)[0] for name in components]
        files.extend(public_api_files(context, f"{FOLDER}/{segment}", modules, elements))
    return files


# trace: PRD-APP-212, PRD-CORE-048
def shadcn_files(segment: str) -> dict[str, bytes]:
    """Give the files of one folder of the pinned copy of shadcn/ui, sorted by name."""
    folder: Traversable = resources.files("dsml").joinpath(SHADCN_FOLDER, segment)
    return {
        item.name: item.read_bytes()
        for item in sorted(folder.iterdir(), key=lambda item: item.name)
        if item.is_file() and item.name.endswith((".ts", ".tsx"))
    }
