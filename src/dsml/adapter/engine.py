# trace: PRD-CORE-017, PRD-CORE-018, PRD-CORE-019, PRD-CORE-020
"""Start OpenSysML, parse SysML v2 files and read the results.

The other modules of the toolchain do not see an OpenSysML object. This module
gives the results as plain data classes.
"""

import json
import warnings
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import TracebackType
from typing import Any, Literal, Self, cast

import opensysml
import opensysml.connection

from dsml import versions
from dsml.errors import ToolchainError

ConstraintValue = Literal["true", "false", "unknown"]

# The status names that OpenSysML gives in a verdict.
_STATUS_VALUES: dict[str, ConstraintValue] = {
    "holds": "true",
    "violated": "false",
    "undecided": "unknown",
}

# The gRPC client of OpenSysML refuses a message larger than 4 MiB. The API
# JSON form of the PRD model is approximately 12 MB. -1 removes the limit.
_CHANNEL_OPTION_MAX_RECEIVE = ("grpc.max_receive_message_length", -1)


# trace: PRD-CORE-024, PRD-CORE-025
@dataclass(frozen=True, slots=True)
class EnumLiteral:
    """A literal of an enumeration that an expression gives.

    `enumeration` is the qualified name of the enumeration definition, and
    `literal` is the name of the literal, for example "must".
    """

    enumeration: str
    literal: str


type PlainValue = str | int | float | bool | EnumLiteral | tuple[PlainValue, ...]
"""A value of an expression, with no OpenSysML object in it.

A tuple is a list of values in the order of the model.
"""


# trace: PRD-CORE-019
class EngineVersionError(ToolchainError):
    """The version of OpenSysML is not the pinned version.

    The command stops with exit code 2 (PRD-CORE-019).
    """


class EngineError(ToolchainError):
    """OpenSysML cannot do the operation. The command stops with exit code 2."""


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One diagnostic of OpenSysML, with its location in a source file.

    `file` is the name that the caller gave to the source file. Lines and
    columns start at 1.
    """

    file: str
    line: int
    column: int
    end_line: int
    end_column: int
    severity: str
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.column}: {self.severity}: {self.message}"


@dataclass(frozen=True, slots=True)
class ConstraintResult:
    """The result of a constraint: "true", "false" or "unknown".

    For "unknown", `detail` gives the message of OpenSysML. The message names
    the feature that has no value.
    """

    value: ConstraintValue
    detail: str = ""


# trace: PRD-CORE-018, PRD-CORE-019
def check_client_version(client_version: str, pinned: str) -> None:
    """Make sure that the `opensysml` Python package has the pinned version.

    The client downloads only the `sysml-grpc` release of its own version. Thus
    the toolchain checks the client before it starts `sysml-grpc`.
    """
    if client_version != pinned:
        raise EngineVersionError(
            f"The opensysml Python package has version {client_version}. "
            f"The toolchain must use version {pinned}."
        )


# trace: PRD-CORE-018, PRD-CORE-019
def check_service_version(service_version: str, pinned: str) -> None:
    """Make sure that `sysml-grpc` has the pinned version.

    `sysml-grpc` gives a release tag, for example "v0.9.2".
    """
    if service_version != f"v{pinned}":
        raise EngineVersionError(
            f"sysml-grpc has version {service_version or 'unknown'}. "
            f"The toolchain must use version v{pinned}."
        )


@dataclass(frozen=True, slots=True)
class ModelElement:
    """One element of a parsed model, with its names and its kind.

    `kind` is the name of the SysML v2 metaclass, for example
    "MetadataDefinition". `general` gives the qualified names of the general
    types of a definition, sorted. It is empty if the element has none.
    `short_name` is the declared short name, for example "PRD-CORE-001".
    `documentation` is the text of the `doc` comment. Each one is empty if the
    element has none.
    """

    qualified_name: str
    name: str
    kind: str
    owner: str
    general: tuple[str, ...] = ()
    short_name: str = ""
    documentation: str = ""


class ParsedModel:
    """A model that OpenSysML parsed from one or more source files.

    `sources` maps the name of each source file to its text.
    """

    def __init__(self, model: Any, sources: Mapping[str, str] | None = None) -> None:
        self._model = model
        self._sources: dict[str, str] = dict(sources or {})
        self.diagnostics: tuple[Diagnostic, ...] = tuple(
            sorted(
                (_diagnostic(item) for item in model.diagnostics),
                key=lambda d: (d.file, d.line, d.column, d.code, d.message),
            )
        )

    def source_text(self, file: str) -> str | None:
        """Give the text of a source file of the parse, or None."""
        return self._sources.get(file)

    @property
    def ok(self) -> bool:
        """True if the model has no error and no warning (PRD-DSML-004)."""
        return not self.diagnostics

    def is_type(self, element: str, type_name: str, namespace: str) -> bool:
        """True if `element` is an instance of the type `type_name`.

        Both names resolve in `namespace`.
        """
        return self.evaluate_bool(f"{element} istype {type_name}", namespace)

    def has_metadata(self, element: str, metadata: str, namespace: str) -> bool:
        """True if `element` has the metadata `metadata` (a user-defined keyword).

        Both names resolve in `namespace`.
        """
        return self.evaluate_bool(f"{element} @ {metadata}", namespace)

    def owned_elements(self, owner: str, kinds: Collection[str] = ()) -> tuple[ModelElement, ...]:
        """Give the elements that `owner` owns, sorted by qualified name.

        `owner` is a qualified name. If `kinds` is not empty, give only the
        elements of these metaclasses.
        """
        try:
            items: Any = self._model.query(scope=[owner])
        except opensysml.OpenSysMLError as error:
            raise EngineError(f"Cannot read the elements of {owner}: {error}") from None
        elements = (_model_element(item) for item in items)
        return tuple(
            sorted(
                (
                    element
                    for element in elements
                    if element.owner == owner and (not kinds or element.kind in kinds)
                ),
                key=lambda element: element.qualified_name,
            )
        )

    # trace: PRD-CORE-024
    def api_elements(self) -> tuple[dict[str, Any], ...]:
        """Give the elements of the model in the SysML v2 API JSON form.

        Only this form gives the source location of each element, the
        metadata usages and the values of the features. OpenSysML 0.9.2 marks
        the form as experimental, so this method does not show its warning.
        `dsml.adapter.source` reads the elements. Each item is a JSON object.
        """
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                conversion: Any = self._model.to_api_json()
        except opensysml.OpenSysMLError as error:
            raise EngineError(f"Cannot convert the model to the API JSON form: {error}") from None
        items: Any = json.loads(str(conversion))
        if not isinstance(items, list):
            raise EngineError("The API JSON form of the model is not a list of elements.")
        elements: list[dict[str, Any]] = []
        for item in items:  # pyright: ignore[reportUnknownVariableType]
            if not isinstance(item, dict):
                raise EngineError("An item of the API JSON form is not an object.")
            elements.append(item)  # pyright: ignore[reportUnknownArgumentType]
        return tuple(elements)

    # trace: PRD-CORE-054
    def evaluate_constraint(self, qualified_name: str) -> ConstraintResult:
        """Evaluate a constraint with the attribute values of the model.

        A constraint that refers to a feature with no value gives "unknown".
        """
        try:
            verdict: Any = self._model.verify_constraint(qualified_name)
        except opensysml.OpenSysMLError as error:
            raise EngineError(f"Cannot evaluate the constraint {qualified_name}: {error}") from None
        return _constraint_result(verdict)

    # trace: PRD-CORE-054
    def evaluate_requirement(self, qualified_name: str) -> ConstraintResult:
        """Evaluate all the `require constraint` items of a requirement."""
        try:
            verdict: Any = self._model.verify_requirement(qualified_name)
        except opensysml.OpenSysMLError as error:
            raise EngineError(
                f"Cannot evaluate the requirement {qualified_name}: {error}"
            ) from None
        return _constraint_result(verdict)

    # trace: PRD-CORE-054
    def evaluate_formula(self, expression: str, namespace: str) -> ConstraintResult:
        """Evaluate a Boolean expression in `namespace` and give its result.

        An expression that refers to a feature with no value gives "unknown".
        Then `detail` gives the reason of OpenSysML, which names one feature.
        """
        try:
            value: Any = self._model.eval(expression, context_symbol_id=namespace)
        except opensysml.OpenSysMLError as error:
            raise EngineError(f"Cannot evaluate {expression!r}: {error}") from None
        if isinstance(value, opensysml.Undetermined):
            return ConstraintResult(value="unknown", detail=str(value.reason))
        if not isinstance(value, bool):
            raise EngineError(f"The expression {expression!r} does not give a Boolean value.")
        return ConstraintResult(value="true" if value else "false")

    # trace: PRD-CORE-054
    def has_value(self, expression: str, namespace: str) -> bool | None:
        """Tell if an expression has a value in `namespace`.

        The result is False if the value is not determined, for example for a
        feature with no value. The result is None if OpenSysML cannot evaluate
        the expression, for example for a name that is not a feature.
        """
        try:
            value: Any = self._model.eval(expression, context_symbol_id=namespace)
        except opensysml.OpenSysMLError:
            return None
        return not isinstance(value, opensysml.Undetermined)

    # trace: PRD-CORE-024, PRD-CORE-025
    def evaluate_value(self, expression: str, namespace: str) -> PlainValue | None:
        """Evaluate an expression in `namespace` and give its value.

        The result is None if the expression has no value in the model. A list
        with no items also gives None.
        """
        try:
            value: Any = self._model.eval(expression, context_symbol_id=namespace)
        except opensysml.OpenSysMLError as error:
            raise EngineError(f"Cannot evaluate {expression!r}: {error}") from None
        return _plain_value(value, expression)

    def evaluate_bool(self, expression: str, namespace: str) -> bool:
        """Evaluate an expression that gives a Boolean value, in `namespace`."""
        try:
            value: Any = self._model.eval(expression, context_symbol_id=namespace)
        except opensysml.OpenSysMLError as error:
            raise EngineError(f"Cannot evaluate {expression!r}: {error}") from None
        if not isinstance(value, bool):
            raise EngineError(f"The expression {expression!r} does not give a Boolean value.")
        return value


class Engine:
    """A connection to a private `sysml-grpc` child process.

    The `opensysml` client starts the child process and stops it (PRD-CORE-017).
    Use the class in a `with` statement.
    """

    def __init__(self) -> None:
        pinned = versions.pinned_version("opensysml")
        check_client_version(opensysml.__version__, pinned)
        _allow_large_messages()
        try:
            # The client has no type annotations for the arguments of connect().
            client: Any = opensysml
            self._connection: Any = client.connect(version=f"v{pinned}")
        except opensysml.StaleServiceError as error:
            raise EngineVersionError(str(error)) from None
        except opensysml.OpenSysMLError as error:
            raise EngineError(f"Cannot start sysml-grpc: {error}") from None
        try:
            info: Any = self._connection.server_info()
            check_service_version(str(info.version), pinned)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        """Stop the connection. The last connection stops the child process."""
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def service_version(self) -> str:
        """The release tag that `sysml-grpc` gives, for example "v0.9.2"."""
        return str(self._connection.server_info().version)

    # trace: PRD-DSML-004, PRD-TOP-011
    def parse_files(self, paths: Sequence[Path], root: Path) -> ParsedModel:
        """Parse the files as one model and resolve all names.

        The diagnostics give each file name relative to `root`, with "/" as
        the separator, so the output does not contain an absolute path.
        """
        documents = [
            (
                PurePosixPath(path.resolve().relative_to(root.resolve())).as_posix(),
                path.read_text(encoding="utf-8"),
            )
            for path in paths
        ]
        return self.parse_texts(documents)

    def parse_texts(self, documents: Sequence[tuple[str, str]]) -> ParsedModel:
        """Parse source texts as one model. Each item is a (name, text) pair."""
        try:
            model: Any = self._connection.parse_sources(list(documents))
        except opensysml.OpenSysMLError as error:
            raise EngineError(f"OpenSysML cannot parse the model: {error}") from None
        return ParsedModel(model, dict(documents))


def _allow_large_messages() -> None:
    """Remove the size limit of a gRPC message that the client receives.

    The client reads the options of a new channel from the module constant
    `CHANNEL_OPTIONS`. The function adds the option one time.
    """
    module: Any = opensysml.connection
    options: tuple[tuple[str, Any], ...] = tuple(module.CHANNEL_OPTIONS)
    if _CHANNEL_OPTION_MAX_RECEIVE not in options:
        module.CHANNEL_OPTIONS = (*options, _CHANNEL_OPTION_MAX_RECEIVE)


def _diagnostic(item: Any) -> Diagnostic:
    return Diagnostic(
        file=str(item.file),
        line=int(item.start_line),
        column=int(item.start_column),
        end_line=int(item.end_line),
        end_column=int(item.end_column),
        severity=str(item.severity),
        code=str(item.code),
        message=str(item.message),
    )


def _model_element(item: Any) -> ModelElement:
    properties: dict[str, Any] = dict(item.properties)
    general: Any = properties.get("general")
    if general is None:
        generals: tuple[str, ...] = ()
    elif isinstance(general, str):
        generals = (general,)
    else:
        generals = tuple(sorted(str(name) for name in general))
    return ModelElement(
        qualified_name=str(item.id),
        name=str(properties.get("name", "")),
        kind=str(item.type),
        owner=str(properties.get("owner", "")),
        general=generals,
        short_name=str(properties.get("declaredShortName", "")),
        documentation=str(properties.get("documentation", "")),
    )


def _plain_value(value: Any, expression: str) -> PlainValue | None:
    match value:
        case opensysml.Undetermined() | None:
            return None
        case bool() | int() | float() | str():
            return value
        case opensysml.EnumLiteral():
            literal_id = str(value.literal_id)
            literal = literal_id.rsplit("::", 1)[-1]
            if len(literal) >= 2 and literal.startswith("'") and literal.endswith("'"):
                literal = literal[1:-1]
            return EnumLiteral(enumeration=str(value.enumeration_id), literal=literal)
        case list() | tuple():
            items = [_plain_value(item, expression) for item in cast(Sequence[Any], value)]
            values = tuple(item for item in items if item is not None)
            return values or None
        case _:
            raise EngineError(
                f"The expression {expression!r} gives a value that the toolchain cannot use: "
                f"{type(value).__name__}."
            )


def _constraint_result(verdict: Any) -> ConstraintResult:
    status = str(verdict.status)
    value = _STATUS_VALUES.get(status)
    if value is None:
        raise EngineError(f"OpenSysML gave the unknown verdict status {status!r}.")
    detail = str(verdict.error) if value == "unknown" else ""
    return ConstraintResult(value=value, detail=detail)
