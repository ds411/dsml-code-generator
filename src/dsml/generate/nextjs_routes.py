# trace: PRD-APP-008, PRD-APP-014, PRD-APP-310, PRD-APP-311, PRD-APP-312, PRD-APP-313
# trace: PRD-CORE-045
"""The route handlers and server functions of the Next.js generator (story #186).

The Next.js generator (`dsml.generate.nextjs`) calls the function
`routes_files` for each `nextjs` application. Each operation of the
application gets these files (PRD-APP-310, PRD-APP-313):

- `src/_app/api-routes/<operation>.gen.ts`: the route handler. It applies
  the role check, validates the input with the Zod schema of the operation,
  calls the server function and gives JSON or problem details
  (PRD-APP-008, PRD-APP-014, PRD-APP-312).
- `app/api/<path>/route.ts`: the route file. It re-exports the route
  handler of each operation with the path (PRD-APP-302).
- `src/features/<operation>/api/<operation>.server.gen.ts` for a CRUD
  operation: the server function with the Drizzle schema.
- `src/features/<operation>/api/<operation>.server.ts` for a custom
  operation: a create-once stub. The route handler calls the typed function
  of the stub, thus a type check finds a difference (PRD-CORE-045). Until a
  developer writes the logic, the function gives HTTP 501.
- `index.server.gen.ts` and the create-once `index.server.ts` of the
  feature slice (PRD-APP-305).

The REST contract is the contract of the FastAPI target with the path prefix
`/api` (PRD-APP-311): the methods and the paths of the operations, the HTTP
status codes and the `list` limits. The module also writes the segment
`src/shared/http/`: the function `routeHandler`, the class `ProblemError` and
the change of database errors into API errors (PRD-APP-113).

The code uses import aliases, for example `orderTable as table`. Thus most
lines have the same length for each entity, and the generator can write them
in the Prettier format.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from http import HTTPStatus
from typing import Final

from dsml.errors import ToolchainError
from dsml.generate.fastapi_database import models
from dsml.generate.fastapi_openapi import PROBLEM_MEDIA_TYPE
from dsml.generate.fastapi_operations import CustomSlice, ParameterField, custom_slices
from dsml.generate.fastapi_slices import (
    LIMIT_DEFAULT,
    LIMIT_MAX,
    SchemaField,
    Slice,
    slices,
)
from dsml.generate.names import camel_case, pascal_case
from dsml.generate.nextjs_database import table_variable
from dsml.generate.react_common import (
    ReactContext,
    file_name,
    public_api_files,
    server_api_files,
    slice_name,
)
from dsml.generate.react_entities import INDENT, PRINT_WIDTH, EntitySlice, entity_slices
from dsml.generate.react_features import FeatureSlice, custom_feature_slice
from dsml.generate.typescript_symbols import typescript_symbols
from dsml.generate.writer import Kind, OutputFile

API_PREFIX: Final = "/api"
"""The path prefix of the operations (PRD-APP-311)."""

API_FOLDER: Final = f"app{API_PREFIX}"
"""The folder of the route files of the operations: the path prefix `/api` (PRD-APP-311)."""

ROUTES_SEGMENT: Final = "src/_app/api-routes"
"""The segment of the route handlers in the layer `app` (PRD-APP-310)."""

HTTP_SEGMENT: Final = "src/shared/http"
"""The segment of the common parts of the route handlers."""

HTTP_MODULE: Final = "route.server.gen"
"""The server-only module of the segment `src/shared/http`."""

PROBLEM_STATUSES: Final = (400, 401, 403, 404, 409, 422, 500, 501)
"""The HTTP statuses of the problem details responses that have a title."""

SUCCESS_STATUSES: Final = {"create": 201, "delete": 204}
"""The HTTP status of a success response of each CRUD operation that does not give 200."""

_SERVER_TEMPLATES: Final = {
    "create": "nextjs/routes/create.server.gen.ts.j2",
    "delete": "nextjs/routes/delete.server.gen.ts.j2",
    "list": "nextjs/routes/list.server.gen.ts.j2",
    "read": "nextjs/routes/read.server.gen.ts.j2",
    "update": "nextjs/routes/update.server.gen.ts.j2",
}

# The function that changes the text of a path parameter or of a query
# parameter into the value of a field type. The other types stay a text.
_PARAMETER_FUNCTIONS: Final = {
    "Boolean": "booleanParameter",
    "Integer": "numberParameter",
    "Real": "numberParameter",
}

# The Zod schema of a key in a path, for each key type. The other types are
# a text.
_KEY_SCHEMAS: Final = {
    "Integer": "z.preprocess(numberParameter, z.int())",
    "Uuid": "z.guid()",
}


# trace: PRD-APP-310, PRD-APP-311
@dataclass(frozen=True, slots=True)
class Operation:
    """One operation of the application: one route handler and one server function."""

    name: str
    """The name of the operation, for example `createOrder` or `cancelOrder`."""
    kind: str
    """The CRUD kind of the operation, or `custom`."""
    method: str
    """The HTTP method in lower case, for example `post`."""
    path: str
    """The path of the operation in the model, for example `/orders/{id}`."""
    elements: tuple[str, ...]
    public: bool
    roles: tuple[str, ...]
    crud: Slice | None = None
    entity: EntitySlice | None = None
    custom: CustomSlice | None = None
    feature: FeatureSlice | None = None
    """The feature slice of the Zod schemas of a custom operation."""
    own_schemas: bool = False
    """Tell if the server slice has the schemas of the custom operation (method GET)."""
    slugs: Mapping[str, str] = field(default_factory=dict[str, str])
    """The name of the dynamic segment of the route folder for each path parameter."""

    # The names.

    @property
    def slice(self) -> str:
        """The name of the feature slice and of the files, for example `create-order`."""
        return slice_name(self.name)

    @property
    def pascal(self) -> str:
        return pascal_case(self.name)

    @property
    def server_function(self) -> str:
        """The name of the server function, for example `handleCreateOrder`."""
        return f"handle{self.pascal}"

    @property
    def http_method(self) -> str:
        return self.method.upper()

    @property
    def route(self) -> str:
        return f"{self.http_method} {self.path}"

    @property
    def folder(self) -> str:
        """The folder of the route file, for example `app/api/orders/[id]`."""
        parts = [API_FOLDER]
        for segment in self.path.strip("/").split("/"):
            if segment.startswith("{") and segment.endswith("}"):
                parts.append(f"[{self.slugs[segment[1:-1]]}]")
            elif segment:
                parts.append(segment)
        return "/".join(parts)

    @property
    def description(self) -> str:
        """The name of the operation in a comment, for example `create of the entity Order`."""
        if self.entity is not None:
            return f"{self.kind} of the entity {self.entity.name}"
        return self.name

    @property
    def server_module(self) -> str:
        """The server module relative to the slice folder, for example `api/x.server.gen`."""
        if self.custom is not None:
            return f"api/{file_name(self.name)}.server"
        return f"api/{file_name(self.name)}.server.gen"

    @property
    def schemas_module(self) -> str:
        """The module of the schemas of a custom operation relative to the slice folder."""
        if self.own_schemas:
            return f"model/{file_name(self.name, 'schemas')}.gen"
        assert self.feature is not None
        return self.feature.api_module

    @property
    def success_status(self) -> int:
        """The HTTP status of a success response."""
        if self.custom is not None:
            return 204 if self.output_type is None else 200
        return SUCCESS_STATUSES.get(self.kind, 200)

    @property
    def path_parameters(self) -> list[str]:
        """The names of the path parameters in the order of the path."""
        return [
            segment[1:-1]
            for segment in self.path.split("/")
            if segment.startswith("{") and segment.endswith("}")
        ]

    # The access rule.

    def access_lines(self) -> list[str]:
        """Give the lines of the constant `ACCESS`: the attributes `public` and `allowedRoles`."""
        roles = [f'"{role}"' for role in self.roles]
        lines = ["const ACCESS: Access = {", f"{INDENT}public: {str(self.public).lower()},"]
        lines.extend(array_lines(INDENT, "roles: ", roles, ","))
        lines.append("};")
        return lines

    # The data of the route handler of a custom operation.

    @property
    def input_type(self) -> str:
        assert self.feature is not None and self.feature.input_type is not None
        return self.feature.input_type

    @property
    def output_type(self) -> str | None:
        """The TypeScript type of the output of a custom operation, or `None` if it has none."""
        assert self.feature is not None
        return None if self.feature.output_type == "void" else self.feature.output_type

    @property
    def request_location(self) -> str:
        """The location of the input values of a custom operation in the request."""
        assert self.custom is not None
        if not self.custom.request_fields:
            return "path"
        return "body" if self.custom.has_body else "query"

    @property
    def uses_request(self) -> bool:
        """Tell if the route handler reads the request: the body or the query."""
        if self.custom is not None:
            return bool(self.custom.request_fields)
        return self.kind in ("create", "update", "list")

    @property
    def uses_context(self) -> bool:
        """Tell if the route handler reads the path parameters."""
        return bool(self.path_parameters)

    @property
    def uses_session(self) -> bool:
        return self.custom is not None

    def handle_lines(self) -> list[str]:
        """Give the first lines of the function `handle` of the route handler."""
        parameters: list[str] = []
        if self.uses_request or self.uses_context or self.uses_session:
            name = "request" if self.uses_request else "_request"
            parameters.append(f"{name}: Request")
        if self.uses_context or self.uses_session:
            name = "context" if self.uses_context else "_context"
            parameters.append(f"{name}: Context" if self.uses_context else f"{name}: unknown")
        if self.uses_session:
            parameters.append("session: Session | undefined")
        return signature_lines("async function handle", parameters, ": Promise<Response>")

    def value_lines(self) -> list[str]:
        """Give the lines of the input value of a custom operation, before the validation."""
        assert self.custom is not None
        lines = ["const value = {"]
        if self.custom.request_fields and self.custom.has_body:
            lines.append(f"{INDENT}...(await readJsonObject(request)),")
        elif self.custom.request_fields:
            for item in self.custom.request_fields:
                lines.append(f"{INDENT}{item.json_name}: {_query_value(item)},")
        for item in self.custom.path_fields:
            source = f"params.{self.slugs[item.name]}"
            function = _PARAMETER_FUNCTIONS.get(item.rules.kind)
            value = source if function is None else f"{function}({source})"
            lines.append(f"{INDENT}{item.json_name}: {value},")
        if len(lines) == 1:
            return ["const value = {};"]
        lines.append("};")
        return lines

    def call_lines(self) -> list[str]:
        """Give the lines of the call of the server function in the route handler."""
        if self.custom is not None:
            call = "handleOperation(input, session)"
            if self.output_type is None:
                return [f"await {call};"]
            return [f"const result: Output = await {call};"]
        key = f"path.{self.slugs[self.crud_parameter]}" if self.crud_parameter else None
        arguments = {
            "create": ["input"],
            "read": [key],
            "update": [key, "input"],
            "delete": [key],
            "list": ["query.limit", "query.offset"],
        }[self.kind]
        call = f"handleOperation({', '.join(str(item) for item in arguments)})"
        if self.kind == "delete":
            return [f"await {call};"]
        return [f"const result = await {call};"]

    @property
    def crud_parameter(self) -> str | None:
        assert self.crud is not None
        return self.crud.parameter

    def path_schema_lines(self) -> list[str]:
        """Give the lines of the Zod schema of the path parameters of a CRUD operation."""
        assert self.entity is not None
        parameter = self.crud_parameter
        assert parameter is not None
        schema = _KEY_SCHEMAS.get(self.entity.key.rules.kind, "z.string()")
        return [
            "const pathSchema = z.object({",
            f"{INDENT}{self.slugs[parameter]}: {schema},",
            "});",
        ]

    @property
    def uses_number_parameter(self) -> bool:
        if self.custom is not None:
            fields = [*self.custom.path_fields, *self.custom.request_fields]
            if self.custom.has_body:
                fields = list(self.custom.path_fields)
            return any(
                _PARAMETER_FUNCTIONS.get(item.rules.kind) == "numberParameter" for item in fields
            )
        if self.kind == "list":
            return True
        return (
            self.entity is not None
            and self.entity.key.rules.kind == "Integer"
            and self.uses_context
        )

    @property
    def uses_boolean_parameter(self) -> bool:
        if self.custom is None:
            return False
        fields = list(self.custom.path_fields)
        if not self.custom.has_body:
            fields.extend(self.custom.request_fields)
        return any(
            _PARAMETER_FUNCTIONS.get(item.rules.kind) == "booleanParameter" for item in fields
        )

    @property
    def uses_zod(self) -> bool:
        """Tell if the route handler has its own Zod schema: the path or the query."""
        return self.custom is None and (self.kind == "list" or self.crud_parameter is not None)

    def http_names(self) -> list[str]:
        """Give the names that the route handler imports from the segment `shared/http`."""
        names = {"parseInput", "routeHandler"}
        if self.uses_number_parameter:
            names.add("numberParameter")
        if self.uses_boolean_parameter:
            names.add("booleanParameter")
        if self.kind in ("create", "update"):
            names.add("readJson")
        if self.custom is not None and self.custom.request_fields and self.custom.has_body:
            names.add("readJsonObject")
        return sorted(names)

    def import_lines(self, http_source: str, auth_source: str) -> list[str]:
        """Give the lines of the imports of the route handler, after the import of Zod."""
        lines: list[str] = []
        if self.entity is not None and self.kind in ("create", "update"):
            schema = f"{self.kind}{self.entity.pascal}InputSchema"
            lines.extend(
                import_lines([f"{schema} as inputSchema"], f"@/entities/{self.entity.slice}")
            )
        if self.custom is not None:
            names = [f"{self.input_schema} as inputSchema"]
            if self.output_type is not None:
                names.append(f"type {self.output_type} as Output")
            lines.extend(import_lines(names, f"@/features/{self.slice}"))
        lines.extend(
            import_lines(
                [f"{self.server_function} as handleOperation"],
                f"@/features/{self.slice}/index.server",
            )
        )
        auth = ["Access", "Session"] if self.uses_session else ["Access"]
        lines.extend(import_lines(auth, auth_source, type_only=True))
        lines.extend(import_lines(self.http_names(), http_source))
        return lines

    @property
    def input_schema(self) -> str:
        assert self.feature is not None and self.feature.input_schema is not None
        return self.feature.input_schema

    # The data of the create-once stub of a custom operation.

    def stub_import_lines(self) -> list[str]:
        """Give the line of the import of the types of the schemas into the stub."""
        names = [self.input_type]
        if self.output_type is not None:
            names.append(self.output_type)
        module = self.schemas_module.removeprefix("api/")
        source = f"./{module}" if not self.own_schemas else f"../{module}"
        return import_lines(sorted(names), source, type_only=True)

    def handler_type_lines(self) -> list[str]:
        """Give the lines of the type of the server function of a custom operation."""
        result = f"Promise<{self.output_type or 'void'}>"
        parameters = [f"input: {self.input_type}", "session: Session | undefined"]
        line = f"type Handler = ({', '.join(parameters)}) => {result};"
        if len(line) <= PRINT_WIDTH:
            return [line]
        return ["type Handler = (", *(f"{INDENT}{item}," for item in parameters), f") => {result};"]

    @property
    def context_doc(self) -> str:
        return f"The context of the route `{self.folder}`."

    def params_lines(self) -> list[str]:
        """Give the lines of the interface of the path parameters of the route."""
        names = sorted({self.slugs[name] for name in self.path_parameters})
        return ["interface Params {", *(f"{INDENT}{name}: string;" for name in names), "}"]


# trace: PRD-APP-111, PRD-APP-113, PRD-APP-114, PRD-APP-115, PRD-APP-313
@dataclass(frozen=True, slots=True)
class ServerFunction:
    """The server function of one CRUD operation, with the Drizzle schema."""

    operation: Operation

    @property
    def entity(self) -> EntitySlice:
        assert self.operation.entity is not None
        return self.operation.entity

    @property
    def crud(self) -> Slice:
        assert self.operation.crud is not None
        return self.operation.crud

    @property
    def table(self) -> str:
        return self.crud.model.table

    @property
    def fields(self) -> tuple[SchemaField, ...]:
        return self.crud.fields

    @property
    def key(self) -> SchemaField:
        return self.crud.key

    @property
    def key_type(self) -> str:
        return self.entity.key_type

    def entity_import_lines(self) -> list[str]:
        """Give the lines of the import of the types of the entity slice."""
        entity = self.entity
        names = {
            "create": [f"Create{entity.pascal}Input as Input", f"{entity.pascal} as Entity"],
            "read": [f"{entity.pascal} as Entity"],
            "update": [f"Update{entity.pascal}Input as Input", f"{entity.pascal} as Entity"],
            "delete": [],
            "list": [f"{entity.pascal} as Entity", f"{entity.pascal}Page as Page"],
        }[self.operation.kind]
        if not names:
            return []
        return import_lines(sorted(names), f"@/entities/{entity.slice}", type_only=True)

    def db_import_lines(self) -> list[str]:
        """Give the lines of the import of the table and of the row types."""
        pascal = pascal_case(self.table)
        names = [f"{table_variable(self.table)} as table"]
        if self.operation.kind != "delete":
            names.append(f"type {pascal}Row as Row")
        if self.operation.kind in ("create", "update"):
            names.append(f"type New{pascal}Row as NewRow")
        return import_lines(names, "@/shared/db")

    def http_names(self) -> list[str]:
        kind = self.operation.kind
        names: set[str] = set()
        if kind in ("create", "update", "delete"):
            names.add("databaseProblem")
        if kind in ("read", "update", "delete"):
            names.add("ProblemError")
        return sorted(names, key=str.lower)

    @property
    def key_line(self) -> str:
        return f"const KEY = table.{camel_case(self.key.name)};"

    @property
    def not_found(self) -> str:
        return f"No entity {self.entity.name} has this key."

    def entity_lines(self) -> list[str]:
        """Give the lines of the function that gives the entity of a row (PRD-APP-115)."""
        lines = ["function entityOf(row: Row): Entity {", f"{INDENT}return {{"]
        for item in self.fields:
            prop = camel_case(item.name)
            value = f"row.{prop}"
            if item.rules.kind == "DateTime":
                value = (
                    f"{value}?.toISOString() ?? null" if item.nullable else f"{value}.toISOString()"
                )
            lines.extend(property_lines(INDENT * 2, item.name, value))
        lines.extend([f"{INDENT}}};", "}"])
        return lines

    def values_lines(self) -> list[str]:
        """Give the lines of the values of the row of `create` or `update`."""
        kind = self.operation.kind
        head = (
            "const values: NewRow = {" if kind == "create" else "const values: Partial<NewRow> = {"
        )
        lines = [head]
        for item in self.fields:
            if item.key:
                if kind == "create":
                    lines.append(f"{INDENT * 2}{camel_case(item.name)}: randomUUID(),")
                continue
            source = f"input.{item.name}"
            absent = kind == "update" or item.nullable
            value = _input_value(item.rules.kind, source, absent)
            lines.extend(property_lines(INDENT * 2, camel_case(item.name), value))
        lines.append(f"{INDENT}}};")
        return [f"{INDENT}{lines[0]}", *lines[1:]]

    @property
    def signature(self) -> list[str]:
        """Give the first lines of the server function."""
        key = f"key: {self.key_type}"
        parameters, result = {
            "create": (["input: Input"], "Entity"),
            "read": ([key], "Entity"),
            "update": ([key, "input: Input"], "Entity"),
            "delete": ([key], "void"),
            "list": (["limit: number", "offset: number"], "Page"),
        }[self.operation.kind]
        head = f"export async function {self.operation.server_function}"
        return signature_lines(head, parameters, f": Promise<{result}>")


# trace: PRD-APP-008, PRD-APP-014, PRD-APP-302, PRD-APP-305, PRD-APP-310, PRD-APP-311
# trace: PRD-APP-312, PRD-APP-313, PRD-CORE-044, PRD-CORE-045, PRD-TRACE-005
def routes_files(context: ReactContext) -> list[OutputFile]:
    """Give the files of the route handlers and server functions of one application."""
    operations = application_operations(context)
    files = http_files(context)
    for operation in operations:
        files.append(route_handler_file(context, operation))
        files.extend(server_files(context, operation))
    by_folder: dict[str, list[Operation]] = {}
    for operation in operations:
        by_folder.setdefault(operation.folder, []).append(operation)
    for folder, items in sorted(by_folder.items()):
        files.append(route_file(context, folder, items))
    return files


# trace: PRD-APP-110, PRD-APP-310, PRD-APP-311
def application_operations(context: ReactContext) -> list[Operation]:
    """Give the operations of the application, sorted by name.

    Two operations with one name, or two operations with the same method and
    path, give a `ToolchainError`. A create operation needs a key of the type
    `Uuid`, because the server function makes the key.
    """
    ir = context.ir
    application = context.application
    found = models(ir, application)
    crud = slices(ir, application, found)
    entities = {item.entity: item for item in entity_slices(ir, application)}
    items: list[Operation] = []
    for item in crud:
        entity = entities[item.model.entity]
        if item.operation == "create" and item.key.rules.kind != "Uuid":
            raise ToolchainError(
                f"The entity {entity.name} has a key of the type {item.key.rules.kind}. The "
                "create operation of the Next.js target needs a key of the type Uuid."
            )
        items.append(
            Operation(
                name=camel_case(f"{item.operation} {entity.name}"),
                kind=item.operation,
                method=item.method,
                path=item.path,
                elements=tuple(item.elements),
                public=item.public,
                roles=item.roles,
                crud=item,
                entity=entity,
            )
        )
    for custom in custom_slices(ir, application, found, crud):
        feature = custom_feature_slice(custom, entities)
        items.append(
            Operation(
                name=custom.collection,
                kind="custom",
                method=custom.method,
                path=custom.path,
                elements=tuple(custom.elements),
                public=custom.public,
                roles=custom.roles,
                custom=custom,
                feature=feature,
                own_schemas=custom.method == "get",
            )
        )
    check_names(application.name, items)
    slugs = path_slugs([item.path for item in items])
    result = [replace(item, slugs=slugs[item.path]) for item in items]
    return sorted(result, key=lambda item: item.slice)


def check_names(application: str, items: Sequence[Operation]) -> None:
    """Raise a `ToolchainError` for two operations with one name, or with one method and path."""
    names: dict[str, Operation] = {}
    routes: dict[tuple[str, str], Operation] = {}
    for item in items:
        if item.slice in names:
            raise ToolchainError(
                f'The application {application} has two operations with the name "{item.slice}". '
                "Give one of the operations an other name."
            )
        names[item.slice] = item
        route = (item.method, _route_pattern(item.path))
        if route in routes:
            raise ToolchainError(
                f"The operations {routes[route].name} and {item.name} of the application "
                f"{application} have the same method and path {item.route}. Give one of the "
                "operations an other path."
            )
        routes[route] = item


def _route_pattern(path: str) -> str:
    """Give the path with `{}` for each path parameter, for example `/orders/{}`."""
    return "/".join(
        "{}" if part.startswith("{") and part.endswith("}") else part for part in path.split("/")
    )


# trace: PRD-APP-302, PRD-APP-310
def path_slugs(paths: Iterable[str]) -> dict[str, dict[str, str]]:
    """Give the name of the dynamic segment of each path parameter of each path.

    Next.js permits one name for the dynamic segment at one place of the
    route tree. Thus all the path parameters at one place get one name: the
    first name in sorted order. For example, `/orders/{id}` and
    `/orders/{orderId}/cancel` give the folders `orders/[id]` and
    `orders/[id]/cancel`.
    """
    names: dict[tuple[str, ...], set[str]] = {}
    for path in paths:
        prefix: tuple[str, ...] = ()
        for part in path.strip("/").split("/"):
            if part.startswith("{") and part.endswith("}"):
                names.setdefault(prefix, set()).add(part[1:-1])
                prefix = (*prefix, "{}")
            else:
                prefix = (*prefix, part)
    result: dict[str, dict[str, str]] = {}
    for path in paths:
        prefix = ()
        slugs: dict[str, str] = {}
        for part in path.strip("/").split("/"):
            if part.startswith("{") and part.endswith("}"):
                slugs[part[1:-1]] = min(names[prefix])
                prefix = (*prefix, "{}")
            else:
                prefix = (*prefix, part)
        result[path] = slugs
    return result


# trace: PRD-APP-008, PRD-APP-014, PRD-APP-113, PRD-APP-305, PRD-APP-312, PRD-TRACE-005
def http_files(context: ReactContext) -> list[OutputFile]:
    """Give the segment `src/shared/http`: the common parts of the route handlers."""
    elements = context.elements
    data: dict[str, object] = {
        "problem_media_type": PROBLEM_MEDIA_TYPE,
        "titles": [(status, HTTPStatus(status).phrase) for status in PROBLEM_STATUSES],
        "unprocessable": int(HTTPStatus.UNPROCESSABLE_CONTENT),
    }
    module = context.generated_file(
        f"{HTTP_SEGMENT}/{HTTP_MODULE}.ts", "nextjs/routes/route.server.gen.ts.j2", data, elements
    )
    files = [_with_symbols(module, elements)]
    files.extend(server_api_files(context, HTTP_SEGMENT, [HTTP_MODULE], elements))
    return files


# trace: PRD-APP-008, PRD-APP-014, PRD-APP-114, PRD-APP-310, PRD-APP-311, PRD-APP-312
# trace: PRD-CORE-045, PRD-TRACE-005
def route_handler_file(context: ReactContext, operation: Operation) -> OutputFile:
    """Give `src/_app/api-routes/<operation>.gen.ts`: the route handler of one operation."""
    layout = context.layout
    data: dict[str, object] = {
        "operation": operation,
        "http_source": f"{layout.import_path('shared', 'http')}/index.server",
        "auth_source": layout.import_path("shared", "auth"),
        "limit_default": LIMIT_DEFAULT,
        "limit_max": LIMIT_MAX,
    }
    file = context.generated_file(
        f"{ROUTES_SEGMENT}/{operation.slice}.gen.ts",
        "nextjs/routes/route-handler.gen.ts.j2",
        data,
        operation.elements,
    )
    return _with_symbols(file, operation.elements)


# trace: PRD-APP-302, PRD-APP-310
def route_file(context: ReactContext, folder: str, operations: Sequence[Operation]) -> OutputFile:
    """Give `app/api/<path>/route.ts`: the re-export of the route handler of each method."""
    exports = sorted(
        (item.http_method, f"{context.layout.import_path('app')}/api-routes/{item.slice}.gen")
        for item in operations
    )
    elements = sorted({element for item in operations for element in item.elements})
    return context.generated_file(
        f"{folder}/route.ts", "nextjs/routes/route.ts.j2", {"exports": exports}, elements
    )


# trace: PRD-APP-111, PRD-APP-113, PRD-APP-114, PRD-APP-115, PRD-APP-305, PRD-APP-313
# trace: PRD-CORE-044, PRD-CORE-045, PRD-TRACE-005
def server_files(context: ReactContext, operation: Operation) -> list[OutputFile]:
    """Give the server function of one operation and the server-only public API of its slice.

    A CRUD operation gets the generated server function. A custom operation
    gets the create-once stub. A custom operation with the method GET has
    no client slice, thus its slice also gets the module of its schemas and
    the public API `index.ts`.
    """
    folder = context.layout.slice_folder("features", operation.name)
    elements = operation.elements
    layout = context.layout
    data: dict[str, object] = {
        "operation": operation,
        "http_source": f"{layout.import_path('shared', 'http')}/index.server",
        "db_source": f"{layout.import_path('shared', 'db')}/index.server",
        "auth_source": layout.import_path("shared", "auth"),
    }
    files: list[OutputFile] = []
    if operation.custom is None:
        data["server"] = ServerFunction(operation)
        file = context.generated_file(
            f"{folder}/{operation.server_module}.ts",
            _SERVER_TEMPLATES[operation.kind],
            data,
            elements,
        )
        files.append(_with_symbols(file, elements))
    else:
        content = context.engine.render_bytes("nextjs/routes/stub.server.ts.j2", data)
        path = f"{context.folder}{folder}/{operation.server_module}.ts"
        files.append(OutputFile(path, content, Kind.CREATE_ONCE, context.part))
    if operation.own_schemas:
        assert operation.feature is not None
        schemas = context.generated_file(
            f"{folder}/{operation.schemas_module}.ts",
            "nextjs/routes/schemas.gen.ts.j2",
            {"feature": operation.feature},
            elements,
        )
        files.append(_with_symbols(schemas, elements))
        files.extend(public_api_files(context, folder, [operation.schemas_module], elements))
    files.extend(server_api_files(context, folder, [operation.server_module], elements))
    return files


def _with_symbols(file: OutputFile, elements: Sequence[str]) -> OutputFile:
    symbols = typescript_symbols(file.content, tuple(elements))
    return OutputFile(file.path, file.content, file.kind, file.part, symbols)


def _query_value(item: ParameterField) -> str:
    """Give the expression of the value of a query parameter of a custom operation."""
    function = _PARAMETER_FUNCTIONS.get(item.rules.kind)
    name = f'"{item.json_name}"'
    if item.many:
        values = f"query.getAll({name})"
        return values if function is None else f"{values}.map({function})"
    value = f"query.get({name})"
    return f"{value} ?? undefined" if function is None else f"{function}({value})"


def _input_value(kind: str, source: str, absent: bool) -> str:
    """Give the expression of the value of a column from a field of the input.

    A decimal value is a number or a text in the input, and a text in the
    `NUMERIC` column. A time stamp is a text in the input, and a `Date` in
    the column. If the field can be missing or null, the value stays as it
    is.
    """
    if kind == "Decimal":
        value = f"String({source})"
    elif kind == "DateTime":
        value = f"new Date({source})"
    else:
        return source
    return f"{source} == null ? {source} : {value}" if absent else value


# The Prettier format.


def import_lines(names: Sequence[str], source: str, type_only: bool = False) -> list[str]:
    """Give the lines of one import statement, with the Prettier line breaks.

    Prettier keeps an import of one name on one line, also if the line is too long.
    """
    keyword = "import type" if type_only else "import"
    line = f'{keyword} {{ {", ".join(names)} }} from "{source}";'
    if len(line) <= PRINT_WIDTH or len(names) == 1:
        return [line]
    return [f"{keyword} {{", *(f"{INDENT}{name}," for name in names), f'}} from "{source}";']


def signature_lines(head: str, parameters: Sequence[str], tail: str) -> list[str]:
    """Give the first lines of a function, with the Prettier line breaks."""
    line = f"{head}({', '.join(parameters)}){tail} {{"
    if len(line) <= PRINT_WIDTH or not parameters:
        return [line]
    return [f"{head}(", *(f"{INDENT}{item}," for item in parameters), f"){tail} {{"]


def array_lines(indent: str, head: str, items: Sequence[str], end: str) -> list[str]:
    """Give the lines of an array in an object, with the Prettier line breaks."""
    line = f"{indent}{head}[{', '.join(items)}]{end}"
    if len(line) <= PRINT_WIDTH or not items:
        return [line]
    return [f"{indent}{head}[", *(f"{indent}{INDENT}{item}," for item in items), f"{indent}]{end}"]


def property_lines(indent: str, name: str, value: str) -> list[str]:
    """Give the lines of one property of an object, with the Prettier line breaks.

    Prettier puts a value that is too long on the next line.
    """
    line = f"{indent}{name}: {value},"
    if len(line) <= PRINT_WIDTH or " " not in value:
        return [line]
    return [f"{indent}{name}:", f"{indent}{INDENT}{value},"]
