# trace: PRD-APP-202, PRD-APP-203, PRD-APP-204, PRD-APP-206, PRD-APP-210, PRD-APP-228
"""The widgets layer of the React generator.

The generator calls `widgets_files` for each `react` application. The
function gives one slice in `src/widgets/` for each entity of a list view
or a detail view of the application (PRD-APP-210):

- A list view gives the slice `<entity>-list` with
  `ui/<entity>-table.gen.tsx`: a table with a header for each column, and
  paging with `limit` and `offset` (PRD-APP-114, PRD-APP-228).
- A detail view gives the slice `<entity>-details` with
  `ui/<entity>-details.gen.tsx`: the fields of one entity.
- `index.gen.ts` and the create-once `index.ts`: the public API of the
  slice (PRD-APP-204).

Two views of one kind for one entity give one slice. The widgets read the
data with the query options of the entity slice. The paging controls are
native buttons, thus the user can reach each control with the keyboard
(PRD-APP-228).

A module imports only from lower layers, through the public API of a slice
(PRD-APP-203): `@/entities/<entity>`, `@/shared/api` and `@/shared/ui`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate.fastapi_slices import LIMIT_DEFAULT, LIMIT_MAX
from dsml.generate.react_common import (
    REACT_LAYOUT,
    FsdLayout,
    ReactContext,
    file_name,
    public_api_files,
    slice_name,
)
from dsml.generate.react_entities import (
    INDENT,
    PRINT_WIDTH,
    EntitySlice,
    ZodField,
    entity_slices,
)
from dsml.generate.react_features import field_label, import_lines, jsx_text_lines
from dsml.generate.typescript_symbols import typescript_symbols
from dsml.generate.writer import OutputFile
from dsml.ir.model import Element, EnumValue, Ir, ReferenceValue

LAYER: Final = "widgets"
"""The FSD layer of this module."""

WIDGET_KINDS: Final = {"list": ("list", "table"), "detail": ("details", "details")}
"""The view kinds with a widget: the suffix of the slice name and of the file name."""

_OPERATIONS: Final = {"list": "list", "detail": "read"}
"""The operation of the entity slice that the widget of each view kind uses."""


def _ui_import_lines(names: Sequence[str], layout: FsdLayout) -> list[str]:
    return import_lines(sorted(names), layout.import_path("shared", "ui"))


# trace: PRD-APP-210, PRD-APP-228
@dataclass(frozen=True, slots=True)
class Column:
    """One field of the entity in a widget: one column of the table, or one row of the details."""

    field: ZodField

    @property
    def label(self) -> str:
        """The text of the column header, for example `Birth date` for `birth_date`."""
        return field_label(self.field.name)

    @property
    def boolean(self) -> bool:
        return self.field.field.rules.kind == "Boolean"

    def value(self, item: str) -> str:
        """Give the JSX expression of the value of the field of `item`.

        A Boolean value gives `Yes` or `No`. A `null` value gives an empty text.
        """
        expression = f"{item}.{self.field.name}"
        if self.boolean:
            return f"{{yesNo({expression})}}"
        if self.field.field.nullable:
            return f'{{{expression} ?? ""}}'
        return f"{{{expression}}}"


# trace: PRD-APP-206, PRD-APP-210
@dataclass(frozen=True, slots=True)
class WidgetSlice:
    """The slice of one widget in `src/widgets/`: a table or the details of an entity."""

    kind: str
    """The view kind: `list` or `detail`."""
    entity: EntitySlice
    views: tuple[str, ...]
    """The identities of the views of the widget, sorted."""

    @property
    def elements(self) -> list[str]:
        """The identities of the header: the entity, the exposed elements and the views."""
        return sorted({*self.entity.elements, *self.views})

    @property
    def slice(self) -> str:
        """The name of the slice folder, for example `order-list`."""
        return slice_name(f"{self.entity.name} {WIDGET_KINDS[self.kind][0]}")

    def folder(self, layout: FsdLayout = REACT_LAYOUT) -> str:
        """Give the folder of the slice in the project, with the layer name of the layout."""
        return layout.slice_folder(LAYER, f"{self.entity.name} {WIDGET_KINDS[self.kind][0]}")

    @property
    def ui_module(self) -> str:
        """The ui module relative to the slice folder, for example `ui/order-table.gen`."""
        return f"ui/{file_name(self.entity.name, WIDGET_KINDS[self.kind][1])}.gen"

    @property
    def component(self) -> str:
        """The name of the component, for example `OrderTable`."""
        suffix = "Table" if self.kind == "list" else "Details"
        return f"{self.entity.pascal}{suffix}"

    @property
    def columns(self) -> tuple[Column, ...]:
        """The fields of the entity: the key first, then the other fields in schema order."""
        fields = sorted(self.entity.fields, key=lambda item: not item.field.key)
        return tuple(Column(item) for item in fields)

    @property
    def uses_yes_no(self) -> bool:
        return any(item.boolean for item in self.columns)

    @property
    def route(self) -> str:
        return self.entity.route(_OPERATIONS[self.kind])

    @property
    def key(self) -> str:
        """The name of the key property of the details, for example `id`."""
        return self.entity.read_parameter

    @property
    def key_type(self) -> str:
        return self.entity.key_type

    @property
    def page_default(self) -> int:
        return LIMIT_DEFAULT

    @property
    def page_max(self) -> int:
        return LIMIT_MAX

    # The lines of the ui file.

    def import_lines(self, layout: FsdLayout = REACT_LAYOUT) -> list[str]:
        """Give the import statements of the ui file, in groups with an empty line between."""
        entity = self.entity
        if self.kind == "list":
            query = ["keepPreviousData", "useQuery"]
            react = ["type ReactNode", "useState"]
            names = [f"type {entity.pascal}", f"list{entity.pascal}QueryOptions"]
            ui = ["Button", "Table", "TableBody", "TableCell", "TableHead", "TableHeader"]
            ui.append("TableRow")
        else:
            query = ["useQuery"]
            react = ["type ReactNode"]
            names = [f"read{entity.pascal}QueryOptions"]
            ui = []
        ui.extend(("Alert", "AlertDescription", "AlertTitle"))
        return [
            *import_lines(query, "@tanstack/react-query"),
            *import_lines(react, "react"),
            "",
            *import_lines(
                sorted(names, key=lambda name: name.removeprefix("type ")),
                layout.import_path("entities", entity.slice),
            ),
            *import_lines(["ApiError"], layout.import_path("shared", "api")),
            *_ui_import_lines(ui, layout),
        ]

    def header_lines(self, indent: str) -> list[str]:
        """Give the column headers of the table."""
        return [
            line
            for item in self.columns
            for line in jsx_text_lines(indent, '<TableHead scope="col">', item.label, "TableHead")
        ]

    def cell_lines(self, indent: str) -> list[str]:
        """Give the cells of one row of the table. The entity of the row is `item`."""
        return [
            line
            for column in self.columns
            for line in jsx_text_lines(indent, "<TableCell>", column.value("item"), "TableCell")
        ]

    def detail_lines(self, indent: str) -> list[str]:
        """Give the terms and the values of the details. The entity is `item`."""
        lines: list[str] = []
        for column in self.columns:
            lines.extend(jsx_text_lines(indent, '<dt className="font-medium">', column.label, "dt"))
            lines.extend(jsx_text_lines(indent, "<dd>", column.value("item"), "dd"))
        return lines

    def component_lines(self) -> list[str]:
        """Give the first lines of the function of the component, with the Prettier line breaks."""
        names = [f"pageSize = {LIMIT_DEFAULT}", "actions"] if self.kind == "list" else [self.key]
        head = f"export function {self.component}("
        tail = f"}}: {self.component}Props) {{"
        line = f"{head}{{ {', '.join(names)} {tail}"
        if len(line) <= PRINT_WIDTH:
            return [line]
        return [f"{head}{{", *(f"{INDENT}{name}," for name in names), tail]

    def query_lines(self) -> list[str]:
        """Give the lines of the query of the component, with the Prettier line breaks."""
        pascal = self.entity.pascal
        if self.kind == "detail":
            line = f"{INDENT}const query = useQuery(read{pascal}QueryOptions({self.key}));"
            if len(line) <= PRINT_WIDTH:
                return [line]
            return [
                f"{INDENT}const query = useQuery(",
                f"{INDENT * 2}read{pascal}QueryOptions({self.key}),",
                f"{INDENT});",
            ]
        options = f"{INDENT * 2}...list{pascal}QueryOptions("
        line = f"{options}{{ limit: pageSize, offset }}),"
        if len(line) <= PRINT_WIDTH:
            lines = [line]
        else:
            lines = [
                f"{options}{{",
                f"{INDENT * 3}limit: pageSize,",
                f"{INDENT * 3}offset,",
                f"{INDENT * 2}}}),",
            ]
        return [
            f"{INDENT}const query = useQuery({{",
            *lines,
            f"{INDENT * 2}placeholderData: keepPreviousData,",
            f"{INDENT}}});",
        ]

    @property
    def column_count(self) -> int:
        return len(self.columns)

    @property
    def row_key(self) -> str:
        """The JSX expression of the React key of a row: the key of the entity."""
        return f"item.{self.entity.key.name}"


def _attribute(view: Element, name: str) -> object:
    return next((item.value for item in view.attributes if item.name == name), None)


# trace: PRD-APP-206, PRD-APP-210
def widget_slices(ir: Ir, application: Element) -> list[WidgetSlice]:
    """Give the widget slices of a React application, sorted by slice name.

    Each entity of a list view gives one table, and each entity of a detail
    view gives one details widget. A view of an entity with no entity slice,
    or with no operation for the widget, gives a `ToolchainError`.
    """
    entities = {item.entity: item for item in entity_slices(ir, application)}
    views: dict[tuple[str, str], list[str]] = {}
    for view in ir.elements:
        if view.kind != "View" or view.owner != application.identity:
            continue
        kind = _attribute(view, "kind")
        reference = _attribute(view, "entity")
        if not isinstance(kind, EnumValue) or kind.literal not in WIDGET_KINDS:
            continue
        if not isinstance(reference, ReferenceValue):
            continue
        entity = entities.get(reference.target)
        if entity is None:
            raise ToolchainError(
                f"The {kind.literal} view {view.name} of the application {application.name} "
                f"refers to the entity {reference.target}. No application that "
                f"{application.name} calls exposes this entity. Expose the entity in a called "
                "application."
            )
        operation = _OPERATIONS[kind.literal]
        if entity.operation(operation) is None:
            raise ToolchainError(
                f"The {kind.literal} view {view.name} of the application {application.name} "
                f"needs the operation {operation} of the entity {entity.name}. Add "
                f"CrudKind::{operation} to the exposed entity."
            )
        views.setdefault((kind.literal, entity.entity), []).append(view.identity)
    result = [
        WidgetSlice(kind, entities[entity], tuple(sorted(identities)))
        for (kind, entity), identities in views.items()
    ]
    return sorted(result, key=lambda item: item.slice)


# trace: PRD-APP-017, PRD-APP-202, PRD-APP-203, PRD-APP-204, PRD-APP-210, PRD-APP-228
# trace: PRD-CORE-031, PRD-TRACE-005, PRD-TRACE-006
def widgets_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the layer `widgets` of one application."""
    files: list[OutputFile] = []
    for widget in widget_slices(context.ir, context.application):
        template = "table" if widget.kind == "list" else "details"
        file = context.generated_file(
            f"{widget.folder(context.layout)}/{widget.ui_module}.tsx",
            f"react/widgets/{template}.gen.tsx.j2",
            {"widget": widget},
            widget.elements,
        )
        symbols = typescript_symbols(file.content, tuple(widget.elements))
        files.append(OutputFile(file.path, file.content, file.kind, file.part, symbols))
        files.extend(
            public_api_files(
                context, widget.folder(context.layout), [widget.ui_module], widget.elements
            )
        )
    return files
