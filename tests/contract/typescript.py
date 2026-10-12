"""Read one TypeScript expression of a generated file into a small syntax tree.

The reader knows only the expressions that the React generator writes in a
Zod schema and in a call of `apiRequest`: names, numbers, texts, template
texts, member access, calls, `new`, index access, objects and arrays. It
stops at the end of one expression, thus the text after the expression can
have other syntax. An unknown syntax gives a `ContractError`.
"""

import re
from dataclasses import dataclass
from typing import Final

from contract.shapes import ContractError

_TOKEN: Final = re.compile(
    r"""
    (?P<space>\s+|//[^\n]*|/\*.*?\*/)
    |(?P<name>[A-Za-z_$][\w$]*)
    |(?P<number>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
    |(?P<string>"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')
    |(?P<template>`(?:[^`\\]|\\.)*`)
    |(?P<punct>\.\.\.|\?\?|[()\[\]{},:.?;=<>!+\-*|&])
    """,
    re.VERBOSE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class Name:
    value: str


@dataclass(frozen=True, slots=True)
class Number:
    value: int | float


@dataclass(frozen=True, slots=True)
class Text:
    value: str


@dataclass(frozen=True, slots=True)
class Template:
    """A template text. `texts` has one more item than `values`."""

    texts: tuple[str, ...]
    values: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Member:
    target: Node
    name: str


@dataclass(frozen=True, slots=True)
class Index:
    target: Node
    index: Node


@dataclass(frozen=True, slots=True)
class Call:
    function: Node
    arguments: tuple[Node, ...]
    new: bool = False


@dataclass(frozen=True, slots=True)
class Object:
    """An object literal. A shorthand property has the value `Name(key)`."""

    items: tuple[tuple[str, Node], ...]

    def get(self, key: str) -> Node | None:
        return next((value for name, value in self.items if name == key), None)


@dataclass(frozen=True, slots=True)
class Array:
    items: tuple[Node, ...]


type Node = Name | Number | Text | Template | Member | Index | Call | Object | Array


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    start: int


class _Reader:
    """Read tokens from one position of a text, one at a time."""

    def __init__(self, text: str, position: int) -> None:
        self.text = text
        self.position = position
        self.token = self._read()

    def _read(self) -> _Token:
        while True:
            if self.position >= len(self.text):
                return _Token("end", "", self.position)
            match = _TOKEN.match(self.text, self.position)
            if match is None or match.lastgroup is None:
                snippet = self.text[self.position : self.position + 20]
                raise ContractError(f"The contract test cannot read the text {snippet!r}.")
            self.position = match.end()
            if match.lastgroup != "space":
                return _Token(match.lastgroup, match.group(), match.start())

    def next(self) -> _Token:
        token = self.token
        self.token = self._read()
        return token

    def expect(self, text: str) -> None:
        token = self.next()
        if token.text != text:
            raise ContractError(f"The contract test expects {text!r}, not {token.text!r}.")

    def accept(self, text: str) -> bool:
        if self.token.kind == "punct" and self.token.text == text:
            self.next()
            return True
        return False


def read_expression(text: str, position: int = 0) -> tuple[Node, int]:
    """Read one expression that starts at `position` of `text`.

    Give the syntax tree and the position after the last token of the
    expression.
    """
    reader = _Reader(text, position)
    node = _expression(reader)
    # The reader has read one token after the expression.
    return node, reader.token.start


def _expression(reader: _Reader) -> Node:
    node = _primary(reader)
    while True:
        if reader.accept("."):
            node = Member(node, _name(reader))
        elif reader.accept("("):
            node = Call(node, _list(reader, ")"))
        elif reader.accept("["):
            node = Index(node, _expression(reader))
            reader.expect("]")
        elif reader.token.kind == "name" and reader.token.text == "as":
            reader.next()
            _name(reader)
        else:
            return node


def _primary(reader: _Reader) -> Node:
    token = reader.next()
    if token.kind == "name" and token.text == "new":
        function = _primary(reader)
        while reader.accept("."):
            function = Member(function, _name(reader))
        reader.expect("(")
        return Call(function, _list(reader, ")"), new=True)
    if token.kind == "name":
        return Name(token.text)
    if token.kind == "number":
        return Number(_number(token.text))
    if token.kind == "punct" and token.text == "-" and reader.token.kind == "number":
        return Number(-_number(reader.next().text))
    if token.kind == "string":
        return Text(_unquote(token.text))
    if token.kind == "template":
        return _template(token.text[1:-1])
    if token.kind == "punct" and token.text == "(":
        node = _expression(reader)
        reader.expect(")")
        return node
    if token.kind == "punct" and token.text == "[":
        return Array(_list(reader, "]"))
    if token.kind == "punct" and token.text == "{":
        return _object(reader)
    raise ContractError(f"The contract test cannot read an expression at {token.text!r}.")


def _name(reader: _Reader) -> str:
    token = reader.next()
    if token.kind != "name":
        raise ContractError(f"The contract test expects a name, not {token.text!r}.")
    return token.text


def _list(reader: _Reader, close: str) -> tuple[Node, ...]:
    items: list[Node] = []
    while not reader.accept(close):
        items.append(_expression(reader))
        if not reader.accept(","):
            reader.expect(close)
            break
    return tuple(items)


def _object(reader: _Reader) -> Object:
    items: list[tuple[str, Node]] = []
    while not reader.accept("}"):
        token = reader.next()
        if token.kind == "name":
            key = token.text
        elif token.kind == "string":
            key = _unquote(token.text)
        else:
            raise ContractError(f"The contract test cannot read the object key {token.text!r}.")
        value: Node = _expression(reader) if reader.accept(":") else Name(key)
        items.append((key, value))
        if not reader.accept(","):
            reader.expect("}")
            break
    return Object(tuple(items))


def _template(body: str) -> Template:
    texts: list[str] = []
    values: list[Node] = []
    position = 0
    while (start := body.find("${", position)) >= 0:
        texts.append(body[position:start])
        node, end = read_expression(body, start + 2)
        if not body.startswith("}", end):
            raise ContractError(f"The contract test cannot read the template text {body!r}.")
        values.append(node)
        position = end + 1
    texts.append(body[position:])
    return Template(tuple(texts), tuple(values))


def _number(text: str) -> int | float:
    if text.isdigit():
        return int(text)
    return float(text)


def _unquote(text: str) -> str:
    body = text[1:-1]
    return re.sub(r"\\(.)", lambda match: match.group(1), body)
