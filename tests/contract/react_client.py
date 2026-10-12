"""Give the operations of a generated React client in the form of `shapes.py`.

The function reads the `.gen.ts` files of the entities and features layers.
Each call of `apiRequest` is one operation:

- `method` and `path` give the method and the path. Each value in the
  template text of the path is one path parameter.
- `query` gives the query parameters: the third item of the query key.
- `body` gives the request body: the parsed input, or an object with the
  fields of the parsed input.
- The Zod schema that parses `body` after the call gives the response.

The Zod schemas give the shapes. A Zod schema in a request has the field
rules of the Pydantic model. A decimal value with a precision also has
rules for its digits. The OpenAPI document does not have these rules, thus
the comparison does not examine them. The Vitest test of the field rules
examines them (`tests/react/field-rules/`).
"""

import dataclasses
import re
from pathlib import Path
from typing import Final

from contract.shapes import ContractError, Operation, Parameter, Shape
from contract.typescript import (
    Array,
    Call,
    Index,
    Member,
    Name,
    Node,
    Number,
    Object,
    Template,
    Text,
    read_expression,
)

LAYERS: Final = ("src/entities", "src/features")
"""The folders of the generated client."""

_CONSTANT: Final = re.compile(r"^(?:export )?const (\w+) = ", re.MULTILINE)
_FUNCTION: Final = re.compile(r"^(?:export )?(?:async )?function (\w+)\(([^)]*)\)", re.MULTILINE)
_INTERFACE: Final = re.compile(r"^(?:export )?interface (\w+) \{(.*?)^\}", re.MULTILINE | re.DOTALL)
_MEMBER: Final = re.compile(r"^\s*(\w+)(\?)?: ([^;]+);", re.MULTILINE)
_PARAMETER: Final = re.compile(r"(\w+)(\?)?: (\w+)")

_LENGTH: Final = {"min": "minLength", "max": "maxLength"}
_SIZE: Final = {
    "min": "minimum",
    "max": "maximum",
    "gt": "exclusiveMinimum",
    "lt": "exclusiveMaximum",
}
_ITEMS: Final = {"min": "minItems", "max": "maxItems"}
_RULES: Final = {"string": _LENGTH, "integer": _SIZE, "number": _SIZE, "array": _ITEMS}
"""The Zod method of each field rule, for each type."""


def read_client(project: Path) -> dict[str, str]:
    """Give the text of each generated TypeScript file of the client, by its path."""
    files: dict[str, str] = {}
    for layer in LAYERS:
        for path in sorted((project / layer).rglob("*.gen.ts")):
            files[path.relative_to(project).as_posix()] = path.read_text(encoding="utf-8")
    return files


# trace: PRD-APP-005
def client_operations(files: dict[str, str]) -> list[Operation]:
    """Give each operation that the client sends."""
    client = _Client(files)
    operations: list[Operation] = []
    for path, text in sorted(files.items()):
        for function in _functions(text):
            for match in re.finditer(r"apiRequest\((?=\{)", function.text):
                operations.append(client.operation(path, function, match.end()))
    return operations


class _Function:
    """One top-level function of a file: its name, its parameters and its text."""

    def __init__(self, name: str, parameters: str, text: str) -> None:
        self.name = name
        self.parameters = {
            match.group(1): (match.group(3), match.group(2) is None)
            for match in _PARAMETER.finditer(parameters)
        }
        self.text = text


def _functions(text: str) -> list[_Function]:
    matches = list(_FUNCTION.finditer(text))
    ends = [match.start() for match in matches[1:]] + [len(text)] if matches else []
    return [
        _Function(match.group(1), match.group(2), text[match.start() : end])
        for match, end in zip(matches, ends, strict=True)
    ]


class _Client:
    """The declarations of all the files of the client."""

    def __init__(self, files: dict[str, str]) -> None:
        self.constants: dict[str, Node] = {}
        self.functions: dict[str, _Function] = {}
        self.interfaces: dict[str, str] = {}
        for text in files.values():
            for match in _CONSTANT.finditer(text):
                if match.group(1).endswith("Schema"):
                    self._add(self.constants, match.group(1), read_expression(text, match.end())[0])
            for function in _functions(text):
                self._add(self.functions, function.name, function)
            for match in _INTERFACE.finditer(text):
                self._add(self.interfaces, match.group(1), match.group(2))

    @staticmethod
    def _add[T](found: dict[str, T], name: str, value: T) -> None:
        if name in found and name not in ("decimal", "decimalValue"):
            raise ContractError(f"The client has two declarations of {name!r}.")
        found[name] = value

    # trace: PRD-APP-005
    def operation(self, path: str, function: _Function, start: int) -> Operation:
        """Give the operation of the call of `apiRequest` at `start` of the function."""
        request, end = read_expression(function.text, start)
        if not isinstance(request, Object):
            raise ContractError(f"{path}: the argument of apiRequest is not an object.")
        data = re.search(r"const data = (\w+)\.parse\(input\);", function.text)
        inputs = self.schema(Name(data.group(1))) if data else None
        used: set[str] = set()
        method = request.get("method")
        if not isinstance(method, Text):
            raise ContractError(f"{path}: the method is not a text.")
        template = request.get("path")
        if isinstance(template, Text):
            template = Template((template.value,), ())
        if not isinstance(template, Template):
            raise ContractError(f"{path}: the path is not a text.")
        parameters = tuple(
            self._path_parameter(value, function, inputs, used) for value in template.values
        )
        body = request.get("body")
        response = None
        if re.search(r"const body = await apiRequest\($", function.text[:start], re.MULTILINE):
            response = self._response(function.text, end)
        operation = Operation(
            method=method.value,
            path="{}".join(template.texts),
            source=f"{path} ({function.name})",
            path_parameters=parameters,
            query_parameters=self._query(request.get("query"), function),
            body=None if body is None else self._body(body, inputs, used),
            response=response,
        )
        if inputs is not None:
            unsent = sorted(set(inputs["properties"]) - used)
            operation = dataclasses.replace(operation, unsent=tuple(unsent))
        return operation

    def _path_parameter(
        self, node: Node, function: _Function, inputs: Shape | None, used: set[str]
    ) -> Parameter:
        """Give one path parameter: `encodeURIComponent(<value>)`."""
        if isinstance(node, Call) and node.function == Name("encodeURIComponent"):
            value = node.arguments[0]
            if isinstance(value, Call) and value.function == Name("String"):
                value = value.arguments[0]
            if isinstance(value, Name) and value.value in function.parameters:
                kind, required = function.parameters[value.value]
                return {"required": required, "schema": {"typescript": kind}}
            if isinstance(value, Member) and value.target == Name("data") and inputs is not None:
                used.add(value.name)
                return _input_field(inputs, value.name)
        raise ContractError(f"The contract test does not know the path value {node!r}.")

    def _query(self, node: Node | None, function: _Function) -> tuple[tuple[str, Parameter], ...]:
        """Give the query parameters: `query: queryKey[2]`, the parameters of the query key."""
        if node is None:
            return ()
        key = re.search(r"const queryKey = (\w+)\(parameters\);", function.text)
        if node != Index(Name("queryKey"), Number(2)) or key is None:
            raise ContractError(f"The contract test does not know the query {node!r}.")
        key_function = self.functions[key.group(1)]
        kind, _ = key_function.parameters["parameters"]
        members = {
            match.group(1): (match.group(3), match.group(2) is None)
            for match in _MEMBER.finditer(self.interfaces[kind])
        }
        defaults = {
            match.group(1): read_expression(match.group(3))[0]
            for match in re.finditer(
                r"const (\w+) = parameters\.(\w+) \?\? ([^;]+);", key_function.text
            )
            if match.group(1) == match.group(2)
        }
        returned = re.search(r"return (\[.*\]) as const;", key_function.text, re.DOTALL)
        if returned is None:
            raise ContractError(f"The contract test cannot read the query key {key.group(1)}.")
        items = read_expression(returned.group(1))[0]
        if not isinstance(items, Array) or not isinstance(items.items[2], Object):
            raise ContractError(f"The contract test cannot read the query key {key.group(1)}.")
        query: list[tuple[str, Parameter]] = []
        for name, value in items.items[2].items:
            if value != Name(name) or name not in members:
                raise ContractError(f"The contract test does not know the query value {name!r}.")
            kind, required = members[name]
            parameter: Parameter = {"required": required, "schema": {"typescript": kind}}
            if name in defaults:
                parameter["default"] = _literal(defaults[name])
            query.append((name, parameter))
        return tuple(sorted(query))

    def _body(self, node: Node, inputs: Shape | None, used: set[str]) -> Shape:
        """Give the request body: `<schema>.parse(input)` or an object of input fields."""
        if (
            isinstance(node, Call)
            and isinstance(node.function, Member)
            and node.function.name == "parse"
            and node.arguments == (Name("input"),)
        ):
            return self.schema(node.function.target)
        if isinstance(node, Object) and inputs is not None:
            properties: dict[str, Shape] = {}
            required: list[str] = []
            for name, value in node.items:
                if not (isinstance(value, Member) and value.target == Name("data")):
                    raise ContractError(
                        f"The contract test does not know the body value {value!r}."
                    )
                used.add(value.name)
                properties[name] = inputs["properties"][value.name]
                if value.name in inputs["required"]:
                    required.append(name)
            return {
                "type": "object",
                "properties": properties,
                "required": sorted(required),
                "strict": inputs["strict"],
            }
        raise ContractError(f"The contract test does not know the body {node!r}.")

    def _response(self, text: str, start: int) -> Shape:
        """Give the response: the Zod schema in `return <schema>.parse(body);` after the call."""
        found = re.compile(r"return (.+?)\.parse\(body\);", re.DOTALL).search(text, start)
        if found is None:
            raise ContractError("The contract test cannot find the parse of the response.")
        return self.schema(read_expression(found.group(1))[0])

    # trace: PRD-APP-005, PRD-APP-211
    def schema(self, node: Node) -> Shape:
        """Give the shape of a Zod schema."""
        if isinstance(node, Name) and node.value in self.constants:
            return self.schema(self.constants[node.value])
        if not isinstance(node, Call):
            raise ContractError(f"The contract test does not know the Zod schema {node!r}.")
        function = node.function
        if function == Name("decimal"):
            rules = node.arguments[0]
            assert isinstance(rules, Object)
            shape: Shape = {"type": "decimal"}
            for key, rule in (("min", "minimum"), ("max", "maximum")):
                value = rules.get(key)
                if value is not None:
                    shape[rule] = _literal(value)
            return shape
        if function == Name("decimalValue"):
            return {"type": "decimal"}
        if isinstance(function, Member) and function.target == Name("z"):
            return self._zod(function.name, node.arguments)
        if isinstance(function, Member) and function.target == Member(Name("z"), "iso"):
            formats = {"date": "date", "datetime": "date-time"}
            return {"type": "string", "format": formats[function.name]}
        if isinstance(function, Member):
            return self._method(self.schema(function.target), function.name, node.arguments)
        raise ContractError(f"The contract test does not know the Zod schema {node!r}.")

    def _zod(self, name: str, arguments: tuple[Node, ...]) -> Shape:
        """Give the shape of a function of `z`."""
        simple = {
            "boolean": {"type": "boolean"},
            "guid": {"type": "string", "format": "uuid"},
            "int": {"type": "integer"},
            "number": {"type": "number"},
            "string": {"type": "string"},
            "url": {"type": "string", "format": "uri"},
        }
        if name in simple and not arguments:
            return dict(simple[name])
        if name == "enum" and isinstance(arguments[0], Array):
            values = sorted(str(_literal(item)) for item in arguments[0].items)
            return {"type": "string", "enum": values}
        if name == "array":
            return {"type": "array", "items": self.schema(arguments[0])}
        if name == "union" and isinstance(arguments[0], Array):
            kinds = sorted(self.schema(item)["type"] for item in arguments[0].items)
            if kinds == ["number", "string"]:
                return {"type": "decimal"}
        if name in ("object", "strictObject") and isinstance(arguments[0], Object):
            properties: dict[str, Shape] = {}
            required: list[str] = []
            for key, value in arguments[0].items:
                field = self.schema(value)
                if not field.pop("optional", False):
                    required.append(key)
                properties[key] = field
            return {
                "type": "object",
                "properties": properties,
                "required": sorted(required),
                "strict": name == "strictObject",
            }
        raise ContractError(f"The contract test does not know the Zod function z.{name}.")

    def _method(self, shape: Shape, name: str, arguments: tuple[Node, ...]) -> Shape:
        """Give the shape of a Zod schema with one more method."""
        shape = dict(shape)
        if name in ("nullable", "optional") and not arguments:
            shape[name] = True
            return shape
        rules = _RULES.get(shape["type"], {})
        if name in rules and len(arguments) == 1:
            shape[rules[name]] = _literal(arguments[0])
            return shape
        if name == "regex" and shape["type"] == "string" and len(arguments) == 1:
            pattern = arguments[0]
            if (
                isinstance(pattern, Call)
                and pattern.new
                and pattern.function == Name("RegExp")
                and isinstance(pattern.arguments[0], Text)
            ):
                shape["pattern"] = pattern.arguments[0].value
                return shape
        raise ContractError(f"The contract test does not know the Zod method .{name}().")


def _input_field(inputs: Shape, name: str) -> Parameter:
    if name not in inputs["properties"]:
        raise ContractError(f"The input has no field {name!r}.")
    return {"required": name in inputs["required"], "schema": inputs["properties"][name]}


def _literal(node: Node) -> object:
    if isinstance(node, Number | Text):
        return node.value
    if node in (Name("true"), Name("false")):
        return node == Name("true")
    raise ContractError(f"The contract test does not know the value {node!r}.")
