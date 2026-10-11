# trace: PRD-CORE-012, PRD-CORE-013, PRD-CORE-014, PRD-CORE-016, PRD-DSML-051
"""Read and check the configuration file `dsml.toml`.

The reader gives a typed `Configuration`. The other parts of the toolchain
read only this data, not the TOML text. `docs/configuration.md` gives all
keys of the schema.

The reader reports each error with the file, the line and the key: a TOML
syntax error, an unknown key, a wrong type, a wrong value or an unknown
schema version. The schema has no key for a secret value (PRD-CORE-016).
"""

import re
import tomllib
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Final, Literal, cast

from dsml.errors import ToolchainError

SCHEMA_VERSION: Final = 1
"""The schema version of the configuration file that this toolchain reads."""

DEFAULT_ID_PATTERNS: Final = {
    "need": r"N-[0-9]{3,}",
    "requirement": r"R-[0-9]{3,}",
    "verification": r"V-[0-9]{3,}",
}
"""The ID pattern of each kind of element (PRD-DSML-050)."""

OPTIONAL_RULE_SETS: Final = ("TXT",)
"""The rule categories that are off by default (PRD-VAL-013)."""

RuleSeverity = Literal["error", "warning", "info", "off"]
RULE_SEVERITIES: Final = ("error", "warning", "info", "off")
_RULE_ID = re.compile(r"[A-Z]{3}-[0-9]{3}")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")

KeyPath = tuple[str, ...]


# trace: PRD-CORE-014
class ConfigurationError(ToolchainError):
    """The configuration file is not correct.

    The message has one line for each error. Each line starts with the file
    and the line number of the error, if the reader knows the line.
    """

    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


# trace: PRD-DSML-050, PRD-DSML-051
@dataclass(frozen=True, slots=True)
class IdPatterns:
    """The regular expression of the ID of each kind of element.

    An ID agrees with a pattern if the full ID matches it (`re.fullmatch`).
    """

    need: str = DEFAULT_ID_PATTERNS["need"]
    requirement: str = DEFAULT_ID_PATTERNS["requirement"]
    verification: str = DEFAULT_ID_PATTERNS["verification"]


# trace: PRD-CORE-013, PRD-CORE-046
@dataclass(frozen=True, slots=True)
class Application:
    """The settings of one application of the model."""

    name: str
    output: PurePosixPath | None = None
    """The output folder of the application (PRD-APP-002)."""
    dependencies: tuple[str, ...] = ()
    """The extra dependencies of the application (PRD-CORE-046, Q56)."""


# trace: PRD-CORE-013, PRD-VAL-004, PRD-VAL-013
@dataclass(frozen=True, slots=True)
class Rules:
    """The settings of the validation rules."""

    optional: tuple[str, ...] = ()
    """The optional rule sets that are on, for example "TXT"."""
    severity: tuple[tuple[str, RuleSeverity], ...] = ()
    """The changed severity of each rule, sorted by rule ID."""


# trace: PRD-CORE-013, PRD-TRACE-010, PRD-TRACE-016
@dataclass(frozen=True, slots=True)
class Trace:
    """The settings of the traceability."""

    baseline: str | None = None
    """The default trace baseline, a Git reference.

    If there is no baseline, the reports use the newest release tag (Q54).
    """
    tests: tuple[PurePosixPath, ...] = ()
    """The test folders with hand-written tests (PRD-TRACE-010)."""


# trace: PRD-CORE-013, PRD-IAC-004
@dataclass(frozen=True, slots=True)
class OpenTofuOptions:
    """The IaC options that only OpenTofu accepts."""

    state_encryption: bool = False


# trace: PRD-CORE-013, PRD-CORE-016
@dataclass(frozen=True, slots=True)
class Configuration:
    """The typed contents of the configuration file.

    Each list is sorted and has no duplicate item (PRD-CORE-032). Each path
    is relative to the folder of the configuration file.
    """

    path: Path | None = None
    """The configuration file. `None` if the toolchain read no file."""
    model: tuple[PurePosixPath, ...] = ()
    """The model files and folders (PRD-DSML-007)."""
    applications: tuple[Application, ...] = ()
    """The settings of each application, sorted by name."""
    infrastructure: PurePosixPath | None = None
    """The output folder of the infrastructure (PRD-IAC-001)."""
    pipelines: PurePosixPath | None = None
    """The output folder of the pipelines."""
    ids: IdPatterns = field(default_factory=IdPatterns)
    rules: Rules = field(default_factory=Rules)
    trace: Trace = field(default_factory=Trace)
    regions: tuple[str, ...] = ()
    """The permitted AWS Regions (rule AWS-002)."""
    opentofu: OpenTofuOptions | None = None
    """The IaC options for OpenTofu only. `None` if the file has none."""

    @property
    def root(self) -> Path:
        """The folder that the paths of the configuration are relative to."""
        return Path() if self.path is None else self.path.parent

    def application(self, name: str) -> Application | None:
        """Give the settings of one application, or `None`."""
        return next((app for app in self.applications if app.name == name), None)


# trace: PRD-CORE-012
def load_configuration(path: Path) -> Configuration:
    """Read and check the configuration file at `path`."""
    try:
        text = path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        raise ConfigurationError([f"The configuration file {path} does not exist."]) from None
    except OSError as error:
        raise ConfigurationError(
            [f"Cannot read the configuration file {path}: {error.strerror}."]
        ) from None
    except UnicodeDecodeError:
        raise ConfigurationError(
            [f"The configuration file {path} does not have UTF-8 encoding."]
        ) from None
    return parse_configuration(text, path)


# trace: PRD-CORE-013, PRD-CORE-014
def parse_configuration(text: str, path: Path) -> Configuration:
    """Check the TOML text of a configuration file and give its typed data.

    `path` is the configuration file. The messages give it, and the paths of
    the configuration are relative to its folder.
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigurationError(
            [f"{path}:{error.lineno}: The file is not correct TOML: {error.msg}."]
        ) from None
    reader = _Reader(path, _key_lines(text))
    configuration = reader.read(data)
    if reader.errors:
        raise ConfigurationError([message for _, message in sorted(reader.errors)])
    return configuration


class _Reader:
    """Read the TOML data into a `Configuration` and collect the errors."""

    def __init__(self, path: Path, lines: Mapping[KeyPath, int]) -> None:
        self.path = path
        self.lines = lines
        self.errors: list[tuple[int, str]] = []
        self.values: dict[str, object] = {}

    def read(self, data: dict[str, object]) -> Configuration:
        if "schema" not in data:
            self._error((), f'The key "schema" is missing. Use schema = {SCHEMA_VERSION}.')
            return Configuration(path=self.path)
        schema = data["schema"]
        if type(schema) is not int or schema != SCHEMA_VERSION:
            self._error(
                ("schema",),
                f"The schema version {_toml(schema)} is unknown. "
                f"This toolchain reads schema version {SCHEMA_VERSION}.",
            )
            return Configuration(path=self.path)
        tables: dict[str, Callable[[KeyPath, dict[str, object]], None]] = {
            "model": self._model,
            "applications": self._applications,
            "infrastructure": self._infrastructure,
            "pipelines": self._pipelines,
            "ids": self._ids,
            "rules": self._rules,
            "trace": self._trace,
            "aws": self._aws,
            "iac": self._iac,
        }
        for key, value in data.items():
            if key == "schema":
                continue
            if key not in tables:
                self._unknown((key,))
            elif (table := self._table((key,), value)) is not None:
                tables[key]((key,), table)
        return Configuration(path=self.path, **self.values)  # pyright: ignore[reportArgumentType]

    # The tables of the schema.

    def _model(self, at: KeyPath, table: dict[str, object]) -> None:
        for key, value in self._keys(at, table, {"paths"}):
            paths = self._paths((*at, key), value)
            if paths is not None:
                self.values["model"] = paths

    def _applications(self, at: KeyPath, table: dict[str, object]) -> None:
        applications: list[Application] = []
        for name, value in table.items():
            app_at = (*at, name)
            if not _NAME.fullmatch(name):
                self._error(
                    app_at,
                    f'The application name "{name}" is not correct. '
                    'Use a letter, then letters, digits, "_" or "-".',
                )
                continue
            app = self._table(app_at, value)
            if app is None:
                continue
            output: PurePosixPath | None = None
            dependencies: tuple[str, ...] = ()
            for key, item in self._keys(app_at, app, {"output", "dependencies"}):
                if key == "output":
                    output = self._path((*app_at, key), item)
                else:
                    dependencies = self._texts((*app_at, key), item) or ()
            applications.append(Application(name, output, dependencies))
        self.values["applications"] = tuple(sorted(applications, key=lambda app: app.name))

    def _infrastructure(self, at: KeyPath, table: dict[str, object]) -> None:
        for key, value in self._keys(at, table, {"output"}):
            self.values["infrastructure"] = self._path((*at, key), value)

    def _pipelines(self, at: KeyPath, table: dict[str, object]) -> None:
        for key, value in self._keys(at, table, {"output"}):
            self.values["pipelines"] = self._path((*at, key), value)

    def _ids(self, at: KeyPath, table: dict[str, object]) -> None:
        patterns = dict(DEFAULT_ID_PATTERNS)
        for key, value in self._keys(at, table, set(DEFAULT_ID_PATTERNS)):
            pattern = self._text((*at, key), value)
            if pattern is None:
                continue
            try:
                re.compile(pattern)
            except re.error as error:
                self._error((*at, key), f"The regular expression is not correct: {error.msg}.")
                continue
            patterns[key] = pattern
        self.values["ids"] = IdPatterns(**patterns)

    def _rules(self, at: KeyPath, table: dict[str, object]) -> None:
        optional: tuple[str, ...] = ()
        severity: list[tuple[str, RuleSeverity]] = []
        for key, value in self._keys(at, table, {"optional", "severity"}):
            if key == "optional":
                sets = self._texts((*at, key), value) or ()
                unknown = [name for name in sets if name not in OPTIONAL_RULE_SETS]
                for name in unknown:
                    self._error(
                        (*at, key),
                        f'The rule set "{name}" is unknown. '
                        f"The optional rule sets are: {', '.join(OPTIONAL_RULE_SETS)}.",
                    )
                optional = tuple(name for name in sets if name not in unknown)
                continue
            levels = self._table((*at, key), value)
            for rule, level in (levels or {}).items():
                rule_at = (*at, key, rule)
                if not _RULE_ID.fullmatch(rule):
                    self._error(
                        rule_at,
                        f'The rule ID "{rule}" is not correct. Use the form "COV-003".',
                    )
                elif level not in RULE_SEVERITIES:
                    self._error(
                        rule_at,
                        f"The severity {_toml(level)} is unknown. "
                        f"Use one of: {', '.join(RULE_SEVERITIES)}.",
                    )
                else:
                    severity.append((rule, level))
        self.values["rules"] = Rules(optional, tuple(sorted(severity)))

    def _trace(self, at: KeyPath, table: dict[str, object]) -> None:
        baseline: str | None = None
        tests: tuple[PurePosixPath, ...] = ()
        for key, value in self._keys(at, table, {"baseline", "tests"}):
            if key == "baseline":
                baseline = self._text((*at, key), value)
            else:
                tests = self._paths((*at, key), value) or ()
        self.values["trace"] = Trace(baseline, tests)

    def _aws(self, at: KeyPath, table: dict[str, object]) -> None:
        for key, value in self._keys(at, table, {"regions"}):
            self.values["regions"] = self._texts((*at, key), value) or ()

    def _iac(self, at: KeyPath, table: dict[str, object]) -> None:
        for key, value in self._keys(at, table, {"opentofu"}):
            options = self._table((*at, key), value)
            if options is None:
                continue
            encryption = False
            for name, item in self._keys((*at, key), options, {"state_encryption"}):
                encryption = bool(self._bool((*at, key, name), item))
            self.values["opentofu"] = OpenTofuOptions(state_encryption=encryption)

    # The checks of one value.

    def _keys(
        self, at: KeyPath, table: dict[str, object], known: set[str]
    ) -> Iterator[tuple[str, object]]:
        """Give the known keys of a table. Report each unknown key."""
        for key, value in table.items():
            if key in known:
                yield key, value
            else:
                self._unknown((*at, key))

    def _table(self, at: KeyPath, value: object) -> dict[str, object] | None:
        if isinstance(value, dict):
            return cast(dict[str, object], value)
        self._type(at, "a table", value)
        return None

    def _text(self, at: KeyPath, value: object) -> str | None:
        if isinstance(value, str) and value:
            return value
        self._type(at, "a text that is not empty", value)
        return None

    def _bool(self, at: KeyPath, value: object) -> bool | None:
        if isinstance(value, bool):
            return value
        self._type(at, "true or false", value)
        return None

    def _texts(self, at: KeyPath, value: object) -> tuple[str, ...] | None:
        """Check a list of texts. Give the texts sorted and with no duplicate."""
        if not isinstance(value, list):
            self._type(at, "a list of texts", value)
            return None
        items = cast(list[object], value)
        texts = [self._text(at, item) for item in items]
        if None in texts:
            return None
        return tuple(sorted({text for text in texts if text is not None}))

    def _path(self, at: KeyPath, value: object) -> PurePosixPath | None:
        """Check a relative path with "/" as the separator."""
        text = self._text(at, value)
        if text is None:
            return None
        path = PurePosixPath(text)
        if "\\" in text or path.is_absolute() or ".." in path.parts or ":" in text:
            self._error(
                at,
                f'The path "{text}" is not correct. Use a relative path with "/" '
                'and no "..", in the folder of the configuration file.',
            )
            return None
        return path

    def _paths(self, at: KeyPath, value: object) -> tuple[PurePosixPath, ...] | None:
        if not isinstance(value, list):
            self._type(at, "a list of paths", value)
            return None
        items = cast(list[object], value)
        paths = [self._path(at, item) for item in items]
        if None in paths:
            return None
        return tuple(sorted({path for path in paths if path is not None}))

    # The errors.

    def _unknown(self, at: KeyPath) -> None:
        self._error(at, f'The key "{_dotted(at)}" is unknown.')

    def _type(self, at: KeyPath, expected: str, value: object) -> None:
        self._error(at, f'The key "{_dotted(at)}" must be {expected}, not {_toml(value)}.')

    def _error(self, at: KeyPath, message: str) -> None:
        line = self._line(at)
        prefix = f"{self.path}:{line}" if line else f"{self.path}"
        self.errors.append((line, f"{prefix}: {message}"))

    def _line(self, at: KeyPath) -> int:
        """Give the line of a key, or of the nearest table that contains it."""
        for size in range(len(at), 0, -1):
            line = self.lines.get(at[:size])
            if line is not None:
                return line
        return 0


def _dotted(at: KeyPath) -> str:
    return ".".join(key if _NAME.fullmatch(key) else f'"{key}"' for key in at)


def _toml(value: object) -> str:
    """Give a short TOML form of a value for a message."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, dict):
        return "a table"
    if isinstance(value, list):
        return "a list"
    return str(value)


# trace: PRD-CORE-014
def _key_lines(text: str) -> dict[KeyPath, int]:
    """Find the line of each key and of each table header in TOML text.

    `tomllib` gives no line numbers for the keys. This scanner reads the text
    that `tomllib` accepted, so it does not check the syntax. It does not give
    the keys in an inline table. The reader then uses the line of the key
    that contains the inline table.
    """
    lines: dict[KeyPath, int] = {}
    table: KeyPath = ()
    index, line, size = 0, 1, len(text)
    depth = 0
    start_of_line = True

    def skip_string() -> None:
        nonlocal index, line
        quote = text[index]
        triple = text.startswith(quote * 3, index)
        end = quote * 3 if triple else quote
        index += len(end)
        while index < size:
            if quote == '"' and text[index] == "\\":
                index += 2
                continue
            if text.startswith(end, index):
                index += len(end)
                # A multi-line string can end with up to two more quotes.
                while triple and index < size and text[index] == quote:
                    index += 1
                return
            if text[index] == "\n":
                line += 1
            index += 1

    def read_key() -> KeyPath:
        nonlocal index
        parts: list[str] = []
        while index < size:
            char = text[index]
            if char in " \t.":
                index += 1
            elif char in "\"'":
                begin = index
                skip_string()
                parts.append(tomllib.loads(f"k = {text[begin:index]}")["k"])
            elif char in "=]\n":
                break
            else:
                begin = index
                while index < size and text[index] not in " \t.=]\n":
                    index += 1
                parts.append(text[begin:index])
        return tuple(parts)

    while index < size:
        char = text[index]
        if char == "\n":
            line += 1
            index += 1
            start_of_line = depth == 0
            continue
        if char in " \t\r":
            index += 1
            continue
        if char == "#":
            while index < size and text[index] != "\n":
                index += 1
            continue
        if start_of_line:
            start_of_line = False
            if char == "[":
                index += 2 if text.startswith("[[", index) else 1
                table = read_key()
                lines.setdefault(table, line)
                while index < size and text[index] != "\n":
                    index += 1
                continue
            key = table + read_key()
            lines.setdefault(key, line)
            continue
        if char in "\"'":
            skip_string()
            continue
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        index += 1
    return lines
