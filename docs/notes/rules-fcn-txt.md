# Rules FCN and TXT (story #65)

Story #65 added the FCN rules and the optional TXT rules of the validator.

- FCN rules: `src/dsml/validate/rules/fcn.py`.
- TXT rules: `src/dsml/validate/rules/txt.py`.
- Project dictionary: `src/dsml/validate/dictionary.toml` and `src/dsml/validate/dictionary.py`.
- Tests: `tests/test_fcn_txt_rules.py`. Test models: `tests/models/rules/FCN-*/` and `tests/models/rules/TXT-*/`.

## FCN rules

The IR adapter writes the result of each formal constraint for each environment into the IR (PRD-CORE-054). `docs/notes/ir-constraints.md` gives the procedure. The FCN rules read these results from the IR only (PRD-VAL-012, PRD-CORE-026).

| Rule | Severity | Finding |
| --- | --- | --- |
| FCN-001 | error | One finding for each `false` result. |
| FCN-002 | warning | One finding for each `unknown` result. The message names the features that have no value. |

The location of a finding is the location of the constraint. The element of a finding is the requirement.

## TXT rules

The TXT rules are off by default. The key `rules.optional = ["TXT"]` turns them on (PRD-VAL-013). The rules read the `doc` text of the needs and the requirements. They ignore the text in `code` font.

| Rule | Text | Finding |
| --- | --- | --- |
| TXT-001 | Need and requirement | One finding for each sentence with more than 25 words. |
| TXT-002 | Requirement | One finding for each text that uses "shall", "should", "may" or "will". |
| TXT-003 | Requirement | One finding for each text with more than one "must". |

A sentence ends with ".", "!" or "?" before a white space or the end of the text. A word has at least one letter or digit.

## Project dictionary

`dictionary.toml` is a packaged copy of the project dictionary of the top-level PRD (PRD-VAL-014, Q2). A test makes sure that the copy agrees with the PRD. If you change the dictionary in the PRD, change the copy also.

TXT-001 counts a term of the dictionary with more than one word, for example "trace link", as one word.

The TXT rules do a small number of checks only. The messages do not tell that a text agrees with all rules of ASD-STE100 (Q3).
