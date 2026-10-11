# trace: PRD-VAL-014
"""The project dictionary that the text rules use.

The file `dictionary.toml` is a packaged copy of the project dictionary of the
top-level PRD. The text rules use its terms as additional approved words
(PRD-VAL-014, Q2). A term can have more than one word, for example "trace
link". The rule TXT-001 counts such a term as one word.

The text rules do a small number of checks only. They do not make sure that a
text agrees with all rules of ASD-STE100.
"""

import tomllib
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Final, Literal

DICTIONARY_FILE: Final = "dictionary.toml"
"""The name of the packaged copy of the project dictionary."""


# trace: PRD-VAL-014
@dataclass(frozen=True, slots=True)
class Term:
    """One term of the project dictionary: a technical noun or a technical verb."""

    word: str
    type: Literal["noun", "verb"]


# trace: PRD-VAL-014
def load_dictionary(text: str | None = None) -> tuple[Term, ...]:
    """Give the terms of the project dictionary, in the order of the file.

    Without `text`, the function reads the `dictionary.toml` file of the package.
    """
    if text is None:
        text = (
            resources.files("dsml.validate").joinpath(DICTIONARY_FILE).read_text(encoding="utf-8")
        )
    terms: list[Term] = []
    for item in tomllib.loads(text).get("term", []):
        kind = item["type"]
        if kind not in ("noun", "verb"):
            raise ValueError(f'The term "{item["word"]}" has the type "{kind}".')
        terms.append(Term(word=item["word"], type=kind))
    return tuple(terms)


@cache
def dictionary() -> tuple[Term, ...]:
    """Give the terms of the packaged project dictionary."""
    return load_dictionary()
