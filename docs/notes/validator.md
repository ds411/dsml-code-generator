# Validator

Story #57 added the rule interface, the rule registry, the rule engine and the subcommand `dsml validate`. The rules of the catalog, except the SYN rules, come in the stories of step 2 of milestone M4 (#6).

- Rule interface: `src/dsml/validate/rule.py`.
- Rule registry: `src/dsml/validate/rules/__init__.py`.
- Rule engine: `src/dsml/validate/engine.py`.
- Text and JSON reports: `src/dsml/validate/report.py`.
- Subcommand: `run_validate` in `src/dsml/cli.py`.
- Tests: `tests/test_validate.py`. The test helper `run_rule` is in `tests/conftest.py`.

## Rule interface

A rule is a Python function with its `Rule` metadata: the ID, the default severity, the message and the fix hint. The category comes from the ID (PRD-VAL-001, PRD-VAL-002). The function reads only the IR and the configuration (PRD-CORE-026). It gives one `Hit` for each problem:

```python
COV_003 = Rule(
    id="COV-003",
    severity="warning",
    message="A requirement with the status approved or later has no satisfying element.",
    fix_hint="Add a satisfy link from an element of the solution to the requirement.",
)


# trace: PRD-VAL-015
@implements(COV_003)
def cov_003(ir: Ir, configuration: Configuration) -> Iterator[Hit]:
    for element in ir.elements:
        if ...:
            yield Hit(f"The requirement {element.name} has no satisfying element.", element.location, element.identity)


RULES = (cov_003,)
```

- A hit gives a message, a location and an element identity. Each one is optional. A hit with no message gets the message of the rule.
- A hit has no severity. The engine gives the severity of the rule after the configuration overrides.
- A rule must not change the IR, and it must not use the network.

## Registry

Each module of `src/dsml/validate/rules/` holds rules of one category in the tuple `RULES`. The module name starts with the category in lower case, then optionally `_` and a topic, for example `cov.py` or `str_names.py`. The registry finds each module itself, so a new module needs no change in a different file. Thus the stories of step 2 do not change the same file. The three STR stories (#59, #60 and #61) can each add a module `str_<topic>.py`.

The registry stops with an error if two rules have the same ID, or if the category of a rule does not agree with the name of its module.

## Rule engine

1. The engine reads the keys `rules.severity` and `rules.optional` of the configuration (PRD-VAL-004, PRD-VAL-013). `docs/configuration.md` gives the rules. An error stops the command with exit code 2 before the toolchain reads the model.
2. The engine runs each enabled rule on the IR. If the IR has a SYN-001 finding, only the SYN rules run, because the elements of the IR are not complete.
3. The engine sorts the findings by file, line, column and rule ID (PRD-VAL-007). A finding with no location comes first.

## Baseline and IDN rules

Story #66 added the baseline module `src/dsml/baseline.py` and the IDN rules in `src/dsml/validate/rules/idn.py`.

- `--baseline <git-ref>` of `dsml validate` gives the baseline. If there is no `--baseline`, the key `trace.baseline` of `dsml.toml` gives it. If neither gives a baseline, the IDN rules do not run (PRD-VAL-011).
- The baseline module uses the local `git` command and no network (PRD-TOP-004). It copies the model files of `model.paths` at the baseline commit into a temporary folder. The IR adapter makes the IR of these files. Thus only the adapter imports OpenSysML.
- A Git reference that does not exist stops the command with exit code 2.
- `newest_release_tag()` gives the newest release tag `v*` before `HEAD` (Q54). A tag on `HEAD` is not before `HEAD`. The impact and suspect reports of M5 use it as the default baseline (PRD-TRACE-016).

A baseline rule uses the decorator `compares`, not `implements`. Its function also gets the IR of the baseline:

```python
@compares(IDN_002)
def idn_002(ir: Ir, baseline: Ir, configuration: Configuration) -> Iterator[Hit]: ...
```

The engine runs a baseline rule only when `Validator.run()` gets a baseline IR.

IDN-003 must find the baseline element of an element with no short name. The identity of this element is its qualified name, so the identity changed. The function `renamed()` makes a pair of a removed baseline element and an added element of the same kind. The pair must agree with one of these conditions, in this order:

1. The same name, and the owners are a pair or have the same identity. The element moved with its owner.
2. The owners are a pair or have the same identity, and the same contents. The element has a new name.
3. The same name and the same contents. The element moved to a different owner.

A condition makes a pair only if it gives exactly one candidate in each direction. Thus IDN-003 gives no finding when the pair is not clear.

The IR adapter makes the SYN findings from the OpenSysML diagnostics and writes them into the IR (PRD-CORE-021). The rules SYN-001 and SYN-002 in `syn.py` read these findings from the IR. Thus the configuration overrides apply to them, and they go into the same list as the findings of the other rules.

## Tests of a rule

Each rule has one model that it accepts and one model that it rejects (PRD-VAL-008). Put the models in `tests/models/rules/<rule>/`, for example `accept.sysml` and `reject.sysml`. The fixture `run_rule` parses one model with the DSML library, makes the IR and runs one rule. It turns on the optional rule set of the rule, for example TXT.

```python
def test_cov_003_accepts_its_accept_model(run_rule: RunRule) -> None:
    assert run_rule("COV-003", "accept.sysml") == ()
```

All rule tests share one OpenSysML service, the session fixture `rule_engine`.

An IDN rule also has the model `baseline.sysml`. The tests in `tests/test_baseline.py` commit it in a temporary Git repository. Then they compare `accept.sysml` and `reject.sysml` with it.
