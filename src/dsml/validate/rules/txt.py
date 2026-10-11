# trace: PRD-VAL-013, PRD-VAL-014, PRD-VAL-015
"""The rules of the category TXT: the text of needs and requirements.

The TXT rules are an optional rule set. They are off by default. The key
`rules.optional = ["TXT"]` of the configuration file turns them on
(PRD-VAL-013). The rules read the `doc` text of each need and requirement in
the IR.

- TXT-001: a sentence in the text of a need or requirement has more than 25
  words. A multi-word term of the project dictionary counts as one word
  (PRD-VAL-014).
- TXT-002: a requirement text uses "shall", "should", "may" or "will".
- TXT-003: a requirement text has more than one "must".

The rules ignore the text in `code` font, because a code name is permitted.
They do a small number of checks only. They do not make sure that a text
agrees with all rules of ASD-STE100 (Q3).
"""

import re
from collections.abc import Iterator
from functools import cache
from typing import Final

from dsml.config import Configuration
from dsml.ir.model import Element, Ir
from dsml.validate.dictionary import dictionary
from dsml.validate.rule import Hit, Rule, implements

MAX_WORDS: Final = 25
"""The maximum number of words in a sentence of a description (ASD-STE100)."""

FORBIDDEN_MODALS: Final = ("may", "shall", "should", "will")
"""The modal verbs that a requirement text must not use in place of "must"."""

_CODE: Final = re.compile(r"`[^`]*`")
_SENTENCE_END: Final = re.compile(r"(?<=[.!?])\s+")
_WORD: Final = re.compile(r"\S*\w\S*")
_MODAL: Final = re.compile(r"\b(?:may|shall|should|will)\b", re.IGNORECASE)
_MUST: Final = re.compile(r"\bmust\b", re.IGNORECASE)

# trace: PRD-VAL-013
TXT_001 = Rule(
    id="TXT-001",
    severity="warning",
    message="A sentence in the text of a need or requirement has more than 25 words.",
    fix_hint="Divide the sentence into sentences of 25 words or fewer.",
)

# trace: PRD-VAL-013
TXT_002 = Rule(
    id="TXT-002",
    severity="warning",
    message='A requirement text uses "shall", "should", "may" or "will" in place of "must".',
    fix_hint='Use "must" for an obligation. Use "can" for a possibility.',
)

# trace: PRD-VAL-013
TXT_003 = Rule(
    id="TXT-003",
    severity="warning",
    message=(
        'A requirement text has more than one "must", so it can contain more than one requirement.'
    ),
    fix_hint='Divide the text into requirements that each have one "must".',
)


@cache
def _terms() -> re.Pattern[str]:
    """Give the pattern of the multi-word terms of the project dictionary."""
    words = sorted(
        (term.word for term in dictionary() if " " in term.word),
        key=lambda word: (-len(word), word),
    )
    return re.compile(r"\b(?:" + "|".join(re.escape(word) for word in words) + r")\b", re.I)


def _plain(text: str) -> str:
    """Give the text with one space in place of each code span and each white space."""
    return " ".join(_CODE.sub(" CODE ", text).split())


# trace: PRD-VAL-014
def sentences(text: str) -> tuple[str, ...]:
    """Give the sentences of a text.

    A sentence ends with ".", "!" or "?" before a white space or the end of
    the text.
    """
    plain = _plain(text)
    return tuple(sentence for sentence in _SENTENCE_END.split(plain) if sentence)


# trace: PRD-VAL-014
def word_count(sentence: str) -> int:
    """Count the words of a sentence.

    A word has at least one letter or digit. A multi-word term of the project
    dictionary, for example "trace link", counts as one word (PRD-VAL-014).
    """
    return len(_WORD.findall(_terms().sub("TERM", sentence)))


def _texts(ir: Ir, kinds: frozenset[str]) -> Iterator[tuple[Element, str, str]]:
    """Give each element of the kinds that has a text, its label and its text."""
    for element in ir.elements:
        if element.kind in kinds and element.doc:
            label = element.short_name or element.name
            yield element, f'the {element.kind.lower()} "{label}"', element.doc


# trace: PRD-VAL-013, PRD-VAL-014
@implements(TXT_001)
def txt_001(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    for element, label, text in _texts(ir, frozenset({"Need", "Requirement"})):
        for number, sentence in enumerate(sentences(text), start=1):
            count = word_count(sentence)
            if count > MAX_WORDS:
                yield Hit(
                    f"The sentence {number} in the text of {label} has {count} words. "
                    f"The limit is {MAX_WORDS} words.",
                    element.location,
                    element.identity,
                )


# trace: PRD-VAL-013
@implements(TXT_002)
def txt_002(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    for element, label, text in _texts(ir, frozenset({"Requirement"})):
        found = sorted({word.lower() for word in _MODAL.findall(_plain(text))})
        if found:
            quoted = [f'"{word}"' for word in found]
            words = quoted[0] if len(quoted) == 1 else f"{', '.join(quoted[:-1])} and {quoted[-1]}"
            yield Hit(
                f'The text of {label} uses {words} in place of "must".',
                element.location,
                element.identity,
            )


# trace: PRD-VAL-013
@implements(TXT_003)
def txt_003(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    for element, label, text in _texts(ir, frozenset({"Requirement"})):
        count = len(_MUST.findall(_plain(text)))
        if count > 1:
            yield Hit(
                f'The text of {label} has {count} "must". It can contain more than one '
                "requirement.",
                element.location,
                element.identity,
            )


RULES = (txt_001, txt_002, txt_003)
"""The rules of this module."""
