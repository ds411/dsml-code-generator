# trace: PRD-APP-202, PRD-APP-203, PRD-APP-204, PRD-APP-206, PRD-APP-210, PRD-APP-221
"""The pages layer of the React generator.

The generator calls `pages_files` for each `react` application. The
function gives one slice in `src/pages/` for each view of the application
(PRD-APP-210):

- `ui/<view>-page.gen.tsx`: the page of the view. It combines the widgets
  and the features of the view.
- `index.gen.ts` and the create-once `index.ts`: the public API of the
  slice (PRD-APP-204).

A list view shows the table of its entity. Each row has a link to the
detail view of the entity, if the application has one, and the delete
button, if the entity has the operation `delete`. A detail view shows the
details of one entity. A form view shows the form of its operation.

Each view has one route path (PRD-APP-221): `/<entities>` for a list view,
`/<entities>/$id` for a detail view and `/<operation>` for a form view. The
app layer (`dsml.generate.react_app`) writes the routes.

A module imports only from lower layers, through the public API of a slice
(PRD-APP-203): `@/widgets/<widget>` and `@/features/<feature>`.
"""

from dataclasses import dataclass
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate.fastapi_slices import is_public, roles_of
from dsml.generate.names import kebab_case, pascal_case
from dsml.generate.react_common import (
    ReactContext,
    file_name,
    public_api_files,
    slice_folder,
    slice_name,
)
from dsml.generate.react_entities import INDENT, PRINT_WIDTH, EntitySlice, string_literal
from dsml.generate.react_features import FeatureSlice, feature_slices, field_label, import_lines
from dsml.generate.react_widgets import WidgetSlice, widget_slices
from dsml.generate.typescript_symbols import typescript_symbols
from dsml.generate.writer import OutputFile
from dsml.ir.model import Element, EnumValue, Ir, ReferenceValue

LAYER: Final = "pages"
"""The FSD layer of this module."""

VIEW_KINDS: Final = ("list", "detail", "form")
"""The literals of `DSML::ViewKind`."""

KEY_PARAMETER: Final = "id"
"""The path parameter of the key in the route of a detail view (PRD-APP-221)."""

LINK_CLASS: Final = "text-primary underline-offset-4 hover:underline"
"""The Tailwind CSS classes of a link in a page."""


def _attribute(view: Element, name: str) -> object:
    return next((item.value for item in view.attributes if item.name == name), None)


# trace: PRD-APP-206, PRD-APP-210, PRD-APP-221, PRD-APP-222, PRD-DSML-033
@dataclass(frozen=True, slots=True)
class PageSlice:
    """The slice of the page of one view in `src/pages/`."""

    view: Element
    kind: str
    """The view kind: `list`, `detail` or `form`."""
    widget: WidgetSlice | None = None
    """The widget of a list view or a detail view."""
    feature: FeatureSlice | None = None
    """The feature of the operation of a form view."""
    delete: FeatureSlice | None = None
    """The feature of the operation `delete` of the entity of a list view, if it has one."""
    detail_path: str | None = None
    """The route path of the detail view of the entity of a list view, if it has one."""

    @property
    def name(self) -> str:
        """The name of the view, for example `orderList`."""
        return self.view.name

    @property
    def elements(self) -> list[str]:
        """The identities of the header: the view and the elements of its widget and features."""
        found = {self.view.identity}
        if self.widget is not None:
            found.update(self.widget.entity.elements)
        for feature in (self.feature, self.delete):
            if feature is not None:
                found.update(feature.elements)
        return sorted(found)

    @property
    def slice(self) -> str:
        """The name of the slice folder, for example `order-list`."""
        return slice_name(self.name)

    @property
    def folder(self) -> str:
        return slice_folder(LAYER, self.name)

    @property
    def ui_module(self) -> str:
        """The ui module relative to the slice folder, for example `ui/order-list-page.gen`."""
        return f"ui/{file_name(self.name, 'page')}.gen"

    @property
    def component(self) -> str:
        """The name of the component, for example `OrderListPage`."""
        return f"{pascal_case(self.name)}Page"

    @property
    def title(self) -> str:
        """The title of the page: the view name in words, for example `Order list`."""
        return field_label(self.name)

    @property
    def description(self) -> str | None:
        """The documentation of the view on one line, or `None`."""
        if self.view.doc is None or not self.view.doc.split():
            return None
        return " ".join(self.view.doc.split())

    @property
    def entity(self) -> EntitySlice | None:
        return self.widget.entity if self.widget is not None else None

    @property
    def roles(self) -> tuple[str, ...]:
        """The roles that can use the view, sorted (PRD-DSML-033)."""
        return roles_of(self.view)

    @property
    def public(self) -> bool:
        """Tell if the view needs no session (`public = true`)."""
        return is_public(self.view)

    @property
    def path(self) -> str:
        """The route path of the view, for example `/orders` (PRD-APP-221)."""
        if self.feature is not None:
            return f"/{self.feature.slice}"
        entity = self.entity
        assert entity is not None
        operation = entity.operation("list" if self.kind == "list" else "read")
        assert operation is not None
        collection = f"/{kebab_case(operation.collection)}"
        return collection if self.kind == "list" else f"{collection}/${KEY_PARAMETER}"

    @property
    def key_type(self) -> str:
        """The TypeScript type of the key of the entity of a detail view."""
        entity = self.entity
        return entity.key_type if entity is not None else "string"

    # The lines of the ui file.

    def import_lines(self) -> list[str]:
        """Give the import statements of the ui file, in groups with an empty line between."""
        external: list[str] = []
        if self.kind == "list" and self.detail_path is not None:
            external.extend(import_lines(["Link"], "@tanstack/react-router"))
        if self.kind == "form":
            external.extend(import_lines(["useState"], "react"))
        internal: list[str] = []
        for feature in sorted(
            (item for item in (self.feature, self.delete) if item is not None),
            key=lambda item: item.slice,
        ):
            internal.extend(import_lines([feature.component], f"@/features/{feature.slice}"))
        if self.widget is not None:
            internal.extend(import_lines([self.widget.component], f"@/widgets/{self.widget.slice}"))
        return [*external, *([""] if external else []), *internal]

    def description_lines(self) -> list[str]:
        """Give the constant of the description of the view, with the Prettier line breaks."""
        text = self.description
        assert text is not None
        head = "const DESCRIPTION ="
        line = f"{head} {string_literal(text)};"
        if len(line) <= PRINT_WIDTH:
            return [line]
        return [head, f"{INDENT}{string_literal(text)};"]

    def actions_lines(self, indent: str) -> list[str]:
        """Give the controls of one row of the table of a list view. The entity is `item`.

        The controls are a link to the detail view and the delete button.
        """
        entity = self.entity
        assert entity is not None
        key = f"item.{entity.key.name}"
        lines: list[str] = []
        if self.detail_path is not None:
            value = key if entity.key_type == "string" else f"String({key})"
            lines.extend(
                (
                    "<Link",
                    f'{INDENT}to="{self.detail_path}"',
                    f"{INDENT}params={{{{ {KEY_PARAMETER}: {value} }}}}",
                    f'{INDENT}className="{LINK_CLASS}"',
                    ">",
                    f"{INDENT}Details",
                    "</Link>",
                )
            )
        if self.delete is not None:
            lines.append(f"<{self.delete.component} {self.delete.key}={{{key}}} />")
        return [f"{indent}{line}" for line in lines]

    @property
    def has_actions(self) -> bool:
        return self.detail_path is not None or self.delete is not None

    @property
    def detail_key(self) -> str:
        """The key property of the details widget, for example `id`."""
        assert self.widget is not None
        return self.widget.key


def _view_kind(view: Element) -> str | None:
    kind = _attribute(view, "kind")
    if isinstance(kind, EnumValue) and kind.literal in VIEW_KINDS:
        return kind.literal
    return None


def views_of(ir: Ir, application: Element) -> list[Element]:
    """Give the views of an application with a kind, sorted by identity."""
    return sorted(
        (
            item
            for item in ir.elements
            if item.kind == "View" and item.owner == application.identity and _view_kind(item)
        ),
        key=lambda item: item.identity,
    )


def _form_feature(
    view: Element, application: Element, features: list[FeatureSlice]
) -> FeatureSlice:
    reference = _attribute(view, "operation")
    target = reference.target if isinstance(reference, ReferenceValue) else None
    found = [
        item for item in features if item.custom is not None and item.custom.operation == target
    ]
    if len(found) != 1:
        problem = "no called application exposes" if not found else "two exposed actions use"
        raise ToolchainError(
            f"The form view {view.name} of the application {application.name} refers to the "
            f"operation {target}, but {problem} this operation with a method other than GET. "
            "A form view must refer to one exposed operation with a change."
        )
    return found[0]


# trace: PRD-APP-206, PRD-APP-210, PRD-APP-221
def page_slices(ir: Ir, application: Element) -> list[PageSlice]:
    """Give the page slices of a React application, sorted by slice name.

    Each view gives one page. A form view that does not refer to one
    exposed operation with a change, or two views with one route path, give
    a `ToolchainError`.
    """
    views = views_of(ir, application)
    if not views:
        return []
    widgets = {view: item for item in widget_slices(ir, application) for view in item.views}
    features = feature_slices(ir, application)
    pages: list[PageSlice] = []
    for view in views:
        kind = _view_kind(view)
        assert kind is not None
        if kind == "form":
            pages.append(PageSlice(view, kind, feature=_form_feature(view, application, features)))
            continue
        pages.append(PageSlice(view, kind, widget=widgets[view.identity]))
    details = {
        page.widget.entity.entity: page.path
        for page in pages
        if page.kind == "detail" and page.widget is not None
    }
    deletes = {
        item.entity.entity: item
        for item in features
        if item.kind == "delete" and item.entity is not None
    }
    result: dict[str, PageSlice] = {}
    paths: dict[str, PageSlice] = {}
    for page in pages:
        if page.kind == "list" and page.widget is not None:
            entity = page.widget.entity.entity
            page = PageSlice(
                page.view,
                page.kind,
                widget=page.widget,
                delete=deletes.get(entity),
                detail_path=details.get(entity),
            )
        other = paths.get(page.path)
        if other is not None:
            raise ToolchainError(
                f"The views {other.name} and {page.name} of the application {application.name} "
                f'have the same route path "{page.path}". Each view must have its own route '
                "(PRD-APP-221). Remove one of the views."
            )
        if page.slice in result:
            raise ToolchainError(
                f"The application {application.name} has two views with the page slice name "
                f'"{page.slice}". Give one of the views an other name.'
            )
        paths[page.path] = page
        result[page.slice] = page
    return [result[name] for name in sorted(result)]


# trace: PRD-APP-017, PRD-APP-202, PRD-APP-203, PRD-APP-204, PRD-APP-210, PRD-CORE-031
# trace: PRD-TRACE-005, PRD-TRACE-006
def pages_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the layer `pages` of one application."""
    files: list[OutputFile] = []
    for page in page_slices(context.ir, context.application):
        file = context.generated_file(
            f"{page.folder}/{page.ui_module}.tsx",
            f"react/pages/{page.kind}-page.gen.tsx.j2",
            {"page": page},
            page.elements,
        )
        symbols = typescript_symbols(file.content, tuple(page.elements))
        files.append(OutputFile(file.path, file.content, file.kind, file.part, symbols))
        files.extend(public_api_files(context, page.folder, [page.ui_module], page.elements))
    return files
