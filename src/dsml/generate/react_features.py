# trace: PRD-APP-202, PRD-APP-203, PRD-APP-204, PRD-APP-206, PRD-APP-210, PRD-APP-225
# trace: PRD-APP-226, PRD-APP-227, PRD-APP-228
"""The features layer of the React generator.

The generator calls `features_files` for each `react` application. The
function gives one slice in `src/features/<operation>/` for each operation
with a change of each application that the React application calls
(`#Calls`) (PRD-APP-210):

- `create`, `update` and each custom operation that does not use the HTTP
  method GET: `api/<operation>.gen.ts` (the mutation) and
  `ui/<operation>-form.gen.tsx` (the TanStack Form form).
- `delete`: `api/<operation>.gen.ts` (the mutation) and
  `ui/<operation>-button.gen.tsx` (a button with a confirmation dialog).
- `index.gen.ts` and the create-once `index.ts`: the public API of the
  slice (PRD-APP-204).

The operations `read` and `list` and a custom operation with the method
GET do not change data. The entities layer gives their query options.

After a success, a mutation invalidates the queries of each changed entity
with the query key of its entity slice (PRD-APP-225). A form validates its
values with the Zod schema of its operation (PRD-APP-226). The schemas of
`create` and `update` come from the entity slice. A custom operation gets
its schemas in its own mutation file, from the same parameters as the
Pydantic models of the called FastAPI application (PRD-APP-005). Each field
has a label and an error message. The form shows the `title` and the
`detail` of a problem details response (PRD-APP-227). The forms use only
native controls and the shadcn/ui components, thus the user can reach each
control with the keyboard (PRD-APP-228).

Each operation of an external API that does not use the method GET also
gives a slice, as a custom operation (PRD-APP-006). Its input schema has the
path parameters, the query parameters and the properties of the request
body. Its output schema is the schema of the entity slice of the response.
After a success, the mutation invalidates the queries of each entity slice
of the external API.

A module imports only from lower layers, through the public API of a slice
(PRD-APP-203): `@/entities/<entity>`, `@/shared/api` and `@/shared/ui`.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate.fastapi_database import models
from dsml.generate.fastapi_examples import Rules
from dsml.generate.fastapi_operations import CustomSlice, ParameterField, custom_slices
from dsml.generate.fastapi_slices import Slice, slices
from dsml.generate.names import camel_case, pascal_case, words
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
    ExternalEntitySlice,
    ZodField,
    api_applications,
    base_chain,
    entity_slices,
    external_entity_slices,
    input_rule_chain,
    object_lines,
    path_expression,
    query_lines,
)
from dsml.generate.react_external import ExternalField, ExternalOperation, external_apis
from dsml.generate.typescript_symbols import typescript_symbols
from dsml.generate.writer import OutputFile
from dsml.ir.model import Element, Ir

LAYER: Final = "features"
"""The FSD layer of this module."""

CHANGE_OPERATIONS: Final = ("create", "update", "delete")
"""The CRUD operations with a change. Each one gives a feature slice."""

FIELD_INDENT: Final = 8
"""The indentation of the element `form.Field` of a field in the form file."""

MULTILINE_LENGTH: Final = 200
"""A text field with no `maxLength`, or a greater `maxLength`, uses a text area."""

_LIST_KINDS: Final = frozenset({"Date", "DateTime", "Decimal", "Enumeration", "String", "Uuid"})
"""The field types that a form can give as a list of values: one value on each line."""

_INPUT_TYPES: Final = {"Date": "date", "DateTime": "datetime-local"}
"""The type of the HTML input of each field type. The other types use `text`."""

_ATTRIBUTE: Final = re.compile(r"\s[A-Za-z-]+=")
"""The start of one attribute of a JSX opening tag."""

_KEY_TYPES: Final = {"Integer": "number", "Real": "number"}
"""The TypeScript type of a path parameter of each field type. Other types are a `string`."""


def field_label(name: str) -> str:
    """Give the label of a field, for example `Birth date` for `birth_date`."""
    text = " ".join(words(name))
    return text[:1].upper() + text[1:]


# trace: PRD-APP-226, PRD-APP-228
@dataclass(frozen=True, slots=True)
class FormField:
    """One field of a form: one property of the input schema of an operation."""

    name: str
    """The name of the property in JSON, for example `order_id`."""
    rules: Rules
    optional: bool
    """Tell if the value can be missing or null."""
    many: bool = False

    @property
    def label(self) -> str:
        return field_label(self.name)

    @property
    def kind(self) -> str:
        return self.rules.kind

    @property
    def multiline(self) -> bool:
        """Tell if the field uses a text area: a list or a long text."""
        if self.many:
            return True
        length = self.rules.max_length
        return self.kind == "String" and (length is None or length > MULTILINE_LENGTH)

    @property
    def helpers(self) -> set[str]:
        """The helper functions of the form file that the field uses."""
        if self.many:
            return {"textLines"}
        if self.kind in ("Integer", "Real"):
            return {"optionalNumber"} if self.optional else set()
        if self.kind == "Boolean":
            return set()
        return {"optionalText"} if self.optional else set()

    @property
    def components(self) -> set[str]:
        """The shadcn/ui components of the field."""
        result = {"Field", "FieldError", "FieldLabel"}
        if self.multiline:
            result.add("Textarea")
        elif self.kind == "Enumeration":
            result.update(("NativeSelect", "NativeSelectOption"))
        elif self.kind != "Boolean":
            result.add("Input")
        return result

    def initial(self) -> str | None:
        """Give the TypeScript value of the field in a new form, or `None` for no value."""
        if self.many:
            return None if self.optional else "[]"
        if self.optional:
            return None
        if self.kind == "Enumeration":
            return f'"{self.rules.values[0]}"' if self.rules.values else '""'
        if self.kind in ("Integer", "Real"):
            return "Number.NaN"
        if self.kind == "Boolean":
            return "false"
        return '""'

    # trace: PRD-APP-226, PRD-APP-228
    def jsx_lines(self) -> list[str]:
        """Give the lines of the element `form.Field` of the field, in the Prettier format."""
        pad = " " * FIELD_INDENT
        inner = pad + INDENT * 3
        horizontal = self.kind == "Boolean" and not self.many
        invalid = "data-invalid={isInvalid(field.state.meta)}"
        if horizontal:
            opening = [
                f"{pad}{INDENT * 2}<Field",
                f'{inner}orientation="horizontal"',
                f"{inner}{invalid}",
                f"{pad}{INDENT * 2}>",
            ]
        else:
            opening = [f"{pad}{INDENT * 2}<Field {invalid}>"]
        lines = [
            f'{pad}<form.Field name="{self.name}">',
            f"{pad}{INDENT}{{(field) => (",
            *opening,
            *jsx_text_lines(inner, "<FieldLabel htmlFor={`${formId}-${field.name}`}>", self.label),
            *self._control_lines(inner),
            f"{inner}<FieldError errors={{shownErrors(field.state.meta)}} />",
            f"{pad}{INDENT * 2}</Field>",
            f"{pad}{INDENT})}}",
            f"{pad}</form.Field>",
        ]
        return lines

    def _control_lines(self, indent: str) -> list[str]:
        """Give the lines of the control of the field."""
        deeper = indent + INDENT
        value, change = self._value_and_change()
        if self.multiline:
            tag = "Textarea"
            attributes = []
        elif self.kind == "Enumeration":
            tag = "NativeSelect"
            attributes = []
        elif self.kind == "Boolean":
            tag = "input"
            attributes = ['type="checkbox"']
        elif self.kind in ("Integer", "Real"):
            tag = "Input"
            attributes = ['type="number"', f'step="{"1" if self.kind == "Integer" else "any"}"']
        else:
            tag = "Input"
            attributes = [f'type="{_INPUT_TYPES.get(self.kind, "text")}"']
            if self.kind == "Decimal":
                attributes.append('inputMode="decimal"')
        lines = [
            f"{indent}<{tag}",
            f"{deeper}id={{`${{formId}}-${{field.name}}`}}",
            *(f"{deeper}{item}" for item in attributes),
            f"{deeper}name={{field.name}}",
            f"{deeper}{value}",
        ]
        if tag == "input":
            lines.append(f'{deeper}className="size-4"')
        lines.extend(
            (
                f"{deeper}aria-invalid={{isInvalid(field.state.meta)}}",
                f"{deeper}onBlur={{field.handleBlur}}",
                f"{deeper}onChange={{(event) => {{",
                *self._change_lines(deeper + INDENT, change),
                f"{deeper}}}}}",
            )
        )
        if tag != "NativeSelect":
            lines.append(f"{indent}/>")
            return lines
        lines.append(f"{indent}>")
        if self.optional:
            lines.extend(jsx_text_lines(deeper, '<NativeSelectOption value="">', "No value"))
        for item in self.rules.values:
            lines.extend(jsx_text_lines(deeper, f'<NativeSelectOption value="{item}">', item))
        lines.append(f"{indent}</NativeSelect>")
        return lines

    def _change_lines(self, indent: str, change: str) -> list[str]:
        """Give the lines of the body of the function `onChange` of the control.

        The value of an enumeration field is a text that the select control
        gives. The function changes its type to the type of the field value.
        """
        if self.kind != "Enumeration":
            return _call_lines(indent, "field.handleChange", change)
        return [
            f"{indent}const value = {change};",
            f"{indent}field.handleChange(value as typeof field.state.value);",
        ]

    def _value_and_change(self) -> tuple[str, str]:
        """Give the attribute of the value of the control and the argument of `handleChange`."""
        if self.many:
            value = "field.state.value" if not self.optional else "(field.state.value ?? [])"
            return (
                f'value={{{value}.join("\\n")}}',
                "textLines(event.target.value)",
            )
        if self.kind == "Boolean":
            checked = "field.state.value ?? false" if self.optional else "field.state.value"
            return f"checked={{{checked}}}", "event.target.checked"
        if self.kind in ("Integer", "Real"):
            if self.optional:
                return (
                    'value={field.state.value ?? ""}',
                    "optionalNumber(event.target.valueAsNumber)",
                )
            return (
                'value={Number.isNaN(field.state.value) ? "" : field.state.value}',
                "event.target.valueAsNumber",
            )
        if self.optional:
            return 'value={field.state.value ?? ""}', "optionalText(event.target.value)"
        return "value={field.state.value}", "event.target.value"


# trace: PRD-APP-206, PRD-APP-210, PRD-APP-225, PRD-APP-226
@dataclass(frozen=True, slots=True)
class FeatureSlice:
    """The slice of one operation with a change in `src/features/`."""

    name: str
    """The name of the operation, for example `createOrder` or `placeOrder`."""
    kind: str
    """The kind of the operation: `create`, `update`, `delete` or `custom`."""
    method: str
    """The HTTP method in lower case, for example `post`."""
    path: str
    elements_: tuple[str, ...]
    entity: EntitySlice | None
    """The entity slice of a CRUD operation, or `None` for a custom operation."""
    changed: tuple[EntitySlice | ExternalEntitySlice, ...]
    """The entity slices of the entities that the operation changes, sorted by slice name."""
    fields: tuple[FormField, ...]
    """The fields of the form, in the order of the input schema."""
    key: str | None = None
    """The name of the path parameter of the key of `update` and `delete`, for example `id`."""
    key_type: str = "string"
    custom: CustomSlice | None = None
    output_fields: tuple[ZodField, ...] = field(default=())
    external: ExternalOperation | None = None
    """The operation of an external API, or `None`."""
    external_inputs: tuple[ExternalField, ...] = field(default=())
    """The input of an external operation: the parameters and the properties of the body."""
    response: ExternalEntitySlice | None = None
    """The entity slice of the response of an external operation, or `None`."""

    @property
    def own_schemas(self) -> bool:
        """Tell if the mutation file has the input schema and the output schema of the operation."""
        return self.custom is not None or self.external is not None

    @property
    def elements(self) -> list[str]:
        return sorted(set(self.elements_))

    @property
    def slice(self) -> str:
        return slice_name(self.name)

    def folder(self, layout: FsdLayout = REACT_LAYOUT) -> str:
        """Give the folder of the slice in the project, with the layer name of the layout."""
        return layout.slice_folder(LAYER, self.name)

    @property
    def camel(self) -> str:
        return camel_case(self.name)

    @property
    def pascal(self) -> str:
        return pascal_case(self.name)

    @property
    def api_module(self) -> str:
        """The mutation module relative to the slice folder, for example `api/create-order.gen`."""
        return f"api/{file_name(self.name)}.gen"

    @property
    def ui_module(self) -> str:
        """The module of the form or of the button, for example `ui/create-order-form.gen`."""
        suffix = "button" if self.kind == "delete" else "form"
        return f"ui/{file_name(self.name, suffix)}.gen"

    @property
    def component(self) -> str:
        """The name of the React component, for example `CreateOrderForm`."""
        return f"{self.pascal}{'Button' if self.kind == 'delete' else 'Form'}"

    @property
    def hook(self) -> str:
        return f"use{self.pascal}Mutation"

    @property
    def route(self) -> str:
        return f"{self.method.upper()} {self.path}"

    @property
    def description(self) -> str:
        """The name of the operation in a comment, for example `create of the entity Order`."""
        if self.entity is not None:
            return f"{self.kind} of the entity {self.entity.name}"
        return self.name

    @property
    def submit_text(self) -> str:
        """The text of the submit button of the form."""
        if self.kind == "create":
            return "Create"
        if self.kind == "update":
            return "Save"
        return field_label(self.name)

    # The types of the operation.

    @property
    def input_type(self) -> str | None:
        """The TypeScript type of the request body, or `None` for `delete`."""
        if self.entity is not None:
            if self.kind == "delete":
                return None
            return f"{self.kind.capitalize()}{self.entity.pascal}Input"
        return f"{self.pascal}Input"

    @property
    def input_schema(self) -> str | None:
        if self.input_type is None:
            return None
        return self.input_type[0].lower() + self.input_type[1:] + "Schema"

    @property
    def output_type(self) -> str:
        """The TypeScript type of the result of the mutation."""
        if self.entity is not None:
            return "void" if self.kind == "delete" else self.entity.pascal
        if self.external is not None:
            return "void" if self.response is None else f"{self.pascal}Output"
        if self.custom is None or self.custom.output_class is None:
            return "void"
        return f"{self.pascal}Output"

    @property
    def output_schema(self) -> str | None:
        if self.entity is not None:
            return None if self.kind == "delete" else f"{self.entity.camel}Schema"
        if self.output_type == "void":
            return None
        return f"{self.camel}OutputSchema"

    @property
    def variables_type(self) -> str:
        """The TypeScript type of the variables of the mutation."""
        if self.kind == "update":
            return f"{self.pascal}Variables"
        if self.kind == "delete":
            return self.key_type
        assert self.input_type is not None
        return self.input_type

    @property
    def parameter(self) -> str:
        """The parameter of the function of the operation."""
        if self.kind == "update":
            return f"variables: {self.variables_type}"
        if self.kind == "delete":
            return f"{self.key}: {self.key_type}"
        return f"input: {self.variables_type}"

    # The lines of the mutation file.

    def api_import_lines(self, layout: FsdLayout = REACT_LAYOUT) -> list[str]:
        """Give the lines of the imports of the mutation file, after the import of React Query."""
        result: list[str] = []
        if self.entity is None and self.uses_zod:
            result.extend(('import { z } from "zod";', ""))
        by_source: dict[str, set[str]] = {}
        if self.entity is not None:
            names = by_source.setdefault(layout.import_path("entities", self.entity.slice), set())
            names.add(f"{self.entity.camel}QueryKey")
            if self.input_type is not None and self.input_schema is not None:
                names.update((f"type {self.input_type}", self.input_schema))
            if self.output_schema is not None:
                names.update((f"type {self.output_type}", self.output_schema))
        for entity in self.changed:
            source = layout.import_path("entities", entity.slice)
            by_source.setdefault(source, set()).add(f"{entity.camel}QueryKey")
        if self.response is not None:
            by_source.setdefault(layout.import_path("entities", self.response.slice), set()).add(
                self.response.schema
            )
        by_source[layout.import_path("shared", "api")] = {"apiRequest"}
        for source in sorted(by_source):
            result.extend(import_lines(sorted(by_source[source], key=_import_key), source))
        return result

    @property
    def react_query_names(self) -> list[str]:
        return ["useMutation", "useQueryClient"] if self.changed else ["useMutation"]

    @property
    def uses_zod(self) -> bool:
        return self.entity is None

    @property
    def decimal_helpers(self) -> list[str]:
        """The functions for decimal values that the input schema of a custom operation uses."""
        if self.external is not None:
            kinds = {item.rules.kind for item in self.external_inputs if item.rules is not None}
            return ["decimalValue"] if "Decimal" in kinds else []
        if self.custom is None:
            return []
        result: set[str] = set()
        for item in self.custom.inputs:
            if item.rules.kind == "Decimal":
                result.add("decimalValue" if item.rules.precision is None else "decimal")
        return sorted(result)

    def input_schema_lines(self) -> list[str]:
        """Give the lines of the input schema of a custom operation or an external operation."""
        if self.external is not None:
            return object_lines(
                "z.strictObject", [_external_input(item) for item in self.external_inputs]
            )
        assert self.custom is not None
        return object_lines(
            "z.strictObject", [_input_property(item) for item in self.custom.inputs]
        )

    @property
    def input_doc(self) -> str:
        """The comment of the input schema."""
        if self.external is not None:
            return f"The input of the operation {self.name}: the parameters and the request body."
        return f"The input of the operation {self.name}: the `in` parameters."

    @property
    def output_doc(self) -> str:
        """The comment of the output schema."""
        if self.response is not None:
            many = (
                "An array of the schema"
                if self.external and self.external.response_many
                else "The schema"
            )
            return f"The output of the operation {self.name}. {many} {self.response.name}."
        return f"The output of the operation {self.name}. A related entity is its key."

    def output_schema_lines(self) -> list[str]:
        """Give the lines of the output schema of a custom operation or an external operation."""
        if self.response is not None:
            assert self.external is not None
            value = self.response.schema
            if self.external.response_many:
                value = f"z.array({value})"
            line = f"export const {self.camel}OutputSchema = {value};"
            if len(line) <= PRINT_WIDTH:
                return [line]
            return [f"export const {self.camel}OutputSchema =", f"{INDENT}{value};"]
        assert self.custom is not None
        custom = self.custom
        if custom.entity_output is not None:
            schema = object_lines(
                "z.object", [(item.name, item.output_chain()) for item in self.output_fields]
            )
            if not custom.entity_many and not custom.entity_optional:
                return [f"export const {self.camel}OutputSchema = {schema[0]}", *schema[1:]]
            item = f"{self.camel}ItemSchema"
            outer = f"z.array({item})" if custom.entity_many else f"{item}.nullable()"
            return [
                f"const {item} = {schema[0]}",
                *schema[1:],
                "",
                f"export const {self.camel}OutputSchema = {outer};",
            ]
        schema = object_lines("z.object", [_output_property(item) for item in custom.outputs])
        return [f"export const {self.camel}OutputSchema = {schema[0]}", *schema[1:]]

    def function_lines(self) -> list[str]:
        """Give the first lines of the function of the operation."""
        result = f"Promise<{self.output_type}>"
        return signature_lines(f"export async function {self.camel}", self.parameter, f": {result}")

    def request_lines(self) -> list[str]:
        """Give the lines of the object of the request, in the call of `apiRequest`."""
        lines = [
            f'{INDENT * 2}method: "{self.method.upper()}",',
            f"{INDENT * 2}path: {self.path_expression},",
        ]
        if self.entity is not None:
            if self.input_schema is not None:
                source = "variables.input" if self.kind == "update" else "input"
                lines.append(f"{INDENT * 2}body: {self.input_schema}.parse({source}),")
            return lines
        if self.external is not None:
            lines.extend(query_lines(INDENT * 2, "data", self.external.query_parameters))
            body = self.external_inputs[len(self.external.parameters) :]
            if self.external.body is not None:
                if not body:
                    lines.append(f"{INDENT * 2}body: {{}},")
                    return lines
                lines.append(f"{INDENT * 2}body: {{")
                lines.extend(f"{INDENT * 3}{item.name}: data.{item.name}," for item in body)
                lines.append(f"{INDENT * 2}}},")
            return lines
        assert self.custom is not None
        fields = self.custom.request_fields
        if not fields:
            return lines
        if self.custom.has_body:
            lines.append(f"{INDENT * 2}body: {{")
            lines.extend(f"{INDENT * 3}{item.json_name}: data.{item.json_name}," for item in fields)
            lines.append(f"{INDENT * 2}}},")
            return lines
        lines.append(f"{INDENT * 2}query: {{")
        for item in fields:
            if item.optional:
                lines.extend(
                    (
                        f"{INDENT * 3}...(data.{item.json_name} == null",
                        f"{INDENT * 4}? {{}}",
                        f"{INDENT * 4}: {{ {item.json_name}: data.{item.json_name} }}),",
                    )
                )
            else:
                lines.append(f"{INDENT * 3}{item.json_name}: data.{item.json_name},")
        lines.append(f"{INDENT * 2}}},")
        return lines

    @property
    def path_expression(self) -> str:
        """The path of the operation as a TypeScript literal, with the path parameters."""
        if self.external is not None:
            return path_expression(self.path, "data", self.external.path_parameters)
        if self.custom is not None:
            values = {
                item.name: (f"data.{item.json_name}", _key_type(item.rules) == "string")
                for item in self.custom.path_fields
            }
        elif self.key is not None:
            source = f"variables.{self.key}" if self.kind == "update" else self.key
            values = {self.key: (source, self.key_type == "string")}
        else:
            values = {}
        path = self.path
        for name, (expression, text) in values.items():
            value = expression if text else f"String({expression})"
            path = path.replace(f"{{{name}}}", f"${{encodeURIComponent({value})}}")
        if path == self.path:
            return f'"{path}"'
        return f"`{path}`"

    def invalidate_lines(self) -> list[str]:
        """Give the lines that invalidate the queries of each changed entity (PRD-APP-225)."""
        indent = INDENT * 3
        lines: list[str] = []
        for entity in self.changed:
            key = f"{entity.camel}QueryKey"
            line = f"{indent}await queryClient.invalidateQueries({{ queryKey: {key} }});"
            if len(line) <= PRINT_WIDTH:
                lines.append(line)
            else:
                lines.extend(
                    (
                        f"{indent}await queryClient.invalidateQueries({{",
                        f"{indent}{INDENT}queryKey: {key},",
                        f"{indent}}});",
                    )
                )
        return lines

    # The lines of the form file and of the button file.

    def ui_import_lines(self, layout: FsdLayout = REACT_LAYOUT) -> list[str]:
        """Give the lines of the imports of the form file or of the button file."""
        lines: list[str] = []
        if self.kind == "delete":
            lines.extend(('import { type ReactNode } from "react";', ""))
        else:
            lines.extend(
                (
                    'import { useForm } from "@tanstack/react-form";',
                    'import { type ReactNode, useId } from "react";',
                    "",
                )
            )
        by_source: dict[str, set[str]] = {layout.import_path("shared", "api"): {"ApiError"}}
        local: set[str] = {self.hook}
        if self.entity is not None and self.kind != "delete":
            names = by_source.setdefault(layout.import_path("entities", self.entity.slice), set())
            assert self.input_type is not None and self.input_schema is not None
            names.update((f"type {self.input_type}", self.input_schema, f"type {self.output_type}"))
        elif self.kind == "update" or self.entity is None:
            assert self.input_type is not None and self.input_schema is not None
            local.update((f"type {self.input_type}", self.input_schema))
            if self.output_type != "void":
                local.add(f"type {self.output_type}")
        by_source[layout.import_path("shared", "ui")] = self.ui_components
        for source in sorted(by_source):
            lines.extend(import_lines(sorted(by_source[source], key=_import_key), source))
        lines.append("")
        lines.extend(import_lines(sorted(local, key=_import_key), f"../{self.api_module}"))
        return lines

    @property
    def ui_components(self) -> set[str]:
        result = {"Alert", "AlertDescription", "AlertTitle", "Button"}
        if self.kind == "delete":
            result.update(
                (
                    "AlertDialog",
                    "AlertDialogAction",
                    "AlertDialogCancel",
                    "AlertDialogContent",
                    "AlertDialogDescription",
                    "AlertDialogFooter",
                    "AlertDialogHeader",
                    "AlertDialogTitle",
                    "AlertDialogTrigger",
                )
            )
            return result
        result.update(("Field", "FieldGroup"))
        for item in self.fields:
            result.update(item.components)
        return result

    @property
    def form_helpers(self) -> list[str]:
        """The helper functions of the form file that the fields use, sorted."""
        result: set[str] = set()
        for item in self.fields:
            result.update(item.helpers)
        return sorted(result)

    @property
    def success_type(self) -> str:
        """The type of the property `onSuccess` of the component."""
        if self.output_type == "void":
            return "() => void"
        return f"(result: {self.output_type}) => void"

    def initial_lines(self) -> list[str]:
        """Give the lines of the constant of the first values of the form."""
        assert self.input_type is not None
        head = f"const initialValues: {self.input_type} = "
        items = [
            (item.name, value) for item in self.fields if (value := item.initial()) is not None
        ]
        if not items:
            return [f"{head}{{}};"]
        return [f"{head}{{", *(f"{INDENT}{name}: {value}," for name, value in items), "};"]

    def component_lines(self) -> list[str]:
        """Give the first lines of the function of the component."""
        names = [self.key] if self.kind in ("update", "delete") and self.key else []
        if self.kind != "delete":
            names.append("defaultValues")
        names.append("onSuccess")
        head = f"export function {self.component}("
        tail = f"}}: {self.component}Props) {{"
        line = f"{head}{{ {', '.join(names)} {tail}"
        if len(line) <= PRINT_WIDTH:
            return [line]
        return [f"{head}{{", *(f"{INDENT}{name}," for name in names), tail]

    def mutate_lines(self, indent: str) -> list[str]:
        """Give the lines that start the mutation with the values of the form."""
        if self.kind == "update":
            variables = f"{{ {self.key}, input: value }}"
        elif self.kind == "delete":
            variables = str(self.key)
        else:
            variables = "value"
        result = "" if self.output_type == "void" else "result"
        callback = [
            f"onSuccess: ({result}) => {{",
            f"{INDENT}onSuccess?.({result});",
            "},",
        ]
        if not variables.startswith("{"):
            return [
                f"{indent}mutation.mutate({variables}, {{",
                *(f"{indent}{INDENT}{line}" for line in callback),
                f"{indent}}});",
            ]
        # Prettier does not hug the last argument if the first argument is an object.
        return [
            f"{indent}mutation.mutate(",
            f"{indent}{INDENT}{variables},",
            f"{indent}{INDENT}{{",
            *(f"{indent}{INDENT * 2}{line}" for line in callback),
            f"{indent}{INDENT}}},",
            f"{indent});",
        ]

    def field_lines(self) -> list[str]:
        return [line for item in self.fields for line in item.jsx_lines()]

    def submit_lines(self, indent: str) -> list[str]:
        return jsx_text_lines(
            indent,
            '<Button type="submit" disabled={mutation.isPending}>',
            self.submit_text,
            "Button",
        )

    def dialog_title_lines(self, indent: str) -> list[str]:
        assert self.entity is not None
        return jsx_text_lines(
            indent, "<AlertDialogTitle>", f"Delete this {self.entity.name}", "AlertDialogTitle"
        )


def _import_key(name: str) -> str:
    """Sort the names of an import by the name, with no `type` keyword."""
    return name.removeprefix("type ")


def _key_type(rules: Rules) -> str:
    return _KEY_TYPES.get(rules.kind, "string")


def _input_property(item: ParameterField) -> tuple[str, list[str]]:
    """Give the name and the Zod schema of one `in` parameter, as the Pydantic input model."""
    chain = input_rule_chain(item.rules)
    if item.many:
        inner = "".join(chain)
        chain = [f"z.array({inner})"]
        if item.lower > 0:
            chain.append(f".min({item.lower})")
        if item.upper is not None:
            chain.append(f".max({item.upper})")
        if item.lower == 0:
            chain.append(".optional()")
    elif item.optional:
        chain.extend((".nullable()", ".optional()"))
    return item.json_name, chain


# trace: PRD-APP-006, PRD-APP-226
def _external_input(item: ExternalField) -> tuple[str, list[str]]:
    """Give the name and the Zod schema of one input value of an external operation."""
    assert item.rules is not None
    chain = input_rule_chain(item.rules)
    if item.many:
        chain = [f"z.array({''.join(chain)})"]
    elif item.optional:
        chain.extend((".nullable()", ".optional()"))
    return item.name, chain


def _output_property(item: ParameterField) -> tuple[str, list[str]]:
    """Give the name and the Zod schema of one `out` parameter, as the Pydantic output model."""
    chain = base_chain(item.rules)
    if item.many:
        chain = [f"z.array({''.join(chain)})"]
    elif item.optional:
        chain.append(".nullable()")
    return item.json_name, chain


def import_lines(names: Sequence[str], source: str) -> list[str]:
    """Give the lines of one import statement, with the Prettier line breaks.

    Prettier keeps an import of one name on one line, also if the line is too long.
    """
    line = f'import {{ {", ".join(names)} }} from "{source}";'
    if len(line) <= PRINT_WIDTH or len(names) == 1:
        return [line]
    return ["import {", *(f"{INDENT}{name}," for name in names), f'}} from "{source}";']


def signature_lines(head: str, parameter: str, tail: str) -> list[str]:
    """Give the first lines of a function with one parameter, with the Prettier line breaks."""
    line = f"{head}({parameter}){tail} {{"
    if len(line) <= PRINT_WIDTH:
        return [line]
    return [f"{head}(", f"{INDENT}{parameter},", f"){tail} {{"]


def jsx_text_lines(indent: str, opening: str, text: str, tag: str | None = None) -> list[str]:
    """Give the lines of a JSX element with one line of text, with the Prettier line breaks.

    `opening` is the opening tag. `tag` is the name of the closing tag. If
    it is `None`, the name comes from the opening tag. Prettier puts the
    text on a separate line if the element is too long for one line or has
    more than one attribute.
    """
    name = tag or opening[1:].split(" ", 1)[0].rstrip(">")
    line = f"{indent}{opening}{text}</{name}>"
    if len(line) <= PRINT_WIDTH and len(_ATTRIBUTE.findall(opening)) <= 1:
        return [line]
    return [f"{indent}{opening}", f"{indent}{INDENT}{text}", f"{indent}</{name}>"]


def _call_lines(indent: str, function: str, arguments: str) -> list[str]:
    """Give the lines of a call statement, with the Prettier line breaks.

    Prettier puts the arguments of a call that is too long on a separate line.
    """
    line = f"{indent}{function}({arguments});"
    if len(line) <= PRINT_WIDTH:
        return [line]
    return [f"{indent}{function}(", f"{indent}{INDENT}{arguments},", f"{indent});"]


def _entity_fields(entity: EntitySlice, operation: str) -> tuple[FormField, ...]:
    """Give the fields of the form of `create` or `update`: all fields but the key."""
    return tuple(
        FormField(
            name=item.name,
            rules=item.field.rules,
            optional=item.field.nullable or operation == "update",
        )
        for item in entity.fields
        if not item.field.key
    )


def _custom_fields(item: CustomSlice) -> tuple[FormField, ...]:
    """Give the fields of the form of a custom operation: all `in` parameters."""
    result: list[FormField] = []
    for parameter in item.inputs:
        if parameter.many and parameter.rules.kind not in _LIST_KINDS:
            raise ToolchainError(
                f"The parameter {parameter.name} of the operation {item.operation_name} is a "
                f"list of the type {parameter.rules.kind}. The React target has no form "
                "control for this list. Use a list of texts."
            )
        result.append(
            FormField(
                name=parameter.json_name,
                rules=parameter.rules,
                optional=parameter.optional or (parameter.many and parameter.lower == 0),
                many=parameter.many,
            )
        )
    return tuple(result)


# trace: PRD-APP-006, PRD-APP-226
def _external_slice(
    operation: ExternalOperation,
    api_name: str,
    inputs: tuple[ExternalField, ...],
    changed: tuple[ExternalEntitySlice, ...],
    response: ExternalEntitySlice | None,
) -> FeatureSlice:
    fields: list[FormField] = []
    for item in inputs:
        if item.rules is None:
            raise ToolchainError(
                f"The property {item.name} of the request body of the operation "
                f"{operation.name} of the external API {api_name} refers to an object schema. "
                "The React target has no form control for an object. Use scalar properties."
            )
        if item.many and item.rules.kind not in _LIST_KINDS:
            raise ToolchainError(
                f"The property {item.name} of the operation {operation.name} of the external "
                f"API {api_name} is an array of the type {item.rules.kind}. The React target "
                "has no form control for this array. Use an array of texts."
            )
        fields.append(
            FormField(name=item.name, rules=item.rules, optional=item.optional, many=item.many)
        )
    return FeatureSlice(
        name=operation.name,
        kind="custom",
        method=operation.method,
        path=operation.path,
        elements_=tuple(operation.elements),
        entity=None,
        changed=changed,
        fields=tuple(fields),
        external=operation,
        external_inputs=inputs,
        response=response,
    )


# trace: PRD-APP-006
def _external_slices(ir: Ir, application: Element) -> list[FeatureSlice]:
    """Give the feature slices of the operations of the external APIs that do not use GET."""
    by_response = {
        (item.api.identity, item.entity.identity): item
        for item in external_entity_slices(ir, application)
    }
    result: list[FeatureSlice] = []
    for api in external_apis(ir, application):
        changed = tuple(
            item
            for (owner, _), item in sorted(by_response.items(), key=lambda pair: pair[1].slice)
            if owner == api.identity and item.queries
        )
        for operation in api.operations:
            if operation.method == "get":
                continue
            inputs = list(operation.parameters)
            if operation.body is not None:
                inputs.extend(api.entities[operation.body].fields)
            names = [item.name for item in inputs]
            for name in sorted({name for name in names if names.count(name) > 1}):
                raise ToolchainError(
                    f"The operation {operation.name} of the external API {api.name} has a "
                    f'parameter and a property of the request body with the name "{name}". '
                    "The form of the operation cannot have two fields with one name."
                )
            response = (
                by_response[(api.identity, operation.response)]
                if operation.response is not None
                else None
            )
            result.append(_external_slice(operation, api.name, tuple(inputs), changed, response))
    return result


def _crud_slice(item: Slice, entity: EntitySlice) -> FeatureSlice:
    key = item.parameter if item.operation in ("update", "delete") else None
    return FeatureSlice(
        name=f"{item.operation} {entity.name}",
        kind=item.operation,
        method=item.method,
        path=item.path,
        elements_=tuple(item.elements),
        entity=entity,
        changed=(entity,),
        fields=() if item.operation == "delete" else _entity_fields(entity, item.operation),
        key=key,
        key_type=entity.key_type,
    )


def _custom_slice(item: CustomSlice, by_entity: dict[str, EntitySlice]) -> FeatureSlice:
    output: tuple[ZodField, ...] = ()
    if item.entity_output is not None:
        output = tuple(ZodField(column) for column in item.entity_output)
    changed = tuple(
        sorted(
            (by_entity[identity] for identity in item.entities if identity in by_entity),
            key=lambda entity: entity.slice,
        )
    )
    return FeatureSlice(
        name=item.collection,
        kind="custom",
        method=item.method,
        path=item.path,
        elements_=tuple(item.elements),
        entity=None,
        changed=changed,
        fields=_custom_fields(item),
        custom=item,
        output_fields=output,
    )


# trace: PRD-APP-005, PRD-APP-206, PRD-APP-210
def feature_slices(ir: Ir, application: Element) -> list[FeatureSlice]:
    """Give the feature slices of a React application, sorted by slice name.

    Each operation with a change of a called application gives one slice:
    `create`, `update`, `delete` and each custom operation that does not
    use the method GET. Each operation of a called external API that does
    not use the method GET also gives one slice (PRD-APP-006). Two
    operations with one slice name give a `ToolchainError`.
    """
    entities = entity_slices(ir, application)
    by_entity = {item.entity: item for item in entities}
    items: list[FeatureSlice] = []
    for api in api_applications(ir, application):
        found = models(ir, api)
        crud = slices(ir, api, found)
        items.extend(
            _crud_slice(item, by_entity[item.model.entity])
            for item in crud
            if item.operation in CHANGE_OPERATIONS and item.model.entity in by_entity
        )
        items.extend(
            _custom_slice(item, by_entity)
            for item in custom_slices(ir, api, found, crud)
            if item.method != "get"
        )
    items.extend(_external_slices(ir, application))
    result: dict[str, FeatureSlice] = {}
    for entry in items:
        if entry.slice in result:
            raise ToolchainError(
                f"The application {application.name} calls two operations with the "
                f'feature slice name "{entry.slice}". Give one of the operations an '
                "other name."
            )
        result[entry.slice] = entry
    return [result[name] for name in sorted(result)]


# trace: PRD-APP-017, PRD-APP-202, PRD-APP-203, PRD-APP-204, PRD-APP-210, PRD-APP-225
# trace: PRD-APP-226, PRD-APP-227, PRD-APP-228, PRD-CORE-031, PRD-TRACE-005, PRD-TRACE-006
def features_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the layer `features` of one application."""
    files: list[OutputFile] = []
    for feature in feature_slices(context.ir, context.application):
        ui_template = "button" if feature.kind == "delete" else "form"
        files.append(
            _source_file(
                context,
                f"{feature.folder(context.layout)}/{feature.api_module}.ts",
                "react/features/mutation.gen.ts.j2",
                feature,
            )
        )
        files.append(
            _source_file(
                context,
                f"{feature.folder(context.layout)}/{feature.ui_module}.tsx",
                f"react/features/{ui_template}.gen.tsx.j2",
                feature,
            )
        )
        modules = [feature.api_module, feature.ui_module]
        files.extend(
            public_api_files(context, feature.folder(context.layout), modules, feature.elements)
        )
    return files


def _source_file(
    context: ReactContext, path: str, template: str, feature: FeatureSlice
) -> OutputFile:
    file = context.generated_file(path, template, {"feature": feature}, feature.elements)
    symbols = typescript_symbols(file.content, tuple(feature.elements))
    return OutputFile(file.path, file.content, file.kind, file.part, symbols)
