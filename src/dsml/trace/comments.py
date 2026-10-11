# trace: PRD-TRACE-009, PRD-TRACE-010, PRD-TRACE-011, PRD-CORE-032
"""Read the trace comments in the hand-written files.

A trace comment is a line comment with the form `trace: <ID>[, <ID>]`:
`# trace: R-001` in Python, HCL and YAML files, and `// trace: R-001` in
TypeScript files (PRD-TRACE-009). An ID is a short name, for example
`R-001`, or a qualified name, for example `OrderService::getOrderStatus`.
The comment must be on a line of its own.

The reader reads the files in the output folders and in the test folders of
the configuration file. It does not read a generated file of the manifest
`.dsml/generated.json` (PRD-TRACE-010). The caller gives these folders and
files, so the module does not read the configuration file or the manifest.
The reader does not go into the folders of `SKIPPED_FOLDERS`, and it does
not follow a symbolic link.

A trace comment applies to the next symbol in the file. If no symbol
follows, it applies to the file (PRD-TRACE-011). These are the symbols:

- Python: a `def` or a `class`. The name has the names of the classes and
  functions that contain it, for example `OrderStore.get`.
- HCL: a top-level block. The name is the address of the block, for
  example `aws_s3_bucket.logs`, `data.aws_iam_policy_document.read`,
  `module.network`, `var.region` or `output.url`.
- TypeScript: a function, a class or an exported constant.
- YAML: no symbols. Each comment applies to the file.

The reader does not compare the IDs with the model. The orphans report does
this (PRD-TRACE-012). The results are sorted by file and line, so the order
of the files on disk does not change them (PRD-CORE-032).
"""

import enum
import io
import re
import tokenize
from collections.abc import Collection, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final


class Language(enum.Enum):
    """The file types that can have trace comments."""

    PYTHON = "python"
    HCL = "hcl"
    YAML = "yaml"
    TYPESCRIPT = "typescript"


LANGUAGES: Final = {
    ".cts": Language.TYPESCRIPT,
    ".hcl": Language.HCL,
    ".mts": Language.TYPESCRIPT,
    ".py": Language.PYTHON,
    ".tf": Language.HCL,
    ".tofu": Language.HCL,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".yaml": Language.YAML,
    ".yml": Language.YAML,
}
"""The file type of each file name extension. The reader skips other files."""

SKIPPED_FOLDERS: Final = frozenset(
    {".dsml", ".git", ".terraform", ".venv", "__pycache__", "node_modules"}
)
"""The folders that the reader does not go into: tool data and installed packages."""

_MARKER = re.compile(r"\s*trace:(.*)")
_NAME = r"(?:[A-Za-z_][A-Za-z0-9_-]*|'[^'\\]+')"
_ID = re.compile(rf"{_NAME}(?:::{_NAME})*")


# trace: PRD-TRACE-009, PRD-TRACE-011
@dataclass(frozen=True, slots=True)
class TraceComment:
    """One trace comment in a hand-written file."""

    path: str
    """The file, relative to the folder of the configuration file, with "/"."""
    line: int
    """The line of the comment. The first line is 1."""
    ids: tuple[str, ...]
    """The IDs in the comment, in the order of the comment."""
    symbol: str | None
    """The symbol that the comment applies to. `None` if it applies to the file."""
    symbol_line: int | None
    """The line of the symbol. `None` if the comment applies to the file."""


# trace: PRD-TRACE-009
@dataclass(frozen=True, slots=True)
class TraceProblem:
    """A trace comment or a file that the reader cannot read."""

    path: str
    line: int | None
    """The line of the comment. `None` if the problem is about the full file."""
    message: str


# trace: PRD-TRACE-010, PRD-CORE-032
@dataclass(frozen=True, slots=True)
class TraceComments:
    """The trace comments of all hand-written files, sorted by file and line."""

    comments: tuple[TraceComment, ...] = ()
    problems: tuple[TraceProblem, ...] = ()


# trace: PRD-TRACE-010, PRD-CORE-032
def read_trace_comments(
    root: Path, folders: Iterable[PurePosixPath], generated: Collection[str]
) -> TraceComments:
    """Read the trace comments in the hand-written files of the folders.

    `root` is the folder of the configuration file. `folders` are the output
    folders and the test folders of the configuration file, relative to
    `root`. `generated` are the paths of the generated files of the manifest
    `.dsml/generated.json`. The reader does not read these files.

    The caller gives the folders and the generated files, so this package
    reads only the IR and the files on disk (PRD-CORE-026).
    """
    comments: list[TraceComment] = []
    problems: list[TraceProblem] = []
    for path in hand_written_files(root, folders, generated):
        language = LANGUAGES[PurePosixPath(path).suffix]
        try:
            text = (root / path).read_bytes().decode("utf-8-sig")
        except UnicodeDecodeError:
            problems.append(TraceProblem(path, None, "The file does not have UTF-8 encoding."))
            continue
        except OSError as error:
            problems.append(TraceProblem(path, None, f"Cannot read the file: {error.strerror}."))
            continue
        found, found_problems = parse_trace_comments(path, text, language)
        comments.extend(found)
        problems.extend(found_problems)
    return TraceComments(tuple(comments), tuple(problems))


# trace: PRD-TRACE-010, PRD-CORE-032
def hand_written_files(
    root: Path, folders: Iterable[PurePosixPath], generated: Collection[str]
) -> list[str]:
    """Give the hand-written files with a known extension in the folders, sorted.

    The arguments are the same as the arguments of `read_trace_comments`.
    The result does not contain the generated files.
    """
    paths: set[str] = set()
    for folder in folders:
        paths.update(_files(root, folder))
    return sorted(paths.difference(generated))


def _files(root: Path, folder: PurePosixPath) -> Iterator[str]:
    """Give the path of each file with a known extension in the folder."""
    base = root / folder
    if base.is_symlink() or not base.is_dir():
        return
    for child in sorted(base.iterdir()):
        if child.is_symlink():
            continue
        if child.is_dir():
            if child.name not in SKIPPED_FOLDERS:
                yield from _files(root, folder / child.name)
        elif child.is_file() and child.suffix in LANGUAGES:
            yield (folder / child.name).as_posix()


# trace: PRD-TRACE-009, PRD-TRACE-011
def parse_trace_comments(
    path: str, text: str, language: Language
) -> tuple[list[TraceComment], list[TraceProblem]]:
    """Find the trace comments in the text of one file and the symbol of each comment."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    match language:
        case Language.PYTHON:
            raw_comments, symbols = _python(text)
        case Language.HCL:
            raw_comments, symbols = _hcl(text)
        case Language.YAML:
            raw_comments, symbols = _yaml(text), []
        case Language.TYPESCRIPT:
            raw_comments, symbols = _typescript(text)
    comments: list[TraceComment] = []
    problems: list[TraceProblem] = []
    for line, body in raw_comments:
        marker = _MARKER.fullmatch(body)
        if marker is None:
            continue
        ids = tuple(item.strip() for item in marker.group(1).split(","))
        bad = [item for item in ids if not _ID.fullmatch(item)]
        if ids == ("",):
            problems.append(TraceProblem(path, line, "The trace comment has no ID."))
        elif bad:
            items = ", ".join(f'"{item}"' for item in bad)
            problems.append(
                TraceProblem(
                    path,
                    line,
                    f"The trace comment has an item that is not a short name "
                    f"or a qualified name: {items}.",
                )
            )
        else:
            symbol = next((item for item in symbols if item[0] > line), None)
            comments.append(
                TraceComment(
                    path,
                    line,
                    ids,
                    None if symbol is None else symbol[1],
                    None if symbol is None else symbol[0],
                )
            )
    return comments, problems


_Found = list[tuple[int, str]]
"""A list of (line, text) pairs, sorted by line."""


def _python(text: str) -> tuple[_Found, _Found]:
    """Find the comment lines and the `def` and `class` symbols of a Python file."""
    comments: _Found = []
    symbols: _Found = []
    stack: list[tuple[int, str]] = []
    depth = 0
    keyword_line: int | None = None
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.INDENT:
                depth += 1
            elif token.type == tokenize.DEDENT:
                depth -= 1
            elif token.type == tokenize.COMMENT:
                if not token.line[: token.start[1]].strip():
                    comments.append((token.start[0], token.string[1:]))
            elif token.type == tokenize.NAME and keyword_line is not None:
                stack = [item for item in stack if item[0] < depth]
                stack.append((depth, token.string))
                symbols.append((keyword_line, ".".join(name for _, name in stack)))
                keyword_line = None
            elif token.type == tokenize.NAME and token.string in ("def", "class"):
                keyword_line = token.start[0]
    except SyntaxError, tokenize.TokenError:
        return _python_lines(text)
    return comments, symbols


_PYTHON_SYMBOL = re.compile(r"\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)")


def _python_lines(text: str) -> tuple[_Found, _Found]:
    """Find the comments and the symbols of a Python file that does not tokenize."""
    comments: _Found = []
    symbols: _Found = []
    for number, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            comments.append((number, stripped[1:]))
        elif symbol := _PYTHON_SYMBOL.match(line):
            symbols.append((number, symbol.group(1)))
    return comments, symbols


_HCL_BLOCK = re.compile(r'([A-Za-z_][\w-]*)((?:\s+(?:"[^"]*"|[A-Za-z_][\w-]*))*)\s*\{')
_HCL_LABEL = re.compile(r'"([^"]*)"|([A-Za-z_][\w-]*)')
_HCL_HEREDOC = re.compile(r"<<-?([A-Za-z_]\w*)\s*$")
_HCL_PREFIXES: Final = {"data": "data", "module": "module", "output": "output", "variable": "var"}


def _hcl(text: str) -> tuple[_Found, _Found]:
    """Find the comment lines and the top-level blocks of an HCL file."""
    comments: _Found = []
    symbols: _Found = []
    scanner = _HclScanner()
    for number, line in enumerate(text.split("\n"), 1):
        if scanner.heredoc is not None:
            if line.strip() == scanner.heredoc:
                scanner.heredoc = None
            continue
        if not scanner.stack:
            stripped = line.strip()
            if stripped.startswith("#"):
                comments.append((number, stripped[1:]))
            elif scanner.depth == 0 and (block := _HCL_BLOCK.match(stripped)):
                symbols.append((number, _hcl_address(block.group(1), block.group(2))))
        scanner.scan(line)
    return comments, symbols


def _hcl_address(kind: str, labels_text: str) -> str:
    """Give the address of an HCL block from its type and its labels."""
    labels = [quoted or bare for quoted, bare in _HCL_LABEL.findall(labels_text)]
    if kind == "resource" and labels:
        return ".".join(labels)
    return ".".join([_HCL_PREFIXES.get(kind, kind), *labels])


class _HclScanner:
    """Count the braces of an HCL file outside strings, comments and heredocs.

    `stack` is not empty while a string or a block comment continues on the
    next line.
    """

    def __init__(self) -> None:
        self.depth = 0
        self.heredoc: str | None = None
        self.stack: list[str] = []

    def scan(self, line: str) -> None:
        index = 0
        while index < len(line):
            char = line[index]
            pair = line[index : index + 2]
            top = self.stack[-1] if self.stack else "code"
            if top == "comment":
                if pair == "*/":
                    self.stack.pop()
                    index += 1
            elif top == "string":
                if char == "\\":
                    index += 1
                elif char == '"':
                    self.stack.pop()
                elif pair in ("${", "%{"):
                    self.stack.append("template")
                    index += 1
            elif char == '"':
                self.stack.append("string")
            elif pair == "/*":
                self.stack.append("comment")
                index += 1
            elif char == "#" or pair == "//":
                return
            elif top == "template":
                if char == "{":
                    self.stack.append("template")
                elif char == "}":
                    self.stack.pop()
            elif char == "{":
                self.depth += 1
            elif char == "}":
                self.depth = max(self.depth - 1, 0)
            elif heredoc := _HCL_HEREDOC.match(line, index):
                self.heredoc = heredoc.group(1)
                return
            index += 1


_YAML_BLOCK_SCALAR = re.compile(r"(?:.*:|\s*-)\s+[|>][-+0-9]*\s*(?:#.*)?")


def _yaml(text: str) -> _Found:
    """Find the comment lines of a YAML file, outside block scalars."""
    comments: _Found = []
    block_indent: int | None = None
    for number, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if block_indent is not None:
            if not stripped or indent > block_indent:
                continue
            block_indent = None
        if stripped.startswith("#"):
            comments.append((number, stripped[1:]))
        elif _YAML_BLOCK_SCALAR.fullmatch(line):
            block_indent = indent
    return comments


_TS_IDENTIFIER = r"[A-Za-z_$][\w$]*"
_TS_SYMBOL = re.compile(
    rf"(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:async\s+)?function\b\s*\*?\s*"
    rf"(?P<function>{_TS_IDENTIFIER})?"
    rf"|(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?class\s+"
    rf"(?P<class>{_TS_IDENTIFIER})"
    rf"|export\s+(?:declare\s+)?const\s+(?P<const>{_TS_IDENTIFIER})"
)


def _typescript(text: str) -> tuple[_Found, _Found]:
    """Find the comment lines and the symbols of a TypeScript file."""
    comments: _Found = []
    symbols: _Found = []
    open_text: str | None = None
    for number, line in enumerate(text.split("\n"), 1):
        if open_text is None:
            stripped = line.strip()
            if stripped.startswith("//"):
                comments.append((number, stripped[2:]))
                continue
            if symbol := _TS_SYMBOL.match(stripped):
                name = symbol.group("function") or symbol.group("class") or symbol.group("const")
                symbols.append((number, name or "default"))
        open_text = _typescript_scan(line, open_text)
    return comments, symbols


def _typescript_scan(line: str, open_text: str | None) -> str | None:
    """Give the block comment ("*/") or the template literal ("`") that continues
    after the line, or `None`.
    """
    index = 0
    quote: str | None = None
    while index < len(line):
        char = line[index]
        pair = line[index : index + 2]
        if open_text == "*/":
            if pair == "*/":
                open_text = None
                index += 1
        elif open_text == "`":
            if char == "\\":
                index += 1
            elif char == "`":
                open_text = None
        elif quote is not None:
            if char == "\\":
                index += 1
            elif char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == "`":
            open_text = "`"
        elif pair == "/*":
            open_text = "*/"
            index += 1
        elif pair == "//":
            return None
        index += 1
    return open_text
