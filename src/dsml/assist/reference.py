# trace: PRD-AI-007, PRD-AI-015, PRD-TOP-005, PRD-TOP-009
"""The DSML reference for AI agents, as Markdown from the installed toolchain.

The reference has four parts. Each part has one function:

| Part | Function | Source |
| --- | --- | --- |
| `keywords` | `keywords()` | The DSML library source in `dsml.library` |
| `rules` | `rules()` | The rule registry in `dsml.validate.rules` |
| `commands` | `commands()` | The argument parser of `dsml.cli` |
| `examples` | `examples()` | The starter models in `dsml.starter` |

The skills and the MCP resources use this text. Thus they agree with the
installed version of the library, the rule catalog and the CLI (Q68, Q69).

The output is deterministic (PRD-CORE-028 to PRD-CORE-038): the lists are
sorted, the text has LF line ends, and it contains no time, no random value
and no path of the installation. The module does not use the network or an
AI model (PRD-TOP-005).

The module reads the library source as text and does not import
`opensysml` (PRD-CORE-020). The library uses a small set of SysML forms, so
a small reader is sufficient.
"""

import argparse
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dsml import starter
from dsml.cli import build_parser
from dsml.config import OPTIONAL_RULE_SETS
from dsml.library import LIBRARY_VERSION, library_text
from dsml.validate.rules import registry

GENERATED_NOTE: Final = (
    "<!-- The module dsml.assist.reference writes this file "
    "from the installed toolchain. Do not change it. -->"
)
"""The first line of each part."""

PARTS_FILE: Final = "parts.txt"
"""The file in the folder `references/` of a skill that lists the parts of the skill."""

# trace: PRD-DSML-010
LAYERS: Final[tuple[tuple[str, str], ...]] = (
    ("needs", "Needs layer"),
    ("requirements", "Requirements layer"),
    ("application", "Application layer"),
    ("infrastructure", "Infrastructure layer"),
    ("verification", "Verification layer"),
    ("all", "All layers"),
)
"""The layers of the keywords in the order of the reference, with their headings."""

# trace: PRD-DSML-010
KEYWORD_LAYERS: Final[Mapping[str, str]] = {
    "Stakeholder": "needs",
    "Need": "needs",
    "Requirement": "requirements",
    "Application": "application",
    "Calls": "application",
    "Destructive": "application",
    "Entity": "application",
    "Exposed": "application",
    "ExternalApi": "application",
    "FieldRules": "application",
    "Key": "application",
    "Operation": "application",
    "Roles": "application",
    "View": "application",
    "AwsCognito": "infrastructure",
    "AwsEcsService": "infrastructure",
    "AwsRdsPostgres": "infrastructure",
    "AwsSecrets": "infrastructure",
    "AwsStaticSite": "infrastructure",
    "AwsVpc": "infrastructure",
    "ContainerService": "infrastructure",
    "Environment": "infrastructure",
    "Network": "infrastructure",
    "Override": "infrastructure",
    "Realizes": "infrastructure",
    "RelationalDatabase": "infrastructure",
    "SecretStore": "infrastructure",
    "StaticSite": "infrastructure",
    "ToolingAccount": "infrastructure",
    "UserDirectory": "infrastructure",
    "Uses": "infrastructure",
    "Verification": "verification",
    "DsmlVersion": "all",
    "Waiver": "all",
}
"""The layer of each keyword of the DSML library.

A new keyword of the library must also go in this table. If it is not in the
table, `keywords()` raises `ValueError`, so a test finds the omission.
"""


# ----------------------------------------------------------------------
# A reader for the DSML library source
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Feature:
    """An attribute or a reference of a keyword, as the library gives it."""

    name: str
    type: str
    multiplicity: str
    default: str | None
    reference: bool
    ordered: bool


@dataclass(frozen=True, slots=True)
class Keyword:
    """One keyword of the DSML library: a metadata definition."""

    name: str
    layer: str
    doc: str
    features: tuple[Feature, ...]
    element_kind: bool
    """True if the keyword gives the kind of an element (semantic metadata)."""


@dataclass(frozen=True, slots=True)
class Enumeration:
    """An enumeration definition of the library with its values."""

    name: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AttributeType:
    """An attribute definition of the library that specializes a scalar type."""

    name: str
    general: str
    doc: str


_COMMENT: Final = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT: Final = re.compile(r"//[^\n]*")
_PLACEHOLDER: Final = re.compile(r"\x00(\d+)\x00")
_DOC: Final = re.compile(r"\bdoc\s*\x00(\d+)\x00")
_METADATA: Final = re.compile(
    r"\bmetadata\s+def\s+(?P<name>\w+)\s*(?P<semantic>:>\s*SemanticMetadata\s*)?\{"
)
_BASE_TYPE: Final = re.compile(r"baseType\s*=\s*BaseTypes::(?P<usage>\w+)")
_FEATURE: Final = re.compile(
    r"^\s*(?P<ref>ref\s+)?(?:attribute|part|action)\s+(?P<name>'?\w+'?)\s*:\s*(?P<type>\w+)"
    r"\s*(?:\[(?P<multiplicity>[^\]]*)\])?\s*(?P<ordered>ordered)?"
    r"\s*(?:default\s*)?(?:=\s*(?P<default>[^;]+?))?\s*;",
    re.MULTILINE,
)
_DEFINITION: Final = re.compile(
    r"\b(?:part|concern|requirement|action|verification|attribute|occurrence)\s+def\s+"
    r"(?P<name>\w+)\s*(?::>\s*(?P<general>\w+)\s*)?(?P<end>[;{])"
)
_USAGE: Final = re.compile(
    r"\babstract\s+\w+\s+(?P<name>\w+)\s*(?::\s*(?P<type>\w+)\s*)?(?:\[[^\]]*\]\s*)?"
    r"(?::>\s*\w+\s*)?(?P<end>[;{])"
)
_ENUMERATION: Final = re.compile(r"\benum\s+def\s+(?P<name>\w+)\s*\{(?P<body>[^}]*)\}")
_ATTRIBUTE_TYPE: Final = re.compile(
    r"\battribute\s+def\s+(?P<name>\w+)\s*:>\s*(?P<general>\w+)\s*\{"
)


def _doc_text(comment: str) -> str:
    """Give the text of a block comment as one line."""
    lines = comment.removeprefix("/*").removesuffix("*/").splitlines()
    words = [line.strip().removeprefix("*").strip() for line in lines]
    return " ".join(word for word in words if word)


def _body(text: str, start: int) -> tuple[str, int]:
    """Give the text between the brace at `start` and its closing brace, and the end index."""
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    raise ValueError("A brace of the DSML library has no closing brace.")


def _top_level(body: str) -> str:
    """Give the text of a body without the bodies that it contains."""
    parts: list[str] = []
    depth = 0
    for character in body:
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
        elif depth == 0:
            parts.append(character)
    return "".join(parts)


@dataclass(frozen=True, slots=True)
class _Library:
    """The parts of the library source that the reference uses."""

    keywords: tuple[Keyword, ...]
    enumerations: tuple[Enumeration, ...]
    attribute_types: tuple[AttributeType, ...]


class _Reader:
    """Read the keywords, enumerations and attribute types of the library source."""

    def __init__(self, source: str) -> None:
        self._docs: list[str] = []
        text = _COMMENT.sub(self._keep_doc, source)
        self._text = _LINE_COMMENT.sub("", text)
        self._usages, self._definitions = self._base_types()

    def _keep_doc(self, match: re.Match[str]) -> str:
        self._docs.append(_doc_text(match.group(0)))
        return f"\x00{len(self._docs) - 1}\x00"

    def _doc(self, body: str) -> str:
        match = _DOC.search(_top_level(body))
        return self._docs[int(match.group(1))] if match else ""

    @staticmethod
    def _features(body: str) -> tuple[Feature, ...]:
        return tuple(
            Feature(
                name=match["name"],
                type=match["type"],
                multiplicity=match["multiplicity"] or "1",
                default=match["default"],
                reference=match["ref"] is not None,
                ordered=match["ordered"] is not None,
            )
            for match in _FEATURE.finditer(_top_level(body))
        )

    def _base_types(self) -> tuple[dict[str, tuple[str | None, str]], dict[str, tuple[str, str]]]:
        """Give the usages and the definitions of the package BaseTypes.

        A usage gives its type and its body. A definition gives its general
        type and its body.
        """
        start = re.search(r"\bpackage\s+BaseTypes\s*\{", self._text)
        if start is None:
            raise ValueError("The DSML library has no package BaseTypes.")
        package, _ = _body(self._text, start.end() - 1)
        usages: dict[str, tuple[str | None, str]] = {}
        definitions: dict[str, tuple[str, str]] = {}
        for match in _USAGE.finditer(package):
            usages[match["name"]] = (match["type"], self._match_body(package, match))
        for match in _DEFINITION.finditer(package):
            definitions[match["name"]] = (match["general"] or "", self._match_body(package, match))
        return usages, definitions

    @staticmethod
    def _match_body(text: str, match: re.Match[str]) -> str:
        """Give the body of a declaration that ends with "{", or "" for a declaration with ";"."""
        return _body(text, match.end() - 1)[0] if match["end"] == "{" else ""

    def _base_features(self, usage_name: str) -> tuple[Feature, ...]:
        usages, definitions = self._usages, self._definitions
        if usage_name not in usages:
            raise ValueError(f'The DSML library has no base type "{usage_name}".')
        type_name, body = usages[usage_name]
        features = list(self._features(body))
        while type_name:
            general, definition_body = definitions[type_name]
            features.extend(self._features(definition_body))
            type_name = general
        return tuple(features)

    def read(self) -> _Library:
        keywords: list[Keyword] = []
        for match in _METADATA.finditer(self._text):
            name = match["name"]
            body, _ = _body(self._text, match.end() - 1)
            if name not in KEYWORD_LAYERS:
                raise ValueError(
                    f'The keyword "{name}" of the DSML library has no layer. '
                    "Add it to KEYWORD_LAYERS in dsml.assist.reference."
                )
            base = _BASE_TYPE.search(body)
            features = self._features(body)
            if base is not None:
                features = self._base_features(base["usage"]) + features
            keywords.append(
                Keyword(
                    name=name,
                    layer=KEYWORD_LAYERS[name],
                    doc=self._doc(body),
                    features=features,
                    element_kind=match["semantic"] is not None,
                )
            )
        enumerations = tuple(
            Enumeration(
                match["name"],
                tuple(value.strip() for value in match["body"].split(";") if value.strip()),
            )
            for match in _ENUMERATION.finditer(self._text)
        )
        attribute_types: list[AttributeType] = []
        for match in _ATTRIBUTE_TYPE.finditer(self._text):
            body, _ = _body(self._text, match.end() - 1)
            attribute_types.append(AttributeType(match["name"], match["general"], self._doc(body)))
        return _Library(
            keywords=tuple(sorted(keywords, key=_keyword_order)),
            enumerations=tuple(sorted(enumerations, key=lambda item: item.name)),
            attribute_types=tuple(sorted(attribute_types, key=lambda item: item.name)),
        )


def _keyword_order(keyword: Keyword) -> tuple[int, str]:
    order = [layer for layer, _ in LAYERS]
    return (order.index(keyword.layer), keyword.name)


# trace: PRD-AI-007
def library_keywords() -> tuple[Keyword, ...]:
    """Give the keywords of the installed DSML library, sorted by layer and name."""
    return _Reader(library_text()).read().keywords


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------


def _cell(text: str) -> str:
    """Give text that a Markdown table cell can hold."""
    return text.replace("|", "\\|").replace("\n", " ")


def _document(title: str, introduction: str, sections: list[str]) -> str:
    """Join a title, an introduction and the sections into one Markdown text."""
    text = "\n\n".join([GENERATED_NOTE, f"# {title}", introduction, *sections])
    return text.rstrip("\n") + "\n"


def _feature_rows(features: tuple[Feature, ...]) -> str:
    rows = [
        "| Attribute | Type | Multiplicity | Default |",
        "| --- | --- | --- | --- |",
    ]
    for feature in features:
        kind = f"reference to `{feature.type}`" if feature.reference else f"`{feature.type}`"
        multiplicity = feature.multiplicity + (", ordered" if feature.ordered else "")
        default = f"`{feature.default}`" if feature.default is not None else ""
        rows.append(f"| `{feature.name}` | {kind} | {_cell(multiplicity)} | {_cell(default)} |")
    return "\n".join(rows)


def _form(keyword: Keyword) -> str:
    """Tell how a model writes the keyword."""
    prefix = f"`#{keyword.name}` before the declaration"
    if keyword.element_kind:
        return f"Form: element kind. Write {prefix}."
    if not keyword.features:
        return f"Form: annotation. Write {prefix}."
    return (
        f"Form: annotation. Write {prefix}, or write `@{keyword.name} {{ ... }}` "
        "in the body of the element to give the attribute values."
    )


# trace: PRD-AI-007, PRD-AI-015, PRD-CORE-028
def keywords() -> str:
    """Give the `keywords` part: each keyword with its layer, its attributes and its doc text."""
    library = _Reader(library_text()).read()
    sections: list[str] = []
    for layer, heading in LAYERS:
        members = [keyword for keyword in library.keywords if keyword.layer == layer]
        if not members:
            continue
        sections.append(f"## {heading}")
        for keyword in members:
            lines = [f"### `{keyword.name}`", "", keyword.doc or "No description."]
            lines += ["", _form(keyword)]
            if keyword.features:
                lines += ["", _feature_rows(keyword.features)]
            else:
                lines += ["", "The keyword has no attributes."]
            sections.append("\n".join(lines))
    sections.append("## Enumerations")
    rows = ["| Enumeration | Values |", "| --- | --- |"]
    for enumeration in library.enumerations:
        values = ", ".join(f"`{value}`" for value in enumeration.values)
        rows.append(f"| `{enumeration.name}` | {values} |")
    sections.append("\n".join(rows))
    sections.append("## Attribute types")
    rows = ["| Type | Specializes | Description |", "| --- | --- | --- |"]
    for attribute_type in library.attribute_types:
        rows.append(
            f"| `{attribute_type.name}` | `{attribute_type.general}` "
            f"| {_cell(attribute_type.doc)} |"
        )
    sections.append("\n".join(rows))
    introduction = "\n".join(
        [
            f"This part gives the keywords of the DSML library, version {LIBRARY_VERSION}.",
            "A model imports the library with `private import DSML::*;`.",
            "",
            "An element kind gives the kind of the element that it annotates, for example "
            "`#Need concern <'N-001'> firstNeed { ... }`. "
            "Give the attribute values of an element kind with redefinitions, for example "
            "`:>> priority = Priority::must;`.",
            "An annotation adds data to an element, for example `@FieldRules { maxLength = 40; }` "
            "in the body of a field.",
            "The multiplicity 1 tells that the attribute must have one value.",
        ]
    )
    return _document("DSML keywords", introduction, sections)


# trace: PRD-AI-007, PRD-AI-015, PRD-CORE-028
def rules() -> str:
    """Give the `rules` part: each rule with its ID, severity, message and correction."""
    checks = registry()
    sections: list[str] = []
    category = ""
    for rule_id in sorted(checks):
        rule = checks[rule_id].rule
        if rule.category != category:
            category = rule.category
            sections.append(f"## {category}")
        lines = [
            f"### `{rule.id}`",
            "",
            f"- Severity: {rule.severity}",
            f"- Message: {rule.message}",
            f"- Correction: {rule.fix_hint}",
        ]
        if rule.optional:
            lines.append(
                f"- Rule set: {rule.category}. This rule set is off by default. "
                f'Turn it on with `optional = ["{rule.category}"]` in the table `[rules]`.'
            )
        sections.append("\n".join(lines))
    introduction = "\n".join(
        [
            "This part gives the rules of the validation rule catalog, sorted by rule ID.",
            "`dsml validate` gives a finding with the rule ID for each problem.",
            "Do the correction of the rule, then run `dsml validate` again.",
            "The table `[rules.severity]` of the configuration file can change the severity "
            'of a rule, for example `"COV-003" = "error"`.',
            "The optional rule sets are: "
            + ", ".join(f"`{name}`" for name in OPTIONAL_RULE_SETS)
            + ".",
        ]
    )
    return _document("DSML validation rules", introduction, sections)


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, tuple[str, argparse.ArgumentParser]]:
    """Give the summary and the parser of each subcommand, by name."""
    for action in parser._actions:  # pyright: ignore[reportPrivateUsage]
        if isinstance(action, argparse._SubParsersAction):  # pyright: ignore[reportPrivateUsage]
            summaries = {
                choice.dest: choice.help or ""
                for choice in action._choices_actions  # pyright: ignore[reportPrivateUsage, reportUnknownMemberType, reportUnknownVariableType]
            }
            choices: Mapping[str, argparse.ArgumentParser] = action.choices  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            return {name: (summaries.get(name, ""), choices[name]) for name in choices}
    return {}


def _arguments(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    return [
        action
        for action in parser._actions  # pyright: ignore[reportPrivateUsage]
        if not isinstance(action, argparse._HelpAction)  # pyright: ignore[reportPrivateUsage]
    ]


def _argument_name(action: argparse.Action) -> str:
    if action.option_strings:
        return ", ".join(sorted(action.option_strings))
    return str(action.metavar or action.dest)


def _argument_value(action: argparse.Action) -> str:
    if action.choices is not None:
        return ", ".join(f"`{choice}`" for choice in action.choices)
    if action.nargs == 0:
        return "No value"
    if action.option_strings:
        return f"`{action.metavar or action.dest.upper()}`"
    return ""


def _argument_rows(actions: list[argparse.Action]) -> str:
    rows = ["| Argument | Value | Description |", "| --- | --- | --- |"]
    for action in actions:
        name = _argument_name(action)
        value = _argument_value(action)
        if not action.option_strings:
            count = {"*": "zero or more", "+": "one or more", "?": "optional"}
            if isinstance(action.nargs, str) and action.nargs in count:
                value = f"{value} ({count[action.nargs]})".strip()
        rows.append(f"| `{_cell(name)}` | {_cell(value)} | {_cell(action.help or '')} |")
    return "\n".join(rows)


def _sort_key(action: argparse.Action) -> tuple[int, str]:
    """Put the positional arguments first, in their order, then the options by name."""
    if not action.option_strings:
        return (0, "")
    return (1, _argument_name(action))


# trace: PRD-AI-007, PRD-AI-015, PRD-CORE-028
def _command_rows(sub: argparse.ArgumentParser, common: set[str]) -> str:
    """Give the rows of the arguments of `sub` that are not in `common`."""
    own = sorted(
        (action for action in _arguments(sub) if _argument_name(action) not in common),
        key=_sort_key,
    )
    return _argument_rows(own) if own else "The subcommand has no other options."


# trace: PRD-AI-007, PRD-AI-015, PRD-CORE-028
def commands() -> str:
    """Give the `commands` part: each `dsml` subcommand with its options.

    The common options are the options that all subcommands with `--config`
    accept. A subcommand without `--config`, for example `dsml mcp`, gives all
    its options. A subcommand with actions, for example `dsml skills`, gives
    each action and its options.
    """
    parser = build_parser()
    subcommands = _subcommands(parser)
    names = sorted(subcommands)
    option_sets = {
        name: {_argument_name(action) for action in _arguments(subcommands[name][1])}
        for name in names
    }
    with_config = [name for name in names if "--config" in option_sets[name]]
    common: set[str] = set(option_sets[with_config[0]]) if with_config else set()
    for name in with_config[1:]:
        common &= option_sets[name]
    others = [name for name in names if not common <= option_sets[name]]
    sections: list[str] = []
    if common:
        first = _arguments(subcommands[with_config[0]][1])
        shared = sorted(
            (action for action in first if _argument_name(action) in common), key=_sort_key
        )
        text = "Each subcommand accepts these options"
        if others:
            text += ", except " + " and ".join(f"`{parser.prog} {name}`" for name in others)
        sections += ["## Common options", f"{text}.\n\n" + _argument_rows(shared)]
    for name in names:
        summary, sub = subcommands[name]
        skipped: set[str] = set() if name in others else common
        lines = [f"## `{parser.prog} {name}`", "", sub.description or summary]
        actions = _subcommands(sub)
        if not actions:
            lines += ["", _command_rows(sub, skipped)]
        for action in sorted(actions):
            action_summary, action_parser = actions[action]
            lines += [
                "",
                f"### `{parser.prog} {name} {action}`",
                "",
                action_parser.description or action_summary,
                "",
                _command_rows(action_parser, skipped),
            ]
        sections.append("\n".join(lines))
    introduction = "\n".join(
        [
            f"This part gives the subcommands of the command `{parser.prog}`, sorted by name.",
            f"Write the subcommand after `{parser.prog}`, then its arguments and options, "
            f"for example `{parser.prog} validate --format json`.",
        ]
    )
    return _document("DSML commands", introduction, sections)


# trace: PRD-AI-007, PRD-AI-015, PRD-CORE-028
def examples() -> str:
    """Give the `examples` part: the example models that the package contains."""
    names = {keyword.name for keyword in library_keywords()}
    sections: list[str] = []
    for target in sorted(starter.TARGETS):
        model = starter.starter_files(target)[starter.MODEL_FILE].decode("utf-8")
        used = sorted(set(re.findall(r"[#@](\w+)", model)) & names)
        lines = [
            f"## Starter model of the target `{target}`",
            "",
            f"`dsml init --target {target}` writes this model in `{starter.MODEL_FILE}`, "
            f"and the configuration file `{starter.CONFIG_FILE}`.",
            "",
            "Keywords: " + ", ".join(f"`{name}`" for name in used) + ".",
            "",
            "```sysml",
            model.rstrip("\n"),
            "```",
        ]
        sections.append("\n".join(lines))
    introduction = "\n".join(
        [
            "This part gives the example models that the toolchain package contains.",
            "Each model validates with no finding.",
        ]
    )
    return _document("DSML example models", introduction, sections)


PARTS: Final[Mapping[str, Callable[[], str]]] = {
    "commands": commands,
    "examples": examples,
    "keywords": keywords,
    "rules": rules,
}
"""The function of each part of the reference, by part name."""


# trace: PRD-AI-007
def part(name: str) -> str:
    """Give the text of one part of the reference."""
    if name not in PARTS:
        raise ValueError(
            f'The reference part "{name}" is unknown. The parts are: {", ".join(PARTS)}.'
        )
    return PARTS[name]()


# ----------------------------------------------------------------------
# Reference files of the skills
# ----------------------------------------------------------------------


def _listed_parts(parts_file: Path) -> list[str]:
    """Read the part names of a file `parts.txt`: one name on each line.

    The reader ignores empty lines and lines that start with "#".
    """
    names: list[str] = []
    for line in parts_file.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        if name not in PARTS:
            raise ValueError(
                f'The file {parts_file.name} lists the unknown part "{name}". '
                f"The parts are: {', '.join(PARTS)}."
            )
        names.append(name)
    return names


# trace: PRD-AI-007, PRD-CORE-028
def skill_reference_files(skills_folder: Path) -> dict[Path, bytes]:
    """Give the bytes of each reference file of the skills in `skills_folder`.

    Each folder `<skill>/references/` with the file `parts.txt` gets the file
    `<part>.md` for each part that `parts.txt` lists. If `skills_folder`
    does not exist, the result is empty.
    """
    files: dict[Path, bytes] = {}
    if not skills_folder.is_dir():
        return files
    for parts_file in sorted(skills_folder.glob(f"*/references/{PARTS_FILE}")):
        for name in _listed_parts(parts_file):
            files[parts_file.parent / f"{name}.md"] = part(name).encode("utf-8")
    return dict(sorted(files.items()))


# trace: PRD-AI-007
def stale_reference_files(skills_folder: Path) -> Iterator[Path]:
    """Give each reference file in `skills_folder` that is missing or not current."""
    for path, content in skill_reference_files(skills_folder).items():
        if not path.is_file() or path.read_bytes() != content:
            yield path
