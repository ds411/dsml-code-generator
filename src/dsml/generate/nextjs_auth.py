# trace: PRD-APP-007, PRD-APP-008, PRD-APP-011, PRD-APP-322, PRD-APP-323, PRD-APP-324
"""The authentication of the Next.js generator (story #183).

The Next.js generator (`dsml.generate.nextjs`) calls the function
`auth_files` for each `nextjs` application. The function gives these files:

- `src/shared/auth/amplify.gen.ts`: the configuration of Amplify Auth in the
  browser, with Cognito managed login, the authorization code flow and PKCE
  (PRD-APP-007). The option `ssr` of Amplify keeps the tokens in cookies
  (PRD-APP-322). The callback path, the logout path and the scopes are the
  values of the app client of the user directory (PRD-IAC-019).
- `src/shared/auth/access.gen.ts`: the role check of PRD-APP-008.
- `src/shared/auth/login-page.gen.tsx` and `callback-page.gen.tsx`: the
  client components of the login page and of the callback page.
- `src/shared/auth/session.server.gen.ts`: the session on the server
  through the Amplify adapter, and the function `authorize` that gives
  HTTP 401 or HTTP 403 with problem details (PRD-APP-008, PRD-APP-324).
- The public API files of the segment `src/shared/auth`.
- `app/auth/login/page.tsx` and `app/auth/callback/page.tsx`: the route
  files of the two pages (PRD-APP-302).
- `proxy.ts`: the request interceptor (PRD-APP-323). It sends a request
  for the page of a view that needs a session to the login page. If each
  view is public, the generator does not write the file.

No file contains an environment value or a secret value. The values of the
user pool come from the environment at run time (PRD-APP-011,
PRD-APP-325).
"""

from typing import Final

from dsml.errors import ToolchainError
from dsml.generate.fastapi_openapi import PROBLEM_MEDIA_TYPE
from dsml.generate.fastapi_slices import is_public
from dsml.generate.infrastructure.modules import CALLBACK_PATH, LOGOUT_PATH
from dsml.generate.names import kebab_case
from dsml.generate.react_common import ReactContext, public_api_files
from dsml.generate.react_pages import KEY_PARAMETER, views_of
from dsml.generate.react_shared import SCOPES
from dsml.generate.typescript_symbols import typescript_symbols
from dsml.generate.writer import OutputFile
from dsml.ir.model import Element, EnumValue, ReferenceValue

SEGMENT: Final = "src/shared/auth"
"""The segment of the authentication."""

PROXY: Final = "proxy.ts"
"""The request interceptor. The pinned Next.js version uses this name (PRD-APP-323)."""

LOGIN_PATH: Final = "/auth/login"
"""The path of the page that starts the login."""

RETURN_PARAMETER: Final = "next"
"""The query parameter of the login page that gives the path after the login."""

RETURN_KEY: Final = "dsml.auth.return-path"
"""The key in the session storage of the browser of the path after the login."""

# The modules of the segment and their templates. The server-only module is
# in `index.server.ts` (PRD-APP-305).
_MODULES: Final = {
    "access.gen": "nextjs/auth/access.gen.ts.j2",
    "amplify.gen": "nextjs/auth/amplify.gen.ts.j2",
    "callback-page.gen": "nextjs/auth/callback-page.gen.tsx.j2",
    "login-page.gen": "nextjs/auth/login-page.gen.tsx.j2",
}
_SERVER_MODULES: Final = {"session.server.gen": "nextjs/auth/session.server.gen.ts.j2"}

# The route file of each page of the authentication and its component.
_PAGES: Final = {
    f"app{CALLBACK_PATH}/page.tsx": "CallbackPage",
    f"app{LOGIN_PATH}/page.tsx": "LoginPage",
}


# trace: PRD-APP-007, PRD-APP-008, PRD-APP-011, PRD-APP-302, PRD-APP-305, PRD-APP-322
# trace: PRD-APP-323, PRD-APP-324, PRD-TRACE-005
def auth_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the authentication of one application."""
    elements = context.elements
    data: dict[str, object] = {
        "callback_path": CALLBACK_PATH,
        "logout_path": LOGOUT_PATH,
        "login_path": LOGIN_PATH,
        "return_parameter": RETURN_PARAMETER,
        "return_key": RETURN_KEY,
        "scopes": SCOPES,
        "problem_media_type": PROBLEM_MEDIA_TYPE,
    }
    files: list[OutputFile] = []
    for module, template in sorted({**_MODULES, **_SERVER_MODULES}.items()):
        extension = ".tsx" if template.endswith(".tsx.j2") else ".ts"
        file = context.generated_file(f"{SEGMENT}/{module}{extension}", template, data, elements)
        symbols = typescript_symbols(file.content, elements)
        files.append(OutputFile(file.path, file.content, file.kind, file.part, symbols))
    files.extend(
        public_api_files(context, SEGMENT, list(_MODULES), elements, list(_SERVER_MODULES))
    )
    files.extend(
        context.generated_file(
            path, "nextjs/auth/page-route.tsx.j2", {"component": component}, elements
        )
        for path, component in sorted(_PAGES.items())
    )
    proxy = proxy_file(context)
    if proxy is not None:
        files.append(proxy)
    return files


# trace: PRD-APP-009, PRD-APP-221, PRD-APP-320, PRD-APP-323
def protected_routes(context: ReactContext) -> dict[str, tuple[str, ...]]:
    """Give the route pattern of each view that needs a session, with its identity.

    The routes are the paths of PRD-APP-221: `/<entities>` for a list view,
    `/<entities>/:id` for a detail view and `/<operation>` for a form view.
    The name comes from the element of the application that exposes the
    entity or the operation. The pattern has the form of the matcher of
    Next.js: the key of a detail view is the parameter `:id`.
    """
    application = context.application
    exposed = [
        item
        for item in context.ir.elements
        if item.kind == "Exposed" and item.owner == application.identity
    ]
    routes: dict[str, tuple[str, ...]] = {}
    for view in views_of(context.ir, application):
        if is_public(view):
            continue
        kind = _view_value(view, "kind")
        reference = _view_value(view, "operation" if kind == "form" else "entity")
        found = sorted(item.name for item in exposed if reference in item.types)
        if not found:
            raise ToolchainError(
                f"The view {view.name} of the application {application.name} refers to "
                f"{reference}, but the application does not expose it. Expose the "
                "element in the application."
            )
        path = f"/{kebab_case(found[0])}"
        routes[f"{path}/:{KEY_PARAMETER}" if kind == "detail" else path] = (view.identity,)
    return dict(sorted(routes.items()))


def _view_value(view: Element, name: str) -> str | None:
    """Give the literal or the target of an attribute of a view."""
    for item in view.attributes:
        if item.name == name and isinstance(item.value, EnumValue):
            return item.value.literal
        if item.name == name and isinstance(item.value, ReferenceValue):
            return item.value.target
    return None


# trace: PRD-APP-323, PRD-TRACE-005
def proxy_file(context: ReactContext) -> OutputFile | None:
    """Give the request interceptor, or None if no view needs a session."""
    routes = protected_routes(context)
    if not routes:
        return None
    elements = [*context.elements, *(item for identities in routes.values() for item in identities)]
    return context.generated_file(
        PROXY, "nextjs/auth/proxy.ts.j2", {"matcher": list(routes)}, elements
    )
