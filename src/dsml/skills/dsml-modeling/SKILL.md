---
name: dsml-modeling
description: Write or change a DSML model in SysML v2 from a short description of a product. Use this skill when the user asks for a DSML model, or for needs, requirements, an application, infrastructure or verifications in a .sysml file of a dsml project.
---

# Write a DSML model

This skill tells you how to write a DSML model from a short description of a product. A DSML model is SysML v2 text with the keywords of the DSML library. The model has five layers: needs, requirements, application, infrastructure and verification. The `dsml` toolchain validates the model and generates code from it.

Your model is complete when `dsml validate` finds no error.

## Reference files

Read these files when you need them. Do not read all files at the start.

| File | Contents |
| --- | --- |
| `references/patterns.md` | A short model pattern for each layer. Start here. |
| `references/keywords.md` | Each DSML keyword with its layer, its form and its attributes. Also the enumerations. |
| `references/rules.md` | Each validation rule with its ID, severity, message and correction. |
| `references/examples.md` | The starter models that `dsml init` writes. |

The toolchain writes `keywords.md`, `rules.md` and `examples.md` from the installed version. Thus these files agree with the `dsml` command of the project.

## Rules for the model

- Put the model in the `.sysml` files that the key `model.paths` of `dsml.toml` gives. A new project from `dsml init` uses `model/model.sysml`.
- Start each model file with `private import DSML::*;`. Add `private import ScalarValues::*;` if the model uses `String`, `Integer`, `Boolean` or `Real`.
- Put `@DsmlVersion { major = 1; minor = 1; }` on the root package. Use the version in `references/keywords.md`.
- Give each need, requirement and verification a short name, for example `<'N-001'>`, `<'R-001'>` and `<'V-001'>`. Do not use a short name two times.
- Use the attribute values of the DSML enumerations, for example `Priority::must` and `Status::draft`.
- Use `Status::draft` for a new need or requirement. The user changes the status to `approved`.
- Use only the names of elements that the model declares. Do not make up keywords or attributes.

## Write the model text in ASD-STE100

Write all `doc` text and all titles in ASD-STE100 Simplified Technical English, Issue 9:

- Write sentences of 25 words or fewer (TXT-001).
- Use "must" for an obligation. Do not use "shall", "should", "may" or "will" (TXT-002).
- Write one "must" in each requirement text (TXT-003). Divide a text with two obligations into two requirements.
- Use the active voice and simple verb tenses.

## Procedure

Do these steps in their order. After each step, the model must parse with no syntax error.

1. Find the stakeholders and the needs.
   - Read the description of the product. Find the persons and the organizations that have an interest in the product.
   - Write one `#Stakeholder part def` for each stakeholder.
   - Write one `#Need concern` for each need. Link it to its stakeholder with `stakeholder <name> : <Stakeholder>;`.
2. Write the requirements and link them to the needs.
   - Write one `#Requirement requirement` for each function, quality or constraint of the product.
   - Link each requirement to a need with `frame <need>;`, or derive it from a different requirement with a `#derivation` connection.
   - Select the kind: `functional`, `performance`, `security`, `'interface'` or `'constraint'`.
3. Model the application layer: entities, operations, views and roles.
   - Write one `#Roles enum def` with the roles of the users.
   - Write one `#Entity part def` for each type of data. Give one field the `#Key` metadata. Use `@FieldRules` for the constraints of a field.
   - Write one `#Operation action def` for each action that is not create, read, update, delete or list. Give it a method and a path.
   - Write one `#Application part` for each application. Set the target, for example `Target::fastapi`.
   - Expose the entities and the operations with `#Exposed`. Give `allowedRoles`, or set `public = true`.
   - For a `react` or `nextjs` application, write the `#View` parts and the navigation.
   - Link each requirement to the application with `satisfy <requirement> by <application>;`.
4. Model the logical infrastructure and its AWS realizations.
   - Write the logical elements: `#Network`, `#ContainerService`, `#RelationalDatabase`, `#UserDirectory` and, if necessary, `#SecretStore` or `#StaticSite`.
   - Allocate each application to its service or site with `allocate`.
   - Link each service to its database and user directory with a `#Uses` dependency.
   - Write one AWS realization for each logical element, and a `#Realizes` dependency from the realization to the logical element.
   - Write the `#ToolingAccount` and the environments `dev`, `staging` and `prod`. If you do not know the account IDs, use the example values of the patterns and tell the user.
   - Write an `#Override` part in an environment to change an AWS attribute for that environment only.
5. Write the verifications.
   - Write one `#Verification verification` for each requirement. Link it with `objective { verify <requirement>; }`.
   - Select the method: `test`, `'analysis'`, `inspection` or `demonstration`.
   - For the method `test`, give the test files in `testFiles` only if they exist.
6. Run `dsml validate --format json`. Correct each error finding, then run it again.
   - Each finding has the keys `rule`, `severity`, `message`, `location` and `fixHint`.
   - Do the correction in `fixHint`. `references/rules.md` gives more data about each rule.
   - Correct the findings in the order of the output. A syntax error (`SYN-001`) can cause other findings.
   - Run the command again until the summary gives 0 errors.
   - Then examine the warnings. Correct a warning if the correction is clear. Tell the user about the other warnings.

## When you complete the model

Tell the user these items:

- The stakeholders, needs and requirements that you found in the description.
- The values that you did not know, for example account IDs, Regions and domains.
- The result of the last `dsml validate`, with the remaining warnings.

The CLI skill `dsml-cli` tells you how to generate code from the model after validation.
