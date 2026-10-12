# trace: PRD-APP-009, PRD-APP-302, PRD-APP-314, PRD-APP-320, PRD-APP-321, PRD-APP-324
# trace: PRD-DSML-032, PRD-DSML-033
"""The pages and navigation of the Next.js generator (story #188).

The Next.js generator (`dsml.generate.nextjs`) calls the function
`pages_files` for each `nextjs` application. The function gives these files:

- `src/_pages/<view>/`: one page slice for each view (PRD-APP-320). The
  page `ui/<view>-page.server.gen.tsx` is a server component. It checks the
  session and the roles of the view (PRD-APP-324). A list page and a detail
  page call the server function of `list` or `read` directly, with no HTTP
  request, and give the data to the query cache of the client
  (PRD-APP-314). A list page with controls and a form page also have a
  client component `ui/<view>-content.gen.tsx` (PRD-APP-321). The slice
  exports the page through `index.server.ts` (PRD-APP-305).
- `app/<route>/page.tsx`: the route file of each view. It re-exports the
  page (PRD-APP-302). The routes have the paths of PRD-APP-221. The key of
  a detail view is the dynamic segment `[id]`.
- `app/page.tsx` and `app/not-found.tsx`: the home page and the "not found"
  page.
- `src/_app/layout/`: the layout of the pages, the navigation, the logout
  button and the status pages. The navigation shows only the views that the
  roles of the user permit (PRD-APP-009, PRD-DSML-032).
- `src/_app/providers/`: the providers of TanStack Query and of the client
  session.
- `src/_app/styles/index.css`: the create-once Tailwind CSS file of
  `components.json`.
- `src/shared/access/`: the role check of a view in a server component and
  the "not permitted" page (PRD-APP-009, PRD-APP-324).

The page slices come from the page slices of the React target
(`dsml.generate.react_pages`). Thus the views, the paths and the errors are
the same for the two targets.
"""

from dataclasses import dataclass
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate.names import camel_case, pascal_case
from dsml.generate.nextjs_routes import array_lines
from dsml.generate.react_common import (
    FsdLayout,
    ReactContext,
    file_name,
    public_api_files,
    server_api_files,
)
from dsml.generate.react_entities import INDENT, PRINT_WIDTH, string_literal
from dsml.generate.react_features import field_label, import_lines
from dsml.generate.react_pages import KEY_PARAMETER, LINK_CLASS, PageSlice, page_slices
from dsml.generate.typescript_symbols import typescript_symbols
from dsml.generate.writer import Kind, OutputFile
from dsml.ir.model import Element, ListValue, ReferenceValue

ACCESS_SEGMENT: Final = "src/shared/access"
"""The segment of the role check of a view and of the "not permitted" page."""

APP_LAYER: Final = "src/_app"
"""The folder of the layer `app` in the Next.js layout (PRD-APP-303)."""

STYLES: Final = f"{APP_LAYER}/styles/index.css"
"""The create-once Tailwind CSS file. `components.json` refers to it."""

RESERVED_SEGMENTS: Final = ("api", "auth", "healthz")
"""The first route segments of the other parts.

These are the route handlers, the auth pages and the health check.
"""

# The template of each generated file of the layer `app`, by the path in the project.
_APP_FILES: Final = {
    f"{APP_LAYER}/layout/app-layout.gen.tsx": "nextjs/pages/app-layout.gen.tsx.j2",
    f"{APP_LAYER}/layout/logout-button.gen.tsx": "nextjs/pages/logout-button.gen.tsx.j2",
    f"{APP_LAYER}/layout/navigation.gen.tsx": "nextjs/pages/navigation.gen.tsx.j2",
    f"{APP_LAYER}/layout/status-pages.gen.tsx": "nextjs/pages/status-pages.gen.tsx.j2",
    f"{APP_LAYER}/providers/app-providers.gen.tsx": "nextjs/pages/app-providers.gen.tsx.j2",
    f"{APP_LAYER}/providers/query-client.gen.ts": "nextjs/pages/query-client.gen.ts.j2",
}

# The route files of the pages that are not views, and their components.
_STATUS_ROUTES: Final = {
    "app/not-found.tsx": "NotFoundPage",
    "app/page.tsx": "HomePage",
}

# The modules of the segment `shared/access` and their templates.
_ACCESS_MODULES: Final = {"not-permitted-page.gen": "nextjs/pages/not-permitted-page.gen.tsx.j2"}
_ACCESS_SERVER_MODULES: Final = {
    "view-access.server.gen": "nextjs/pages/view-access.server.gen.ts.j2"
}


# trace: PRD-APP-221, PRD-APP-314, PRD-APP-320, PRD-APP-321, PRD-APP-324, PRD-DSML-033
@dataclass(frozen=True, slots=True)
class NextPage:
    """The page slice of one view in the Next.js layout."""

    page: PageSlice
    layout: FsdLayout

    @property
    def name(self) -> str:
        return self.page.name

    @property
    def kind(self) -> str:
        return self.page.kind

    @property
    def elements(self) -> list[str]:
        return self.page.elements

    @property
    def folder(self) -> str:
        """The folder of the slice, for example `src/_pages/order-list`."""
        return self.page.folder(self.layout)

    @property
    def component(self) -> str:
        """The name of the page component, for example `OrderListPage`."""
        return self.page.component

    @property
    def server_module(self) -> str:
        """The page module, for example `ui/order-list-page.server.gen`."""
        return f"ui/{file_name(self.name, 'page')}.server.gen"

    @property
    def has_content(self) -> bool:
        """Tell if the page has a client component: a form, or a table with controls."""
        return self.kind == "form" or (self.kind == "list" and self.page.has_actions)

    @property
    def content_file(self) -> str:
        """The client component file with no extension, for example `order-list-content.gen`."""
        return f"{file_name(self.name, 'content')}.gen"

    @property
    def content_component(self) -> str:
        """The name of the client component, for example `OrderListContent`."""
        return f"{pascal_case(self.name)}Content"

    @property
    def path(self) -> str:
        """The route path of the view (PRD-APP-221), for example `/orders/[id]`."""
        return self.page.path.replace(f"${KEY_PARAMETER}", f"[{KEY_PARAMETER}]")

    @property
    def route_file(self) -> str:
        """The route file of the view, for example `app/orders/[id]/page.tsx`."""
        return f"app{self.path}/page.tsx"

    @property
    def title(self) -> str:
        return self.page.title

    @property
    def description(self) -> str | None:
        return self.page.description

    def description_lines(self) -> list[str]:
        return self.page.description_lines()

    def access_lines(self) -> list[str]:
        """Give the lines of the constant `ACCESS`: the attributes `public` and `allowedRoles`."""
        roles = [string_literal(role) for role in self.page.roles]
        lines = ["const ACCESS: Access = {", f"{INDENT}public: {str(self.page.public).lower()},"]
        lines.extend(array_lines(INDENT, "roles: ", roles, ","))
        lines.append("};")
        return lines

    # The server functions of a list page and of a detail page (PRD-APP-314).

    @property
    def operation(self) -> str:
        """The name of the operation that gives the data, for example `listOrder`."""
        entity = self.page.entity
        assert entity is not None
        return camel_case(f"{'list' if self.kind == 'list' else 'read'} {entity.name}")

    @property
    def server_function(self) -> str:
        """The name of the server function, for example `handleListOrder`."""
        return f"handle{pascal_case(self.operation)}"

    @property
    def query_key(self) -> str:
        """The name of the function of the query key, for example `listOrderQueryKey`."""
        return f"{self.operation}QueryKey"

    @property
    def collection(self) -> str:
        """The first segment of the route path, for example `/orders`."""
        return "/" + self.page.path.split("/")[1]

    @property
    def key_value(self) -> str:
        """The expression of the key of a detail page, from the path parameter `id`."""
        return "Number(id)" if self.page.key_type == "number" else "id"

    def import_lines(self) -> list[str]:
        """Give the import statements of the page, in groups with an empty line between."""
        groups: list[list[str]] = [['import "server-only";']]
        if self.kind != "form":
            groups.append(
                import_lines(
                    ["dehydrate", "HydrationBoundary", "noop", "QueryClient"],
                    "@tanstack/react-query",
                )
            )
        internal: list[tuple[str, list[str]]] = []
        if self.kind != "form":
            entity = self.page.entity
            assert entity is not None
            internal.append(
                _import(self.query_key, self.layout.import_path("entities", entity.slice))
            )
            source = self.layout.import_path("features", file_name(self.operation))
            internal.append(_import(self.server_function, f"{source}/index.server"))
        access = self.layout.import_path("shared", "access")
        internal.append(_import("NotPermittedPage", access))
        internal.append(_import("permitsView", f"{access}/index.server"))
        auth = self.layout.import_path("shared", "auth")
        internal.append((auth, [f'import type {{ Access }} from "{auth}";']))
        if not self.has_content and self.page.widget is not None:
            source = self.layout.import_path("widgets", self.page.widget.slice)
            internal.append(_import(self.page.widget.component, source))
        groups.append([line for _, lines in sorted(internal) for line in lines])
        if self.has_content:
            groups.append(import_lines([self.content_component], f"./{self.content_file}"))
        lines: list[str] = []
        for group in groups:
            lines.extend((*([""] if lines else []), *group))
        return lines

    # The client component of a list page or a form page.

    def content_import_lines(self) -> list[str]:
        """Give the import statements of the client component."""
        external: list[str] = []
        if self.kind == "list" and self.page.detail_path is not None:
            external.append('import Link from "next/link";')
        if self.kind == "form":
            external.extend(import_lines(["useState"], "react"))
        internal: list[str] = []
        for feature in sorted(
            (item for item in (self.page.feature, self.page.delete) if item is not None),
            key=lambda item: item.slice,
        ):
            source = self.layout.import_path("features", feature.slice)
            internal.extend(import_lines([feature.component], source))
        if self.page.widget is not None:
            source = self.layout.import_path("widgets", self.page.widget.slice)
            internal.extend(import_lines([self.page.widget.component], source))
        return [*external, *([""] if external else []), *internal]

    def actions_lines(self, indent: str) -> list[str]:
        """Give the controls of one row of the table of a list view. The entity is `item`."""
        entity = self.page.entity
        assert entity is not None
        key = f"item.{entity.key.name}"
        lines: list[str] = []
        if self.page.detail_path is not None:
            collection = self.page.detail_path.removesuffix(f"/${KEY_PARAMETER}")
            lines.extend(
                (
                    "<Link",
                    f"{INDENT}href={{`{collection}/${{encodeURIComponent({key})}}`}}",
                    f'{INDENT}className="{LINK_CLASS}"',
                    ">",
                    f"{INDENT}Details",
                    "</Link>",
                )
            )
        if self.page.delete is not None:
            lines.append(f"<{self.page.delete.component} {self.page.delete.key}={{{key}}} />")
        return [f"{indent}{line}" for line in lines]


def _import(name: str, source: str) -> tuple[str, list[str]]:
    """Give the module path and the lines of the import of one name."""
    return source, import_lines([name], source)


# trace: PRD-APP-009, PRD-DSML-032, PRD-DSML-033
@dataclass(frozen=True, slots=True)
class AppData:
    """The data of the templates of the layer `app` of one application."""

    application: Element
    navigation: tuple[NextPage, ...]
    """The pages of the views of the navigation, in the order of the model."""

    @property
    def navigation_elements(self) -> list[str]:
        identities = (page.page.view.identity for page in self.navigation)
        return sorted({self.application.identity, *identities})

    def title_lines(self) -> list[str]:
        head = "export const APPLICATION_TITLE ="
        value = string_literal(field_label(self.application.name))
        line = f"{head} {value};"
        if len(line) <= PRINT_WIDTH:
            return [line]
        return [head, f"{INDENT}{value};"]

    def navigation_lines(self) -> list[str]:
        """Give the lines of the constant `NAVIGATION`."""
        if not self.navigation:
            return ["export const NAVIGATION: readonly NavigationView[] = [];"]
        lines = ["export const NAVIGATION: readonly NavigationView[] = ["]
        for item in self.navigation:
            roles = [string_literal(role) for role in item.page.roles]
            lines.extend(
                (
                    f"{INDENT}{{",
                    f"{INDENT * 2}path: {string_literal(item.path)},",
                    f"{INDENT * 2}title: {string_literal(item.title)},",
                    f"{INDENT * 2}public: {str(item.page.public).lower()},",
                    *array_lines(INDENT * 2, "roles: ", roles, ","),
                    f"{INDENT}}},",
                )
            )
        lines.append("];")
        return lines


def _navigation(application: Element, pages: list[NextPage]) -> list[NextPage]:
    """Give the pages of the views of the navigation, in the order of the model (PRD-DSML-032)."""
    value = next((item.value for item in application.attributes if item.name == "navigation"), None)
    if not isinstance(value, ListValue):
        return []
    by_view = {page.page.view.identity: page for page in pages}
    result: list[NextPage] = []
    for item in value.items:
        if not isinstance(item, ReferenceValue):
            continue
        page = by_view.get(item.target)
        if page is None:
            raise ToolchainError(
                f"The navigation of the application {application.name} contains "
                f"{item.target}. The navigation must contain only views of the application "
                "with a kind."
            )
        if page.kind == "detail":
            raise ToolchainError(
                f"The navigation of the application {application.name} contains the detail "
                f"view {page.name}. A detail view needs the key of an entity. Remove the "
                "view from the navigation."
            )
        if page not in result:
            result.append(page)
    return result


# trace: PRD-APP-221, PRD-APP-320
def next_pages(context: ReactContext) -> list[NextPage]:
    """Give the page slices of a Next.js application, sorted by slice name.

    A view with a route that starts with a segment of an other part
    (`/api`, `/auth` or `/healthz`) gives a `ToolchainError`.
    """
    pages = [
        NextPage(page, context.layout) for page in page_slices(context.ir, context.application)
    ]
    for page in pages:
        segment = page.path.split("/")[1]
        if segment in RESERVED_SEGMENTS:
            raise ToolchainError(
                f"The view {page.name} of the application {context.application.name} has the "
                f'route path "{page.path}". The first segment "/{segment}" is for the '
                "generated code of the Next.js target. Give the element an other name."
            )
    return pages


# trace: PRD-APP-009, PRD-APP-017, PRD-APP-302, PRD-APP-305, PRD-APP-314, PRD-APP-320
# trace: PRD-APP-321, PRD-APP-324, PRD-DSML-032, PRD-TRACE-005
def pages_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the pages and navigation of one application."""
    pages = next_pages(context)
    files: list[OutputFile] = []
    for page in pages:
        files.extend(_page_files(context, page))
    files.extend(_app_files(context, pages))
    files.extend(_access_files(context))
    return files


def _typed_file(
    context: ReactContext, path: str, template: str, data: dict[str, object], elements: list[str]
) -> OutputFile:
    """Render a generated TypeScript file with the symbols of its elements."""
    file = context.generated_file(path, template, data, elements)
    symbols = typescript_symbols(file.content, tuple(elements))
    return OutputFile(file.path, file.content, file.kind, file.part, symbols)


def _page_files(context: ReactContext, page: NextPage) -> list[OutputFile]:
    elements = page.elements
    data: dict[str, object] = {"page": page}
    files = [
        _typed_file(
            context,
            f"{page.folder}/{page.server_module}.tsx",
            f"nextjs/pages/{page.kind}-page.server.gen.tsx.j2",
            data,
            elements,
        )
    ]
    if page.has_content:
        files.append(
            _typed_file(
                context,
                f"{page.folder}/ui/{page.content_file}.tsx",
                f"nextjs/pages/{page.kind}-content.gen.tsx.j2",
                data,
                elements,
            )
        )
    files.extend(server_api_files(context, page.folder, [page.server_module], elements))
    files.append(
        context.generated_file(
            page.route_file,
            "nextjs/pages/page-route.tsx.j2",
            {
                "component": page.component,
                "source": f"{context.layout.import_path('pages', page.page.slice)}/index.server",
            },
            elements,
        )
    )
    return files


def _app_files(context: ReactContext, pages: list[NextPage]) -> list[OutputFile]:
    data = AppData(context.application, tuple(_navigation(context.application, pages)))
    application = list(context.elements)
    files: list[OutputFile] = []
    for path, template in sorted(_APP_FILES.items()):
        elements = data.navigation_elements if path.endswith("/navigation.gen.tsx") else application
        files.append(_typed_file(context, path, template, {"app": data}, elements))
    for path, component in sorted(_STATUS_ROUTES.items()):
        files.append(
            context.generated_file(
                path,
                "nextjs/pages/page-route.tsx.j2",
                {"component": component, "source": "@/_app/layout/status-pages.gen"},
                application,
            )
        )
    content = context.engine.render_bytes("react/app/index.css.j2", {})
    files.append(OutputFile(f"{context.folder}{STYLES}", content, Kind.CREATE_ONCE, context.part))
    return files


def _access_files(context: ReactContext) -> list[OutputFile]:
    elements = list(context.elements)
    files = [
        _typed_file(
            context,
            f"{ACCESS_SEGMENT}/{module}{'.tsx' if template.endswith('.tsx.j2') else '.ts'}",
            template,
            {},
            elements,
        )
        for module, template in sorted({**_ACCESS_MODULES, **_ACCESS_SERVER_MODULES}.items())
    ]
    files.extend(
        public_api_files(
            context, ACCESS_SEGMENT, list(_ACCESS_MODULES), elements, list(_ACCESS_SERVER_MODULES)
        )
    )
    return files
