# IR: results of the formal constraints (story #32)

Story #32 added the evaluation of the formal constraints of the requirements. The adapter evaluates each `require constraint` of each requirement one time for each environment, and writes each result into the IR (PRD-CORE-054, Q57). The validator reads the results from the IR and does not use OpenSysML (PRD-CORE-026). The rules FCN-001 and FCN-002 are in M4.

- Module: `src/dsml/adapter/constraints.py`. `build_ir` calls it after the layer converters.
- Engine: `ParsedModel.evaluate_formula()`, `ParsedModel.has_value()` and `ParsedModel.source_text()` in `src/dsml/adapter/engine.py`.
- Tests: `tests/test_constraints.py`. Test model: `tests/models/ir/constraints.sysml`.
- The form of a result in the IR: "Constraint results" in `docs/notes/ir.md`.

## Procedure of the adapter

For each requirement of kind `Requirement` and each environment, the adapter does these steps:

1. Find the `require constraint` items of the requirement in the order of the model. The index of the first item is 1. An `assume constraint` is not a formal constraint of the requirement, and it has no result.
2. Get the text of the expression from the model file. The API JSON form gives the start and the end of the constraint. The expression is the text between the first "{" and the last "}". The adapter removes the comments and a `doc` keyword.
3. Change the names of the AWS realizations that the environment overrides. See "Values of an environment".
4. Evaluate the expression with `Model.eval()` in the namespace of the requirement.
5. Write the result: `true`, `false` or `unknown`. For `unknown`, also write the features that have no value.

A model with no environment has no results. A constraint with no body, for example `require c;`, has no result, but it keeps its index.

## Values of an environment

An environment changes the attributes of an AWS realization with an `#Override` (PRD-DSML-042). OpenSysML 0.9.2 cannot evaluate an expression with the values of an override in place of the values of the realization. Thus the adapter changes the expression before the evaluation.

The adapter finds each feature chain in the expression, for example `dbAws.multiAz`. If the first part of the chain is the name or the qualified name of a realization that the environment overrides, the adapter puts the qualified name of the override in its place. The override subsets the realization, so it also gives the values that it does not change.

| Environment | Expression in the model | Expression that the adapter evaluates |
| --- | --- | --- |
| `dev` (no override) | `dbAws.multiAz == true` | `dbAws.multiAz == true` |
| `prod` | `dbAws.multiAz == true` | `Store::prod::dbProd.multiAz == true` |
| all | `prod.dbProd.multiAz == true` | No change. The chain names the environment, so the result is the same in each environment. |

A name after "." or "->" is not the first part of a chain. The adapter does not change a name in a string or in a comment.

Limit: the adapter compares names, not resolved elements. If a requirement has its own feature with the name of a realization, the adapter changes that name also. Do not give a feature in a requirement the name of an AWS realization.

## Features with no value

`Model.eval()` gives an `Undetermined` value for an expression that needs a feature with no value. Its reason names one feature only, for example `dbAws.instanceClass has multiplicity [0..1], which fixes no count`.

The IR needs all the features with no value. Thus, for an `unknown` result, the adapter evaluates each feature chain of the expression alone. Each chain that gives an `Undetermined` value goes into `missingFeatures`, as the model writes it. If no chain gives an `Undetermined` value, the adapter uses the feature in the reason of OpenSysML.

The logical operators of OpenSysML do not always need all their operands. For example, `false and x` gives `false` when `x` has no value. Thus a constraint can give `true` or `false` while a feature in it has no value.

## Feature chains in a constraint

A feature chain gets its members from the declared type or the subset of the first part, not from the keyword (see "Limits that change the DSML sketch" in `docs/notes/opensysml-0.9.2.md`). A realization gets its type from its keyword only. Thus a chain such as `dbAws.instanceClass` resolves only if the realization redefines the attribute in its body, for example `:>> instanceClass;` or `:>> multiAz default = false;`.

## Results of the example model

The example model has one formal constraint: `prod.orderDbProd.multiAz == true` in `orderDataSafe` (R-002). The IR holds three results, one for each of `dev`, `staging` and `prod`. Each result is `true`, because the chain names the `prod` environment.
