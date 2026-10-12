# trace: PRD-CORE-055, PRD-DSML-058, PRD-CORE-024, PRD-TOP-005
"""Convert the OpenAPI file of each external API into IR elements.

An external API is a part usage with the keyword `#ExternalApi`. Its
attribute `openApiFile` gives the path of an OpenAPI 3.1 JSON file, relative
to the repository root (PRD-DSML-058). The adapter reads the local file. It
does not use the network (PRD-TOP-005).

The adapter reads a subset of OpenAPI 3.1 (decision Q65, PRD-CORE-055):

- Each operation with an `operationId`, path and query parameters with a
  scalar schema, a JSON request body and a JSON success response.
- Each object schema that a request body or a success response refers to,
  with scalar and enumeration properties. A property can also refer to an
  object schema, or be an array of such references or of scalars.

The error responses (not 2xx) and the schemas that no operation refers to are
not in the IR. Each other item gives one STR-017 finding. If a file gives a
finding, the IR holds no element of that file.

The IR gives each schema as an `Entity` with its `Field` and `Relation`
elements, and each operation as an `Operation` with its `Parameter`
elements. The owner of each schema and operation is the external API.
`docs/notes/openapi-import.md` gives the full rules.
"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from dsml.ir.model import (
    Attribute,
    Direction,
    Element,
    ElementKind,
    EnumValue,
    Finding,
    ListValue,
    Location,
    Multiplicity,
    StringValue,
    check_relative_path,
)
from dsml.validate.rules.str_application import STR_017

OPEN_API_FILE: Final = "openApiFile"
"""The DSML attribute of an external API that gives its OpenAPI file."""

PARAMETER_IN: Final = "in"
"""The IR attribute of a parameter that gives its place: `path`, `query`, `body` or `response`."""

LITERALS: Final = "literals"
"""The IR attribute of an enumeration field that gives its literals, as strings."""

BODY: Final = "body"
"""The name of the parameter of the request body."""

RESPONSE: Final = "response"
"""The name of the parameter of the success response."""

_SCHEMA_REF: Final = re.compile(r"#/components/schemas/(?P<name>[^/~]+)")
_SUCCESS: Final = re.compile(r"2[0-9][0-9]")
_JSON: Final = "application/json"

# trace: PRD-DSML-029
_METHODS: Final = ("get", "post", "put", "patch", "delete")
"""The HTTP methods of `DSML::HttpMethod`."""

# trace: PRD-DSML-023
_FORMATS: Final[Mapping[str, str]] = {
    "uuid": "DSML::Uuid",
    "date": "DSML::Date",
    "date-time": "DSML::DateTime",
}

# trace: PRD-DSML-023
_TYPES: Final[Mapping[str, str]] = {
    "string": "ScalarValues::String",
    "integer": "ScalarValues::Integer",
    "number": "ScalarValues::Real",
    "boolean": "ScalarValues::Boolean",
}

_DECIMAL: Final = "DSML::Decimal"

# The keys that give only text or checks of a value. The adapter does not
# read them, and they give no finding.
_TEXT_KEYS: Final = frozenset({"title", "description", "summary", "externalDocs", "deprecated"})
_CHECK_KEYS: Final = frozenset(
    {
        "default",
        "example",
        "examples",
        "pattern",
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "readOnly",
        "writeOnly",
    }
)
_ARRAY_KEYS: Final = frozenset({"type", "items", "minItems", "maxItems", "uniqueItems"})
_ROOT_KEYS: Final = frozenset(
    {"openapi", "info", "paths", "components", "servers", "tags", "security"}
)
_OPERATION_KEYS: Final = frozenset(
    {"operationId", "parameters", "requestBody", "responses", "tags", "security"}
)
_PARAMETER_KEYS: Final = frozenset({"name", "in", "required", "schema"})
_OBJECT_KEYS: Final = frozenset({"type", "properties", "required", "additionalProperties"})


class _Unreadable(Exception):
    """An item of the file that is not in the subset. `pointer` is a JSON pointer."""

    def __init__(self, pointer: str, reason: str) -> None:
        super().__init__(reason)
        self.pointer = pointer
        self.reason = reason


@dataclass(frozen=True, slots=True)
class _Type:
    """The type of a property or a parameter.

    `target` is the identity of a scalar type or the name of a schema.
    `schema` is true for a schema. `literals` gives the literals of an
    enumeration.
    """

    target: str
    schema: bool = False
    many: bool = False
    nullable: bool = False
    literals: tuple[str, ...] = ()


# trace: PRD-CORE-055, PRD-VAL-016
def import_apis(elements: Sequence[Element], root: Path) -> tuple[list[Element], list[Finding]]:
    """Give the IR elements of the OpenAPI file of each external API, and the STR-017 findings.

    `root` is the repository root. The path in `openApiFile` is relative to it.
    """
    result: list[Element] = []
    findings: list[Finding] = []
    apis = sorted((item for item in elements if item.kind == "ExternalApi"), key=Element.sort_key)
    for api in apis:
        attribute = next((item for item in api.attributes if item.name == OPEN_API_FILE), None)
        location = api.location if attribute is None else attribute.location or api.location
        try:
            document = _read(api, attribute, root)
            result.extend(_Converter(api, document).elements())
        except _Unreadable as error:
            findings.append(_finding(api, location, error))
        except _FileProblem as error:
            findings.append(
                Finding(
                    rule=STR_017.id,
                    severity=STR_017.severity,
                    message=str(error),
                    location=location,
                    element=api.identity,
                )
            )
    return result, findings


class _FileProblem(Exception):
    """The file does not exist, or it is not a JSON file."""


def _read(api: Element, attribute: Attribute | None, root: Path) -> Any:
    if (
        attribute is None
        or not isinstance(attribute.value, StringValue)
        or not attribute.value.value
    ):
        raise _FileProblem(f'The external API "{api.identity}" has no value for "{OPEN_API_FILE}".')
    name = attribute.value.value
    try:
        check_relative_path(name)
    except ValueError:
        raise _FileProblem(
            f'The OpenAPI file "{name}" of the external API "{api.identity}" must be a path '
            'relative to the repository root, with "/" and no ".." segment.'
        ) from None
    path = root / name
    if not path.is_file():
        raise _FileProblem(
            f'The OpenAPI file "{name}" of the external API "{api.identity}" does not exist.'
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError, UnicodeDecodeError, ValueError:
        raise _FileProblem(
            f'The OpenAPI file "{name}" of the external API "{api.identity}" is not a JSON '
            "file with UTF-8 encoding."
        ) from None


def _finding(api: Element, location: Location, error: _Unreadable) -> Finding:
    name = next(
        (
            item.value.value
            for item in api.attributes
            if item.name == OPEN_API_FILE and isinstance(item.value, StringValue)
        ),
        "",
    )
    return Finding(
        rule=STR_017.id,
        severity=STR_017.severity,
        message=(
            f'The OpenAPI file "{name}" of the external API "{api.identity}" contains an item '
            f'that the toolchain cannot read at "{error.pointer or "/"}": {error.reason}'
        ),
        location=location,
        element=api.identity,
    )


def _pointer(*parts: str) -> str:
    """Give a JSON pointer (RFC 6901) for the parts."""
    return "".join("/" + part.replace("~", "~0").replace("/", "~1") for part in parts)


def _object(value: Any, pointer: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _Unreadable(pointer, "The item must be a JSON object.")
    return cast(dict[str, Any], value)


def _keys(value: dict[str, Any], allowed: frozenset[str], pointer: str) -> None:
    """Make sure that the object has only keys that the toolchain can read or ignore."""
    for key in sorted(value):
        if key not in allowed and key not in _TEXT_KEYS:
            raise _Unreadable(f"{pointer}{_pointer(key)}", f'The key "{key}" is not in the subset.')


# trace: PRD-CORE-055
class _Converter:
    """Convert one OpenAPI document of one external API into IR elements."""

    def __init__(self, api: Element, document: Any) -> None:
        self._api = api
        self._document = _object(document, "")
        self._schemas: dict[str, Element] = {}
        self._result: list[Element] = []

    def elements(self) -> list[Element]:
        document = self._document
        _keys(document, _ROOT_KEYS, "")
        version = document.get("openapi")
        if not isinstance(version, str) or not version.startswith("3.1."):
            raise _Unreadable("/openapi", "The OpenAPI version must be 3.1.")
        components = _object(document.get("components", {}), "/components")
        for key in sorted(components):
            if key not in ("schemas", "securitySchemes"):
                raise _Unreadable(
                    _pointer("components", key), f'The key "{key}" is not in the subset.'
                )
        paths = _object(document.get("paths", {}), "/paths")
        names: set[str] = set()
        for path in sorted(paths):
            item = _object(paths[path], _pointer("paths", path))
            _keys(item, frozenset(_METHODS), _pointer("paths", path))
            for method in _METHODS:
                if method in item:
                    self._operation(path, method, item[method], names)
        return self._result

    # Operations ---------------------------------------------------------------

    def _operation(self, path: str, method: str, value: Any, names: set[str]) -> None:
        pointer = _pointer("paths", path, method)
        operation = _object(value, pointer)
        _keys(operation, _OPERATION_KEYS, pointer)
        name = operation.get("operationId")
        if not isinstance(name, str) or not name:
            raise _Unreadable(pointer, "The operation has no operationId.")
        if name in names:
            raise _Unreadable(f"{pointer}/operationId", f'The operationId "{name}" is not unique.')
        names.add(name)
        identity = f"{self._api.identity}::{name}"
        parameters: list[tuple[str, Direction, str, _Type]] = []
        for index, item in enumerate(
            _list(operation.get("parameters", []), f"{pointer}/parameters")
        ):
            parameters.append(self._parameter(item, f"{pointer}/parameters/{index}"))
        if "requestBody" in operation:
            body = self._body(operation["requestBody"], f"{pointer}/requestBody")
            parameters.append((BODY, "in", BODY, body))
        response = self._response(operation.get("responses"), f"{pointer}/responses")
        if response is not None:
            parameters.append((RESPONSE, "out", RESPONSE, response))
        seen: set[str] = set()
        for parameter, _, _, _ in parameters:
            if parameter in seen:
                raise _Unreadable(pointer, f'The operation has two parameters "{parameter}".')
            seen.add(parameter)
        self._result.append(
            self._element(
                identity,
                "Operation",
                name,
                self._api.identity,
                attributes=(
                    Attribute("method", EnumValue("DSML::HttpMethod", method)),
                    Attribute("path", StringValue(path)),
                ),
            )
        )
        for parameter, direction, place, kind in parameters:
            self._result.append(
                self._typed(
                    f"{identity}::{parameter}",
                    "Parameter",
                    parameter,
                    identity,
                    kind,
                    direction=direction,
                    required=True,
                    extra=(Attribute(PARAMETER_IN, StringValue(place)),),
                )
            )

    def _parameter(self, value: Any, pointer: str) -> tuple[str, Direction, str, _Type]:
        parameter = _object(value, pointer)
        _keys(parameter, _PARAMETER_KEYS, pointer)
        place = parameter.get("in")
        if place not in ("path", "query"):
            raise _Unreadable(f"{pointer}/in", "A parameter must be in the path or in the query.")
        name = parameter.get("name")
        if not isinstance(name, str) or not name:
            raise _Unreadable(f"{pointer}/name", "The parameter has no name.")
        kind = self._type(parameter.get("schema"), f"{pointer}/schema")
        if kind.schema:
            raise _Unreadable(f"{pointer}/schema", "A parameter must have a scalar type.")
        if place == "query" and not parameter.get("required", False):
            kind = _Type(kind.target, kind.schema, kind.many, True, kind.literals)
        return (name, "in", place, kind)

    def _body(self, value: Any, pointer: str) -> _Type:
        body = _object(value, pointer)
        _keys(body, frozenset({"content", "required"}), pointer)
        kind = self._content(body.get("content"), f"{pointer}/content")
        if kind is None:
            raise _Unreadable(pointer, "The request body has no JSON content.")
        if not body.get("required", False):
            kind = _Type(kind.target, kind.schema, kind.many, True, kind.literals)
        return kind

    def _response(self, value: Any, pointer: str) -> _Type | None:
        """Give the type of the first success response, or None if it has no content."""
        responses = _object(value, pointer)
        codes = sorted(code for code in responses if _SUCCESS.fullmatch(code))
        if not codes:
            raise _Unreadable(pointer, "The operation has no success response (2xx).")
        where = f"{pointer}/{codes[0]}"
        response = _object(responses[codes[0]], where)
        _keys(response, frozenset({"content"}), where)
        if "content" not in response:
            return None
        kind = self._content(response["content"], f"{where}/content")
        if kind is None:
            raise _Unreadable(f"{where}/content", "The success response has no JSON content.")
        return kind

    def _content(self, value: Any, pointer: str) -> _Type | None:
        content = _object(value, pointer)
        for media in sorted(content):
            if media != _JSON:
                raise _Unreadable(
                    f"{pointer}{_pointer(media)}", f'The media type "{media}" is not in the subset.'
                )
        if _JSON not in content:
            return None
        where = f"{pointer}{_pointer(_JSON)}"
        media = _object(content[_JSON], where)
        _keys(media, frozenset({"schema"}), where)
        kind = self._type(media.get("schema"), f"{where}/schema")
        if not kind.schema:
            raise _Unreadable(f"{where}/schema", "The JSON content must refer to an object schema.")
        return kind

    # Schemas ------------------------------------------------------------------

    def _schema(self, name: str, pointer: str) -> str:
        """Convert the schema with the name, once, and give its identity."""
        identity = f"{self._api.identity}::{name}"
        if name in self._schemas:
            return identity
        components = _object(self._document.get("components", {}), "/components")
        schemas = _object(components.get("schemas", {}), "/components/schemas")
        if name not in schemas:
            raise _Unreadable(pointer, f'The schema "{name}" does not exist.')
        where = _pointer("components", "schemas", name)
        schema = _object(schemas[name], where)
        _keys(schema, _OBJECT_KEYS, where)
        if schema.get("type") != "object":
            raise _Unreadable(f"{where}/type", "A schema must have the type object.")
        if not isinstance(schema.get("additionalProperties", False), bool):
            raise _Unreadable(f"{where}/additionalProperties", "The value must be true or false.")
        entity = self._element(identity, "Entity", name, self._api.identity, doc=_doc(schema))
        self._schemas[name] = entity
        self._result.append(entity)
        required = _list(schema.get("required", []), f"{where}/required")
        properties = _object(schema.get("properties", {}), f"{where}/properties")
        for key in sorted(properties):
            kind = self._type(properties[key], f"{where}/properties{_pointer(key)}")
            self._result.append(
                self._typed(
                    f"{identity}::{key}",
                    "Relation" if kind.schema else "Field",
                    key,
                    identity,
                    kind,
                    required=key in required,
                    doc=_doc(properties[key]),
                )
            )
        return identity

    def _type(self, value: Any, pointer: str) -> _Type:
        """Give the type of a property, a parameter or a JSON content."""
        schema = _object(value, pointer)
        if "$ref" in schema:
            _keys(schema, frozenset({"$ref"}), pointer)
            found = _SCHEMA_REF.fullmatch(str(schema["$ref"]))
            if found is None:
                raise _Unreadable(f"{pointer}/$ref", "A reference must refer to a schema.")
            return _Type(self._schema(found["name"], f"{pointer}/$ref"), schema=True)
        if "anyOf" in schema:
            return self._any_of(schema, pointer)
        kind = schema.get("type")
        if isinstance(kind, list) and len(cast(list[Any], kind)) == 2 and "null" in kind:
            others = [item for item in cast(list[Any], kind) if item != "null"]
            single = self._scalar({**schema, "type": others[0]}, pointer)
            return _Type(single.target, nullable=True, literals=single.literals)
        if kind == "array":
            _keys(schema, _ARRAY_KEYS, pointer)
            item = self._type(schema.get("items"), f"{pointer}/items")
            if item.many or item.nullable:
                raise _Unreadable(
                    f"{pointer}/items", "The items of an array are not in the subset."
                )
            return _Type(item.target, item.schema, many=True, literals=item.literals)
        return self._scalar(schema, pointer)

    def _any_of(self, schema: dict[str, Any], pointer: str) -> _Type:
        _keys(schema, _CHECK_KEYS | {"anyOf"}, pointer)
        options = _list(schema["anyOf"], f"{pointer}/anyOf")
        nullable = any(_is_null(item) for item in options)
        found = [
            self._type(item, f"{pointer}/anyOf/{index}")
            for index, item in enumerate(options)
            if not _is_null(item)
        ]
        targets = {item.target for item in found}
        if len(found) == 1:
            single = found[0]
            return _Type(single.target, single.schema, single.many, nullable, single.literals)
        # FastAPI gives a decimal input as a number or a string.
        if targets == {_TYPES["number"], _TYPES["string"]} and not any(i.literals for i in found):
            return _Type(_DECIMAL, nullable=nullable)
        raise _Unreadable(f"{pointer}/anyOf", "The alternatives of anyOf are not in the subset.")

    def _scalar(self, schema: dict[str, Any], pointer: str) -> _Type:
        _keys(schema, _CHECK_KEYS | {"type", "format", "enum"}, pointer)
        kind = schema.get("type")
        if not isinstance(kind, str) or kind not in _TYPES:
            raise _Unreadable(pointer, "The type is not a scalar type of the subset.")
        target = _TYPES[kind]
        form = schema.get("format")
        if kind == "string" and isinstance(form, str):
            target = _FORMATS.get(form, target)
        literals: tuple[str, ...] = ()
        if "enum" in schema:
            values = _list(schema["enum"], f"{pointer}/enum")
            if kind != "string" or not values or not all(isinstance(v, str) for v in values):
                raise _Unreadable(f"{pointer}/enum", "An enumeration must have string literals.")
            literals = tuple(values)
        return _Type(target, literals=literals)

    # Elements -----------------------------------------------------------------

    def _element(
        self,
        identity: str,
        kind: ElementKind,
        name: str,
        owner: str,
        *,
        doc: str | None = None,
        types: tuple[str, ...] = (),
        multiplicity: Multiplicity | None = None,
        direction: Direction | None = None,
        attributes: tuple[Attribute, ...] = (),
    ) -> Element:
        api = self._api
        return Element(
            identity=identity,
            kind=kind,
            name=name,
            qualified_name=f"{api.qualified_name}::{identity.removeprefix(api.identity + '::')}",
            location=api.location,
            owner=owner,
            doc=doc,
            multiplicity=multiplicity,
            direction=direction,
            types=types,
            attributes=attributes,
        )

    def _typed(
        self,
        identity: str,
        kind: ElementKind,
        name: str,
        owner: str,
        of: _Type,
        *,
        required: bool,
        direction: Direction | None = None,
        doc: str | None = None,
        extra: tuple[Attribute, ...] = (),
    ) -> Element:
        if of.many:
            multiplicity = Multiplicity(0, None)
        elif required and not of.nullable:
            multiplicity = Multiplicity(1, 1)
        else:
            multiplicity = Multiplicity(0, 1)
        attributes = extra
        if of.literals:
            values = ListValue(tuple(StringValue(item) for item in of.literals))
            attributes = (*attributes, Attribute(LITERALS, values))
        return self._element(
            identity,
            kind,
            name,
            owner,
            doc=doc,
            types=(of.target,),
            multiplicity=multiplicity,
            direction=direction,
            attributes=attributes,
        )


def _list(value: Any, pointer: str) -> list[Any]:
    if not isinstance(value, list):
        raise _Unreadable(pointer, "The item must be a JSON array.")
    return cast(list[Any], value)


def _is_null(value: Any) -> bool:
    """Tell if a schema is the schema `{"type": "null"}`."""
    return isinstance(value, dict) and cast(dict[str, Any], value).get("type") == "null"


def _doc(value: Any) -> str | None:
    text = cast(dict[str, Any], value).get("description") if isinstance(value, dict) else None
    return text if isinstance(text, str) and text else None
