# Reference

The reference pages give each DSML keyword, each validation rule and each `dsml` subcommand. Use them when you write a model, when you correct a finding, or when you type a command. The [concepts](../concepts.md) page and the [modeling tutorial](../modeling-tutorial.md) tell how these items work together.

## Pages

| Page | What it gives |
| --- | --- |
| [Keywords](keywords.md) | Each keyword of the DSML library, sorted by layer. Then the enumerations and the attribute types of the library. |
| [Rules](rules.md) | Each rule of the validation rule catalog, sorted by rule ID, with its severity, its message and its correction. |
| [Commands](commands.md) | The common options, then each `dsml` subcommand with its arguments and options. |

The toolchain writes these pages. The skills for AI agents and the MCP resources use the same text. Thus the pages always agree with the toolchain version of this guide. If your installed version is different, an AI agent with the skills gets the text of your version.

## Read a keyword entry

Each keyword entry has these items:

1. The heading: the name of the keyword, for example `Requirement`.
2. A short description. The description also tells the SysML item that the keyword is for, for example "Use it on a requirement usage".
3. The form of the keyword. The form is "element kind" or "annotation".
4. A table of the attributes, or the text "The keyword has no attributes".

An element kind tells what an element is. Write it with `#` before the declaration of the element, for example `#Requirement requirement <'R-001'> cancelOrder { ... }`.

An annotation adds data to an element. Write it with `#` before the declaration, as for an element kind. To give values to the attributes of an annotation, write it with `@` in the body of the element, for example `@FieldRules { maxLength = 40; }`.

The table of the attributes has these columns:

| Column | Meaning |
| --- | --- |
| Attribute | The name of the attribute. |
| Type | The type of the value. The section "Enumerations" gives the permitted values of an enumeration. The section "Attribute types" gives the types of the library, for example `Date`. |
| Multiplicity | The number of values. `1` tells that the attribute must have one value. `0..1` tells that a value is optional. `0..*` tells that the attribute can have zero or more values. |
| Default | The value that the toolchain uses if the model gives no value. An empty cell tells that no default value exists. |

Give the value of an attribute of an element kind with a redefinition in the body of the element, for example `:>> priority = Priority::must;`. Write the value of an enumeration with the name of the enumeration, `::` and the value.

## Read a rule entry

Each rule entry has these items:

- The rule ID, for example `COV-003`. The letters before the hyphen give the category of the rule.
- The severity: `error`, `warning` or `info`. An error stops `dsml generate`. The configuration file can change the severity of a rule.
- The message. A finding of the rule gives this message.
- The correction. It tells how to change the model, so that the rule finds no problem.
- For an optional rule only, the rule set. An optional rule set is off by default.

A finding of `dsml validate` gives the same rule ID, message and correction in its line `fix:`. The page [Reports](../reports.md) tells how to read a finding.

### Words and text in a correction

A correction tells you what to write in the model. It uses these forms:

| Form | Meaning |
| --- | --- |
| A word in angle brackets, for example `<need>` | Put a name of your model at this position. For example, `frame <need>;` becomes `frame fastCancel;` for the need `fastCancel`. |
| `frame <need>;` | Write this line in the body of a requirement. It tells which need the requirement comes from. |
| `satisfy <requirement> by <element>;` | Write this line in the application layer. It tells which element of the application satisfies the requirement. |
| `verify <requirement>;` | Write this line in the objective of a verification. It tells which requirement the verification examines. |
| `allocate <application> to <element>;` | Write this line in the infrastructure layer. It tells which logical element runs the application. |
| A keyword with `#`, for example `#Uses` or `#Realizes` | A DSML keyword. The [keywords](keywords.md) page gives it. A "`#Uses` dependency from A to B" is a line `#Uses dependency from a to b;` in the model. |
| A keyword with `@` and braces, for example `@Waiver { ... }` | An annotation with values for its attributes. Write it in the body of the element. |
| `:>> name = value;` | Give a value to an attribute of the element. |
| An attribute name, for example `multiAz` or `minCount` | An attribute of a DSML keyword. Set it with `:>>` in the body of the element. |
| A key of the configuration file, for example `aws.regions` | A key of `dsml.toml`. The page [Configuration file](../../configuration.md) gives all keys. |
| "The location of the finding" | The file, the line and the column that the finding gives. |

The [glossary](../glossary.md) gives the meaning of the other terms in a correction, for example "short name", "qualified name", "usage", "realization" and "waiver". A "part usage" is a usage of the form `part <name> : <definition>;` or `part <name> { ... }`.

If you cannot do the correction, and the model is correct for your project, you can add a waiver. The page [Reports](../reports.md) tells how.

## Read a command entry

The page starts with the common options. Each subcommand accepts the common options, except the subcommands that the page names.

Each subcommand has a heading, a short description and a table of its arguments and options:

| Column | Meaning |
| --- | --- |
| Argument | The name of the option, for example `--format`, or the name of a positional argument in angle brackets, for example `<model-file>`. |
| Value | The value of the option. "No value" tells that the option is a switch. A list tells the permitted values. "(zero or more)" tells that you can give the argument zero or more times. |
| Description | What the argument or option does, and its default value. |

A subcommand with actions, for example `dsml skills`, has one heading for each action, for example `dsml skills install`. Write the action after the subcommand.

## Write the pages again

The pages come from the script `scripts/write_guide_reference.py` in the toolchain repository. Do not change a page by hand. After a change of the DSML library, the rule catalog or the CLI, run this command from the root of the repository:

```shell
uv run python scripts/write_guide_reference.py
```

The test `tests/test_guide_reference.py` fails if a page is not current.
