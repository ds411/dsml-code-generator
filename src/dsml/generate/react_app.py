# trace: PRD-APP-009, PRD-APP-202, PRD-APP-210, PRD-APP-220, PRD-APP-221, PRD-APP-222
# trace: PRD-APP-223, PRD-APP-230, PRD-APP-231, PRD-DSML-032, PRD-DSML-033
"""The app layer of the React generator.

The generator calls `app_files` for each `react` application. The function
gives the files in the folder of the layer `app`: `src/app/` in the React
layout. The layer `app` has no slices.

- `router/routes.gen.tsx`: the TanStack Router route tree with code-based
  routing (PRD-APP-220). Each view has one route (PRD-APP-221). The
  `beforeLoad` function of each route checks the session and the roles of
  the view (PRD-APP-222). The loader of a list route and of a detail route
  fills the query cache with `queryClient.ensureQueryData` and the query
  options of the entity slice (PRD-APP-223).
- `router/views.gen.ts`: the path, the title and the roles of each view,
  and the navigation of the model (PRD-DSML-032, PRD-DSML-033).
- `router/access.gen.ts`: the check of the session and the roles.
- `router/router.gen.ts`: the router.
- `layout/navigation.gen.tsx`: the navigation. It shows only the views that
  the roles of the user permit (PRD-APP-009).
- `layout/app-layout.gen.tsx` and `layout/status-pages.gen.tsx`: the layout,
  the home page, the "not permitted" page and the "not found" page.
- `providers/*.gen.ts*`: the TanStack Query client, the providers of
  TanStack Query and the router, and the start of the auth session. The
  entry module reads `/config.json` and configures Amplify Auth before the
  first render (PRD-APP-230, PRD-APP-231).
- `styles/index.css`: the Tailwind CSS file with the theme variables of
  shadcn/ui. It is a create-once file, thus a developer can change the
  theme.

The route of the callback URL of the managed login is `/auth/callback`
(PRD-IAC-019).
"""

from dataclasses import dataclass
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate.infrastructure.modules import CALLBACK_PATH
from dsml.generate.names import camel_case
from dsml.generate.react_common import REACT_LAYOUT, FsdLayout, ReactContext
from dsml.generate.react_entities import INDENT, PRINT_WIDTH, string_literal
from dsml.generate.react_features import field_label, import_lines
from dsml.generate.react_pages import PageSlice, page_slices
from dsml.generate.typescript_symbols import typescript_symbols
from dsml.generate.writer import Kind, OutputFile
from dsml.ir.model import Element, ListValue, ReferenceValue

LAYER: Final = "app"
"""The FSD layer of this module."""

STYLES: Final = "styles/index.css"
"""The create-once Tailwind CSS file in the layer folder. `components.json` refers to it."""

# The template of each generated file that has the same text for each
# application, by the path in the layer folder.
_STATIC: Final = {
    "layout/status-pages.gen.tsx": "react/app/status-pages.gen.tsx.j2",
    "providers/app-providers.gen.tsx": "react/app/app-providers.gen.tsx.j2",
    "providers/query-client.gen.ts": "react/app/query-client.gen.ts.j2",
    "providers/session.gen.ts": "react/app/session.gen.ts.j2",
    "router/access.gen.ts": "react/app/access.gen.ts.j2",
    "router/router.gen.ts": "react/app/router.gen.ts.j2",
}


def _list_lines(head: str, items: list[str], tail: str) -> list[str]:
    """Give the lines of an array, with the Prettier line breaks."""
    line = f"{head}[{', '.join(items)}]{tail}"
    if len(line) <= PRINT_WIDTH or not items:
        return [line]
    return [f"{head}[", *(f"{INDENT}{item}," for item in items), f"]{tail}"]


def _call_lines(indent: str, head: str, function: str, argument: str) -> list[str]:
    """Give the lines of `<head> <function>(<argument>),`, with the Prettier line breaks.

    `head` is a property name with its colon, or an arrow function head
    that ends with `=>`. Prettier first puts the body of an arrow function
    on the next line, then the argument of the call.
    """
    call = f"{function}({argument}),"
    line = f"{indent}{head} {call}"
    if len(line) <= PRINT_WIDTH:
        return [line]
    inner = indent + INDENT if head.endswith("=>") else indent
    first = [f"{indent}{head}"] if head.endswith("=>") else []
    if first and len(f"{inner}{call}") <= PRINT_WIDTH:
        return [*first, f"{inner}{call}"]
    opening = f"{inner}{function}(" if first else f"{indent}{head} {function}("
    return [*first, opening, f"{inner}{INDENT}{argument},", f"{inner}),"]


# trace: PRD-APP-220, PRD-APP-221, PRD-APP-222, PRD-APP-223
@dataclass(frozen=True, slots=True)
class ViewRoute:
    """The route of the page of one view."""

    page: PageSlice

    @property
    def key(self) -> str:
        """The key of the view in the object `VIEWS`, for example `orderList`."""
        return camel_case(self.page.name)

    @property
    def name(self) -> str:
        """The name of the route constant, for example `orderListRoute`."""
        return f"{self.key}Route"

    @property
    def component(self) -> str:
        """The component of the route: the page, or a wrapper that gives the path parameter."""
        if self.page.kind == "detail":
            return f"{self.page.component}Route"
        return self.page.component

    @property
    def key_value(self) -> str:
        """The expression of the key of a detail route, from the path parameter."""
        return "Number(id)" if self.page.key_type == "number" else "id"

    @property
    def options(self) -> tuple[str, str] | None:
        """The query options function of the loader and its argument, or `None`."""
        entity = self.page.entity
        if entity is None:
            return None
        if self.page.kind == "list":
            return f"list{entity.pascal}QueryOptions", ""
        value = "Number(params.id)" if self.page.key_type == "number" else "params.id"
        return f"read{entity.pascal}QueryOptions", value

    def view_lines(self) -> list[str]:
        """Give the entry of the view in the object `VIEWS`."""
        page = self.page
        roles = [string_literal(role) for role in page.roles]
        return [
            f"{INDENT}{self.key}: {{",
            f"{INDENT * 2}path: {string_literal(page.path)},",
            f"{INDENT * 2}title: {string_literal(page.title)},",
            f"{INDENT * 2}public: {'true' if page.public else 'false'},",
            *_list_lines(f"{INDENT * 2}roles: ", roles, ","),
            f"{INDENT}}},",
        ]

    def route_lines(self) -> list[str]:
        """Give the lines of the route constant and of the wrapper of a detail page."""
        page = self.page
        lines = [
            f"/** The route of the view {page.name}: {page.path} (PRD-APP-221). */",
            f"const {self.name} = createRoute({{",
            f"{INDENT}getParentRoute: () => rootRoute,",
            f"{INDENT}path: {string_literal(page.path)},",
            *_call_lines(INDENT, "beforeLoad:", "requireView", f"VIEWS.{self.key}"),
        ]
        options = self.options
        if options is not None:
            function, argument = options
            head = "({ context })" if page.kind == "list" else "({ context, params })"
            lines.extend(
                _call_lines(
                    INDENT,
                    f"loader: {head} =>",
                    "context.queryClient.ensureQueryData",
                    f"{function}({argument})",
                )
            )
        lines.extend((f"{INDENT}component: {self.component},", "});"))
        if page.kind == "detail":
            lines.extend(
                (
                    "",
                    f"/** The page of the view {page.name} with the key of the path. */",
                    f"function {self.component}(): ReactNode {{",
                    f"{INDENT}const {{ id }} = {self.name}.useParams();",
                    f"{INDENT}return <{page.component} id={{{self.key_value}}} />;",
                    "}",
                )
            )
        return lines


def _navigation(application: Element, routes: dict[str, ViewRoute]) -> list[ViewRoute]:
    """Give the routes of the views of the navigation, in the order of the model."""
    value = next((item.value for item in application.attributes if item.name == "navigation"), None)
    if not isinstance(value, ListValue):
        return []
    result: list[ViewRoute] = []
    for item in value.items:
        if not isinstance(item, ReferenceValue):
            continue
        route = routes.get(item.target)
        if route is None:
            raise ToolchainError(
                f"The navigation of the application {application.name} contains "
                f"{item.target}. The navigation must contain only views of the application "
                "with a kind."
            )
        if route.page.kind == "detail":
            raise ToolchainError(
                f"The navigation of the application {application.name} contains the detail "
                f"view {route.page.name}. A detail view needs the key of an entity. Remove the "
                "view from the navigation."
            )
        if route not in result:
            result.append(route)
    return result


# trace: PRD-APP-220, PRD-APP-221, PRD-APP-222, PRD-APP-223, PRD-DSML-032
@dataclass(frozen=True, slots=True)
class AppData:
    """The data of the templates of the app layer of one application."""

    application: Element
    routes: tuple[ViewRoute, ...]
    """The routes of the views, sorted by the name of the route constant."""
    navigation: tuple[ViewRoute, ...]
    """The routes of the views of the navigation, in the order of the model."""

    @property
    def view_elements(self) -> list[str]:
        return sorted({self.application.identity, *(r.page.view.identity for r in self.routes)})

    @property
    def navigation_elements(self) -> list[str]:
        identities = (route.page.view.identity for route in self.navigation)
        return sorted({self.application.identity, *identities})

    @property
    def title_lines(self) -> list[str]:
        head = "export const APPLICATION_TITLE ="
        value = string_literal(field_label(self.application.name))
        line = f"{head} {value};"
        if len(line) <= PRINT_WIDTH:
            return [line]
        return [head, f"{INDENT}{value};"]

    @property
    def callback_path(self) -> str:
        return string_literal(CALLBACK_PATH)

    def views_lines(self) -> list[str]:
        if not self.routes:
            return ["export const VIEWS = {} as const satisfies Record<string, View>;"]
        return [
            "export const VIEWS = {",
            *(line for route in self.routes for line in route.view_lines()),
            "} as const satisfies Record<string, View>;",
        ]

    def navigation_lines(self) -> list[str]:
        """Give the lines of the constant `NAVIGATION`.

        An empty navigation has an explicit type. Without it, the type of
        the items is `never`, and `tsc` refuses the navigation component.
        """
        items = [f"VIEWS.{route.key}" for route in self.navigation]
        if not items:
            return ["export const NAVIGATION: readonly View[] = [];"]
        return _list_lines("export const NAVIGATION = ", items, " as const;")

    def import_lines(self, layout: FsdLayout = REACT_LAYOUT) -> list[str]:
        """Give the imports of the entity slices and of the page slices."""
        by_entity: dict[str, set[str]] = {}
        for route in self.routes:
            entity = route.page.entity
            options = route.options
            if entity is not None and options is not None:
                by_entity.setdefault(entity.slice, set()).add(options[0])
        lines = [
            line
            for name in sorted(by_entity)
            for line in import_lines(sorted(by_entity[name]), layout.import_path("entities", name))
        ]
        for route in sorted(self.routes, key=lambda item: item.page.slice):
            source = layout.import_path("pages", route.page.slice)
            lines.extend(import_lines([route.page.component], source))
        return lines

    def route_lines(self) -> list[str]:
        lines: list[str] = []
        for route in self.routes:
            lines.extend(("", *route.route_lines()))
        return lines

    @property
    def has_loaders(self) -> bool:
        """Tell if a route has a loader. A list view and a detail view give a loader."""
        return any(route.options is not None for route in self.routes)

    def tree_lines(self) -> list[str]:
        items = ["homeRoute", "callbackRoute", *(route.name for route in self.routes)]
        return _list_lines("export const routeTree = rootRoute.addChildren(", items, ");")


# trace: PRD-APP-009, PRD-APP-220, PRD-APP-221, PRD-DSML-032
def app_data(context: ReactContext) -> AppData:
    """Give the data of the app layer of one application."""
    pages = page_slices(context.ir, context.application)
    routes = sorted((ViewRoute(page) for page in pages), key=lambda item: item.name)
    by_view = {route.page.view.identity: route for route in routes}
    navigation = _navigation(context.application, by_view)
    return AppData(context.application, tuple(routes), tuple(navigation))


# trace: PRD-APP-009, PRD-APP-017, PRD-APP-202, PRD-APP-220, PRD-APP-221, PRD-APP-222
# trace: PRD-APP-223, PRD-APP-230, PRD-APP-231, PRD-CORE-031, PRD-TRACE-005, PRD-TRACE-006
def app_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the layer `app` of one application."""
    data = app_data(context)
    application = context.elements
    folder = context.layout.layer_folder(LAYER)
    templates: list[tuple[str, str, list[str]]] = [
        (path, template, list(application)) for path, template in _STATIC.items()
    ]
    templates.extend(
        (
            ("layout/app-layout.gen.tsx", "react/app/app-layout.gen.tsx.j2", list(application)),
            (
                "layout/navigation.gen.tsx",
                "react/app/navigation.gen.tsx.j2",
                data.navigation_elements,
            ),
            ("router/routes.gen.tsx", "react/app/routes.gen.tsx.j2", data.view_elements),
            ("router/views.gen.ts", "react/app/views.gen.ts.j2", data.view_elements),
        )
    )
    files: list[OutputFile] = []
    for path, template, elements in sorted(templates):
        file = context.generated_file(
            f"{folder}/{path}",
            template,
            {"app": data, "title_lines": data.title_lines},
            elements,
        )
        symbols = typescript_symbols(file.content, tuple(elements))
        files.append(OutputFile(file.path, file.content, file.kind, file.part, symbols))
    content = context.engine.render_bytes("react/app/index.css.j2", {})
    path = f"{context.folder}{folder}/{STYLES}"
    files.append(OutputFile(path, content, Kind.CREATE_ONCE, context.part))
    return files
