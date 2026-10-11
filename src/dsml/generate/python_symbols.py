# trace: PRD-TRACE-006
"""The symbols of a generated Python file for the trace manifest.

The function `python_symbols` reads the text of a generated Python file
with the Python parser. It gives one symbol for each top-level class and
function. A function with a route decorator, for example
`@router.get("/healthz")`, also gives a route symbol, for example
`GET /healthz`. The line range of a symbol starts at its first decorator
and stops at its last line.
"""

import ast
from collections.abc import Mapping

from dsml.generate.trace import Symbol, SymbolKind

ROUTE_METHODS = frozenset({"delete", "get", "head", "options", "patch", "post", "put"})
"""The names of the route decorators of a FastAPI router."""


# trace: PRD-TRACE-006
def python_symbols(
    content: bytes,
    elements: tuple[str, ...],
    symbol_elements: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[Symbol, ...]:
    """Give the symbols of the top-level classes and functions of Python text.

    `elements` are the element identities of each symbol. `symbol_elements`
    gives other identities for the symbols with these names. The symbols are
    in the order of the file.
    """
    tree = ast.parse(content.decode("utf-8"))
    symbols: list[Symbol] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        first = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
        last = node.end_lineno if node.end_lineno is not None else node.lineno
        identities = (symbol_elements or {}).get(node.name, elements)
        for decorator in node.decorator_list:
            route = _route(decorator)
            if route is not None:
                symbols.append(Symbol(SymbolKind.ROUTE, route, first, last, identities))
        kind = SymbolKind.CLASS if isinstance(node, ast.ClassDef) else SymbolKind.FUNCTION
        symbols.append(Symbol(kind, node.name, first, last, identities))
    return tuple(symbols)


def _route(decorator: ast.expr) -> str | None:
    """Give the method and the path of a route decorator, or `None`."""
    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
        return None
    method = decorator.func.attr
    if method not in ROUTE_METHODS or not decorator.args:
        return None
    path = decorator.args[0]
    if not isinstance(path, ast.Constant) or not isinstance(path.value, str):
        return None
    return f"{method.upper()} {path.value}"
