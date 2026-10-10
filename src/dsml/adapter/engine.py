# trace: PRD-CORE-017, PRD-CORE-018, PRD-CORE-019, PRD-CORE-020
"""Start OpenSysML, parse SysML v2 files and read the results.

The other modules of the toolchain do not see an OpenSysML object. This module
gives the results as plain data classes.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import TracebackType
from typing import Any, Literal, Self

import opensysml

from dsml import versions

ConstraintValue = Literal["true", "false", "unknown"]

# The status names that OpenSysML gives in a verdict.
_STATUS_VALUES: dict[str, ConstraintValue] = {
    "holds": "true",
    "violated": "false",
    "undecided": "unknown",
}


class EngineVersionError(Exception):
    """The version of OpenSysML is not the pinned version."""


class EngineError(Exception):
    """OpenSysML cannot do the operation."""


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
    """

    qualified_name: str
    name: str
    kind: str
    owner: str
    general: tuple[str, ...] = ()


class ParsedModel:
    """A model that OpenSysML parsed from one or more source files."""

    def __init__(self, model: Any) -> None:
        self._model = model
        self.diagnostics: tuple[Diagnostic, ...] = tuple(
            sorted(
                (_diagnostic(item) for item in model.diagnostics),
                key=lambda d: (d.file, d.line, d.column, d.code, d.message),
            )
        )

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
        return ParsedModel(model)


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
    )


def _constraint_result(verdict: Any) -> ConstraintResult:
    status = str(verdict.status)
    value = _STATUS_VALUES.get(status)
    if value is None:
        raise EngineError(f"OpenSysML gave the unknown verdict status {status!r}.")
    detail = str(verdict.error) if value == "unknown" else ""
    return ConstraintResult(value=value, detail=detail)
