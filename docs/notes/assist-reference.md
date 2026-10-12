# DSML reference for AI agents

Story #228 added the module `src/dsml/assist/reference.py`. It writes the DSML reference as Markdown from the installed toolchain. The skills and the MCP resources of milestone #226 use this text, so they agree with the installed version (PRD-AI-007, PRD-AI-015, Q68, Q69).

## Parts

The reference has four parts. Each part has one function and one golden file in `tests/golden/assist/`.

| Part | Function | Source | Contents |
| --- | --- | --- | --- |
| `keywords` | `keywords()` | `src/dsml/library/DSML.sysml` | Each keyword with its layer, its form, its attributes and its `doc` text. Then the enumerations and the attribute types of the library. |
| `rules` | `rules()` | The rule registry of `src/dsml/validate/rules/` | Each rule with its ID, severity, message and correction (the `fix_hint` of the rule). An optional rule also gives its rule set. |
| `commands` | `commands()` | `build_parser()` of `src/dsml/cli.py` | The common options, then each `dsml` subcommand with its arguments and options. |
| `examples` | `examples()` | The starter models of `src/dsml/starter/` | Each starter model with its target, its keywords and its text. |

`part(name)` gives the text of one part. `PARTS` lists the part names.

## Keywords

The module reads the library source as text. It does not import `opensysml`, because only the IR adapter can import it (PRD-CORE-020). The library uses a small set of SysML forms, so a small reader is sufficient:

- Each `metadata def` is a keyword. A keyword that specializes `SemanticMetadata` is an element kind. A different keyword is an annotation.
- The attributes of an element kind come from its base type in the package `BaseTypes`: the body of the usage, the definition of the usage and the general types of the definition.
- The attributes of an annotation come from the body of its metadata definition.
- The `doc` text is one line, with no comment marks.

The table `KEYWORD_LAYERS` gives the layer of each keyword. The library source does not give a layer for each keyword. `Waiver` and `DsmlVersion` are for all layers. If you add a keyword to the library, also add it to `KEYWORD_LAYERS`. If you do not add it, `keywords()` raises `ValueError` and the tests fail.

## Deterministic output

Two runs give byte-identical text (PRD-CORE-028 to PRD-CORE-038):

- The keywords are sorted by layer, then by name. The rules are sorted by rule ID. The subcommands are sorted by name. The options of a subcommand are sorted by name, after the positional arguments.
- The attributes of a keyword and the values of an enumeration stay in the order of the library, because this order has a meaning.
- The text is UTF-8, with LF line ends and one LF at the end.
- The text contains no time, no random value and no path of the installation. The keywords part gives the version of the DSML library.

The module does not use the network or an AI model (PRD-TOP-005).

## Reference files of the skills

Each skill folder `src/dsml/skills/<skill>/` can have the file `references/parts.txt`. This file lists one part name on each line. The reader ignores empty lines and lines that start with "#". For example, the modeling skill can list these parts:

```text
keywords
rules
examples
```

`skill_reference_files(folder)` gives the bytes of the file `references/<part>.md` for each listed part. A skill folder with no `parts.txt` gets no reference file. If the skills folder does not exist, the result is empty.

Thus a skill story adds only its own folder and its `parts.txt`. It does not change a shared list.

## Write the files

Run this script from the root of the repository after a change of the DSML library, the rule catalog or the CLI:

```shell
uv run python scripts/write_skill_references.py
```

The script writes the golden files in `tests/golden/assist/` and the reference files of each skill. Examine the differences with `git diff` before you commit them.

## Tests

`tests/test_assist_reference.py` makes sure of these items:

- Each part agrees with its golden file.
- Each keyword of the library is in the `keywords` part. Each rule of the catalog is in the `rules` part, with its severity, message and correction. Each subcommand of the parser is in the `commands` part.
- Two runs give the same bytes.
- Each reference file in `src/dsml/skills/` is current. The test fails if a reference file is missing or not current (PRD-AI-007).

A story that changes the library, a rule or the CLI also changes the golden files and the reference files. Run the script to write them again.
