# trace: PRD-APP-005, PRD-APP-202, PRD-APP-210, PRD-APP-211, PRD-APP-224
"""The entities layer of the React generator.

The generator calls `entities_files` for each `react` application. The
function gives one slice in `src/entities/<entity>/` for each exposed
entity of each application that the React application calls (`#Calls`):

- `model/<entity>.gen.ts`: the TypeScript types and the Zod schemas of the
  output, the create input and the update input (PRD-APP-210).
- `api/<entity>-queries.gen.ts`: the query keys and the TanStack Query
  options of the operations `read` and `list` (PRD-APP-210, PRD-APP-224).
- `index.gen.ts` and the create-once `index.ts`: the public API of the
  slice (PRD-APP-204).

The schemas come from the same IR entities and operations as the Pydantic
models of the called FastAPI application (PRD-APP-005). Thus this module
uses the CRUD slices of the FastAPI generator (`dsml.generate.fastapi_slices`).
The Zod schemas apply the same field rules as the Pydantic models
(PRD-APP-112, PRD-APP-211). A related entity is its key (PRD-APP-115).

The query functions call the API client `apiRequest` of the segment
`shared/api` through its public API `@/shared/api`.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate.fastapi import applications as fastapi_applications
from dsml.generate.fastapi_database import models
from dsml.generate.fastapi_slices import LIMIT_DEFAULT, LIMIT_MAX, SchemaField, Slice, slices
from dsml.generate.names import camel_case, pascal_case
from dsml.generate.react_common import (
    ReactContext,
    file_name,
    public_api_files,
    slice_folder,
    slice_name,
)
from dsml.generate.typescript_symbols import typescript_symbols
from dsml.generate.writer import OutputFile
from dsml.ir.model import Element, Ir

LAYER: Final = "entities"
"""The FSD layer of this module."""

PRINT_WIDTH: Final = 80
"""The maximum line length of the Prettier format."""

INDENT: Final = "  "
"""One level of indentation in the Prettier format."""

QUERY_OPERATIONS: Final = ("read", "list")
"""The CRUD operations that have query options. The other operations are mutations."""

_OUTPUT_TYPES: Final = {
    "Boolean": ("z", ".boolean()"),
    "Date": ("z.iso", ".date()"),
    "DateTime": ("z.iso", ".datetime({ offset: true, local: true })"),
    "Decimal": ("z", ".string()"),
    "Integer": ("z", ".int()"),
    "Real": ("z", ".number()"),
    "String": ("z", ".string()"),
    "Uuid": ("z", ".guid()"),
}
"""The Zod schema of each DSML field type in a response, as its head and its first call.

A response gives a `Decimal` value as a JSON string, so the client keeps
all of its digits. `z.guid()` accepts each UUID, as Pydantic does.
"""

_KEY_TYPES: Final = {"Integer": "number"}
"""The TypeScript type of a key of each DSML field type. Other keys are a `string`."""


# trace: PRD-APP-112, PRD-APP-115, PRD-APP-211
@dataclass(frozen=True, slots=True)
class ZodField:
    """One field of the Zod schemas of an entity: one field of its Pydantic models."""

    field: SchemaField

    @property
    def name(self) -> str:
        """The name of the field in JSON: the name of the field of the Pydantic models."""
        return self.field.name

    @property
    def decimal(self) -> bool:
        return self.field.rules.kind == "Decimal"

    def output_chain(self) -> list[str]:
        """Give the parts of the Zod schema of the field in a response.

        An output schema has no field rules, as the Pydantic output model.
        """
        chain = self._base()
        if self.field.nullable:
            chain.append(".nullable()")
        return chain

    def input_chain(self, operation: str) -> list[str]:
        """Give the parts of the Zod schema of the field in the input of `create` or `update`.

        The field rules become Zod rules (PRD-APP-112, PRD-APP-211). A
        nullable field can have the value `null` and can be missing. Each
        field of the update input can be missing (PRD-APP-111).
        """
        rules = self.field.rules
        if self.decimal:
            chain = [f"decimal({self._decimal_rules()})"]
        else:
            chain = self._base()
            if rules.min_length is not None:
                chain.append(f".min({rules.min_length})")
            if rules.max_length is not None:
                chain.append(f".max({rules.max_length})")
            if rules.min_value is not None:
                chain.append(f".min({_number(rules.min_value)})")
            if rules.max_value is not None:
                chain.append(f".max({_number(rules.max_value)})")
            if rules.pattern is not None:
                chain.append(f".regex(new RegExp({_string(rules.pattern)}))")
        if self.field.nullable:
            chain.extend((".nullable()", ".optional()"))
        elif operation == "update":
            chain.append(".optional()")
        return chain

    def _base(self) -> list[str]:
        """Give the head and the first call of the Zod schema of the field type."""
        rules = self.field.rules
        if rules.kind == "Enumeration":
            return ["z", f".enum([{', '.join(_string(value) for value in rules.values)}])"]
        return list(_OUTPUT_TYPES[rules.kind])

    def _decimal_rules(self) -> str:
        """Give the object of the rules of a decimal field, for the function `decimal`."""
        rules = self.field.rules
        precision = rules.precision or 0
        scale = rules.scale or 0
        items = [f"whole: {precision - scale}", f"places: {scale}"]
        if rules.min_value is not None:
            items.append(f"min: {_number(rules.min_value)}")
        if rules.max_value is not None:
            items.append(f"max: {_number(rules.max_value)}")
        return "{ " + ", ".join(items) + " }"


# trace: PRD-APP-005, PRD-APP-210, PRD-APP-224
@dataclass(frozen=True, slots=True)
class EntitySlice:
    """The slice of one exposed entity in `src/entities/`."""

    name: str
    """The name of the entity, for example `Order`."""
    entity: str
    """The identity of the entity."""
    operations: tuple[Slice, ...]
    """The CRUD slices of the entity in the called application, sorted by operation."""

    @property
    def elements(self) -> list[str]:
        """The identities of the header: the entity and the exposed elements, sorted."""
        return sorted({self.entity, *(item.exposed for item in self.operations)})

    @property
    def slice(self) -> str:
        """The name of the slice folder and the entity of the query keys, for example `order`."""
        return slice_name(self.name)

    @property
    def folder(self) -> str:
        return slice_folder(LAYER, self.name)

    @property
    def model_module(self) -> str:
        """The model module relative to the slice folder, for example `model/order.gen`."""
        return f"model/{file_name(self.name)}.gen"

    @property
    def queries_module(self) -> str:
        """The query module relative to the slice folder, for example `api/order-queries.gen`."""
        return f"api/{file_name(self.name, 'queries')}.gen"

    @property
    def camel(self) -> str:
        return camel_case(self.name)

    @property
    def pascal(self) -> str:
        return pascal_case(self.name)

    def operation(self, kind: str) -> Slice | None:
        return next((item for item in self.operations if item.operation == kind), None)

    @property
    def fields(self) -> tuple[ZodField, ...]:
        return tuple(ZodField(item) for item in self.operations[0].fields)

    @property
    def key(self) -> SchemaField:
        return self.operations[0].key

    @property
    def inputs(self) -> list[str]:
        """The operations with an input schema: `create` and `update`, in this order."""
        return [kind for kind in ("create", "update") if self.operation(kind) is not None]

    @property
    def queries(self) -> list[str]:
        """The operations with query options: `read` and `list`, in this order."""
        return [kind for kind in QUERY_OPERATIONS if self.operation(kind) is not None]

    @property
    def has_output(self) -> bool:
        """Tell if an operation gives the entity in a response. Only `delete` gives no body."""
        return any(item.operation != "delete" for item in self.operations)

    @property
    def uses_decimal(self) -> bool:
        """Tell if an input schema has a decimal field. Then the model file has `decimal`."""
        return bool(self.inputs) and any(
            item.decimal and not item.field.key for item in self.fields
        )

    # The lines of the model file.

    def output_lines(self) -> list[str]:
        return _object_lines("z.object", [(item.name, item.output_chain()) for item in self.fields])

    def input_lines(self, operation: str) -> list[str]:
        """Give the lines of the input schema of `create` or `update`. The key is not in it."""
        fields = [
            (item.name, item.input_chain(operation)) for item in self.fields if not item.field.key
        ]
        return _object_lines("z.strictObject", fields)

    def input_doc(self, operation: str) -> str:
        if operation == "update":
            return "The request body of the operation update. Each field is optional."
        return f"The request body of the operation create. The key `{self.key.name}` is not in it."

    def type_lines(self, name: str, function: str, schema: str) -> list[str]:
        """Give the lines of a type alias of a Zod schema, with the Prettier line breaks.

        `function` is `infer` for the output type or `input` for the input type.
        """
        line = f"export type {name} = z.{function}<typeof {schema}>;"
        if len(line) <= PRINT_WIDTH:
            return [line]
        return [f"export type {name} = z.{function}<", f"{INDENT}typeof {schema}", ">;"]

    # The data of the query file.

    def model_import_lines(self) -> list[str]:
        """Give the lines of the import of the schemas from the model module of the slice."""
        names = sorted(
            [f"{self.camel}PageSchema"] * ("list" in self.queries)
            + [f"{self.camel}Schema"] * ("read" in self.queries)
        )
        source = f'"../{self.model_module}"'
        line = f"import {{ {', '.join(names)} }} from {source};"
        if len(line) <= PRINT_WIDTH:
            return [line]
        return ["import {", *(f"{INDENT}{name}," for name in names), f"}} from {source};"]

    @property
    def key_type(self) -> str:
        return _KEY_TYPES.get(self.key.rules.kind, "string")

    @property
    def read_parameter(self) -> str:
        """The name of the path parameter of the key of `read`, for example `id`."""
        item = self.operation("read")
        return item.parameter if item is not None and item.parameter else self.key.name

    @property
    def read_path(self) -> str:
        """The path of `read` as a TypeScript template literal."""
        item = self.operation("read")
        assert item is not None
        parameter = self.read_parameter
        value = parameter if self.key_type == "string" else f"String({parameter})"
        path = item.path.replace(f"{{{parameter}}}", f"${{encodeURIComponent({value})}}")
        return f"`{path}`"

    @property
    def list_path(self) -> str:
        item = self.operation("list")
        assert item is not None
        return _string(item.path)

    def route(self, kind: str) -> str:
        """Give the method and the path of an operation, for example `GET /orders/{id}`."""
        item = self.operation(kind)
        assert item is not None
        return f"{item.method.upper()} {item.path}"

    def signature(self, function: str, parameters: str) -> list[str]:
        """Give the first lines of an exported function, with the Prettier line breaks."""
        line = f"export function {function}({parameters}) {{"
        if len(line) <= PRINT_WIDTH:
            return [line]
        return [f"export function {function}(", f"{INDENT}{parameters},", ") {"]


# trace: PRD-APP-005
def called_applications(ir: Ir, application: Element) -> list[Element]:
    """Give the FastAPI applications that an application calls (`#Calls`), sorted by identity."""
    called = {
        link.target
        for link in ir.links
        if link.type == "calls" and link.source == application.identity
    }
    return [item for item in fastapi_applications(ir) if item.identity in called]


# trace: PRD-APP-005, PRD-APP-210
def entity_slices(ir: Ir, application: Element) -> list[EntitySlice]:
    """Give the entity slices of a React application, sorted by slice name.

    Each exposed entity of a called application gives one slice. Two called
    applications that expose the same entity, or two entities with one slice
    name, give a `ToolchainError`.
    """
    result: dict[str, EntitySlice] = {}
    for api in called_applications(ir, application):
        by_entity: dict[str, list[Slice]] = {}
        for item in slices(ir, api, models(ir, api)):
            by_entity.setdefault(item.model.entity, []).append(item)
        for entity, items in sorted(by_entity.items()):
            name = items[0].entity_name
            entry = EntitySlice(name, entity, tuple(sorted(items, key=lambda item: item.operation)))
            if entry.slice in result:
                raise ToolchainError(
                    f"The application {application.name} calls two applications that expose "
                    f'an entity with the slice name "{entry.slice}". Expose the entity in one '
                    "called application only."
                )
            result[entry.slice] = entry
    return [result[name] for name in sorted(result)]


# trace: PRD-APP-017, PRD-APP-202, PRD-APP-204, PRD-APP-210, PRD-APP-211, PRD-APP-224
# trace: PRD-CORE-031, PRD-TRACE-005, PRD-TRACE-006
def entities_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the layer `entities` of one application."""
    files: list[OutputFile] = []
    for entity in entity_slices(context.ir, context.application):
        modules = [entity.model_module]
        files.append(
            _source_file(
                context,
                f"{entity.folder}/{entity.model_module}.ts",
                "react/entities/model.gen.ts.j2",
                entity,
            )
        )
        if entity.queries:
            modules.append(entity.queries_module)
            files.append(
                _source_file(
                    context,
                    f"{entity.folder}/{entity.queries_module}.ts",
                    "react/entities/queries.gen.ts.j2",
                    entity,
                )
            )
        files.extend(public_api_files(context, entity.folder, modules, entity.elements))
    return files


def _source_file(
    context: ReactContext, path: str, template: str, entity: EntitySlice
) -> OutputFile:
    data: dict[str, object] = {
        "entity": entity,
        "limit_default": LIMIT_DEFAULT,
        "limit_max": LIMIT_MAX,
    }
    file = context.generated_file(path, template, data, entity.elements)
    symbols = typescript_symbols(file.content, tuple(entity.elements))
    return OutputFile(file.path, file.content, file.kind, file.part, symbols)


def _object_lines(function: str, fields: Sequence[tuple[str, list[str]]]) -> list[str]:
    """Give the lines of a Zod object schema in the Prettier format, with no last line end."""
    if not fields:
        return [f"{function}({{}});"]
    lines = [f"{function}({{"]
    for name, chain in fields:
        lines.extend(_property_lines(name, chain))
    lines.append("});")
    return lines


def _property_lines(name: str, chain: list[str]) -> list[str]:
    """Give the lines of one property of an object in the Prettier format.

    A property that is too long for one line becomes a member chain with one
    call on each line, as Prettier writes it. Prettier does not divide a
    chain with two calls or fewer after its head.
    """
    line = f"{INDENT}{name}: {''.join(chain)},"
    if len(line) <= PRINT_WIDTH or len(chain) <= 3:
        return [line]
    deeper = INDENT * 2
    return [
        f"{INDENT}{name}: {chain[0]}",
        *(f"{deeper}{part}" for part in chain[1:-1]),
        f"{deeper}{chain[-1]},",
    ]


def _number(value: int | float) -> str:
    """Give a number in the Prettier format of JavaScript."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return repr(value).replace("e+", "e")


def _string(text: str) -> str:
    """Give a JavaScript string literal in the Prettier format.

    Prettier uses double quotes, except when the text has more double
    quotes than single quotes.
    """
    if text.count('"') > text.count("'"):
        escaped = text.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    return json.dumps(text, ensure_ascii=False)
