# trace: PRD-CORE-054, PRD-DSML-018, PRD-CORE-026
"""Evaluate the formal constraints of the requirements for each environment.

A requirement can contain formal constraints (`require constraint { ... }`,
PRD-DSML-018). The adapter evaluates each constraint one time for each
environment, with the attribute values of that environment, and writes each
result into the IR (PRD-CORE-054, Q57). Thus the validator reads the results
from the IR and does not use OpenSysML (PRD-CORE-026).

An environment changes the attributes of an AWS realization with an override
(PRD-DSML-042). OpenSysML 0.9.2 cannot evaluate an expression with the values
of an override in place of the values of the realization. Thus the adapter
changes the expression before the evaluation: a name of a feature chain that
refers to a realization changes to the qualified name of its override in the
environment. For example, in `prod`, `orderDbAws.multiAz` changes to
`OrderService::prod::orderDbProd.multiAz`. The override subsets the
realization, so it has the attributes that it does not change.

`docs/notes/ir-constraints.md` gives the full rules and the limits.
"""

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from dsml.adapter.engine import ParsedModel
from dsml.adapter.source import SourceElement, SourceGraph
from dsml.ir.model import ConstraintResult, Element, Location

# A name: a basic name or a name in single quotes.
_NAME = r"(?:[A-Za-z_][A-Za-z0-9_]*|'(?:[^'\\]|\\.)*')"

# The tokens of an expression. The order of the groups is important: a string
# or a comment can contain a text that looks like a name.
_TOKENS = re.compile(
    rf"""
    (?P<string>"(?:[^"\\]|\\.)*")
    | (?P<comment>//[^\n]*|/\*.*?\*/)
    | (?P<chain>{_NAME}(?:::{_NAME})*(?:\.{_NAME})*)
    | (?P<number>[0-9][0-9A-Za-z_.]*)
    | (?P<other>.)
    """,
    re.VERBOSE | re.DOTALL,
)

# The keywords of SysML v2 that can be in a Boolean expression. They are not
# feature chains.
_KEYWORDS = frozenset(
    {
        "and",
        "all",
        "as",
        "else",
        "false",
        "hastype",
        "if",
        "implies",
        "istype",
        "meta",
        "not",
        "null",
        "or",
        "then",
        "true",
        "xor",
    }
)

# The reason of an undetermined value starts with the feature, for example
# "dbAws.instanceClass has multiplicity [0..1], which fixes no count".
_REASON_FEATURE = re.compile(r"^(\S+) has ")


@dataclass(frozen=True, slots=True)
class _Chain:
    """One feature chain of an expression.

    `start` and `end` give the position of the chain in the expression.
    `head` is the part before the first ".", for example `orderDbAws` or
    `OrderService::orderDbAws`.
    """

    text: str
    start: int
    end: int

    @property
    def head(self) -> str:
        return self.text.split(".", 1)[0]


# trace: PRD-CORE-054
def evaluate_constraints(
    graph: SourceGraph, model: ParsedModel, elements: Sequence[Element]
) -> tuple[ConstraintResult, ...]:
    """Evaluate each formal constraint of each requirement in each environment.

    `elements` are the IR elements of the model. The function uses the
    requirements, the environments, the overrides and the AWS realizations.
    """
    environments = sorted(
        (element for element in elements if element.kind == "Environment"),
        key=Element.sort_key,
    )
    if not environments:
        return ()
    results: list[ConstraintResult] = []
    for requirement in sorted(elements, key=Element.sort_key):
        if requirement.kind != "Requirement":
            continue
        source = graph.find(requirement.qualified_name)
        if source is None:
            continue
        for index, constraint in enumerate(_required_constraints(source), start=1):
            location = constraint.location
            expression = _expression(constraint, model)
            if location is None or expression is None:
                continue
            for environment in environments:
                results.append(
                    _evaluate(
                        model,
                        requirement,
                        index,
                        environment,
                        expression,
                        location,
                        _substitutions(elements, environment),
                    )
                )
    return tuple(results)


def _required_constraints(requirement: SourceElement) -> Iterator[SourceElement]:
    """Give the `require constraint` items of a requirement, in the order of the model.

    An `assume constraint` is not a formal constraint of the requirement.
    """
    for relationship in requirement.relationships():
        if (
            relationship.metaclass == "RequirementConstraintMembership"
            and relationship.data.get("kind") == "requirement"
        ):
            yield from relationship.references("ownedConstraint")


def _expression(constraint: SourceElement, model: ParsedModel) -> str | None:
    """Give the text of the expression in the body of a constraint, or None.

    The API JSON form gives the start and the end of the constraint in its
    file. The expression is the text between the first "{" and the last "}".
    A constraint with no body, for example `require c;`, gives None.
    """
    file = constraint.file
    text = None if file is None else model.source_text(file)
    start_line = constraint.data.get("sysx:sourceLine")
    start_column = constraint.data.get("sysx:sourceColumn")
    end_line = constraint.data.get("sysx:sourceEndLine")
    end_column = constraint.data.get("sysx:sourceEndColumn")
    if (
        text is None
        or not isinstance(start_line, int)
        or not isinstance(start_column, int)
        or not isinstance(end_line, int)
        or not isinstance(end_column, int)
    ):
        return None
    lines = text.split("\n")[start_line - 1 : end_line]
    if not lines:
        return None
    lines[-1] = lines[-1][: max(end_column, 1)]
    lines[0] = lines[0][max(start_column - 1, 0) :]
    span = "\n".join(lines)
    opening = span.find("{")
    closing = span.rfind("}")
    if opening < 0 or closing <= opening:
        return None
    body = _without_comments(span[opening + 1 : closing]).strip()
    if body.startswith("doc") and not re.match(r"doc[A-Za-z0-9_]", body):
        body = body[len("doc") :].strip()
    return body or None


def _without_comments(expression: str) -> str:
    """Remove the comments of an expression, and keep the strings."""
    return "".join(
        " " if match.lastgroup == "comment" else match.group()
        for match in _TOKENS.finditer(expression)
    )


def _chains(expression: str) -> Iterator[_Chain]:
    """Give the feature chains of an expression, in their order.

    A name after "." or "->" is a part of the chain before it, not the start
    of a new chain. A keyword is not a chain.
    """
    for match in _TOKENS.finditer(expression):
        text = match.group()
        if match.lastgroup != "chain" or text in _KEYWORDS:
            continue
        if expression[: match.start()].rstrip().endswith((".", "->")):
            continue
        yield _Chain(text=text, start=match.start(), end=match.end())


def _substitutions(elements: Sequence[Element], environment: Element) -> Mapping[str, str]:
    """Give the names to change in an expression for one environment.

    The result maps the name and the qualified name of each AWS realization
    that the environment overrides to the qualified name of the override.
    """
    by_identity = {element.identity: element for element in elements}
    result: dict[str, str] = {}
    for override in sorted(elements, key=Element.sort_key):
        if override.kind != "Override" or override.owner != environment.identity:
            continue
        for identity in override.types:
            realization = by_identity.get(identity)
            if realization is None:
                continue
            result[realization.name] = override.qualified_name
            result[realization.qualified_name] = override.qualified_name
    return result


def _replace(expression: str, chains: Sequence[_Chain], substitutions: Mapping[str, str]) -> str:
    """Change the head of each chain that refers to an overridden realization."""
    parts: list[str] = []
    position = 0
    for chain in chains:
        parts.append(expression[position : chain.start])
        parts.append(_replace_chain(chain, substitutions))
        position = chain.end
    parts.append(expression[position:])
    return "".join(parts)


def _replace_chain(chain: _Chain, substitutions: Mapping[str, str]) -> str:
    replacement = substitutions.get(chain.head)
    if replacement is None:
        return chain.text
    return replacement + chain.text[len(chain.head) :]


# trace: PRD-CORE-054
def _evaluate(
    model: ParsedModel,
    requirement: Element,
    index: int,
    environment: Element,
    expression: str,
    location: Location,
    substitutions: Mapping[str, str],
) -> ConstraintResult:
    """Evaluate one constraint in one environment.

    The names of the expression resolve in the requirement. For an "unknown"
    result, the function finds each chain of the expression that has no
    value. The IR gives each chain as the model writes it.
    """
    chains = list(_chains(expression))
    namespace = requirement.qualified_name
    result = model.evaluate_formula(_replace(expression, chains, substitutions), namespace)
    missing: set[str] = set()
    if result.value == "unknown":
        for chain in chains:
            if model.has_value(_replace_chain(chain, substitutions), namespace) is False:
                missing.add(chain.text)
        if not missing:
            found = _REASON_FEATURE.match(result.detail)
            if found is not None:
                missing.add(found.group(1))
    return ConstraintResult(
        requirement=requirement.identity,
        index=index,
        environment=environment.identity,
        value=result.value,
        location=location,
        missing_features=tuple(sorted(missing)),
    )
