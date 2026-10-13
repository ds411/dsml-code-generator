# Reports

This page tells how to read the findings of `dsml validate` and the trace reports of the subcommand `trace`. It also tells how to connect hand-written code to the model. The [concepts](concepts.md) page gives the meaning of a finding, a waiver and a trace link. The examples come from the golden files of this repository and from the model on this page.

## Findings

`dsml validate` examines the model with the validation rules. `dsml generate` does the same examination first. A finding is one result of one rule. Each finding has these parts:

| Part | Meaning |
| --- | --- |
| Location | The model file, the line and the column of the element. |
| Severity | `error`, `warning` or `info`. An error finding stops `dsml generate`. |
| Rule | The ID of the rule, for example `COV-006`. The first part is the category. The [reference](reference/README.md) gives each rule. |
| Element | The ID or the qualified name of the element, for example `R-001`. |
| Message | What is wrong. |
| Fix hint | What to do to correct it. |

The validator sorts the findings by file, line, column and rule ID. Thus the same model always gives the same report.

The option `--format` selects one of three formats. Each format has the same findings.

| Format | Command | Use |
| --- | --- | --- |
| Text | `dsml validate` | A person reads it in a terminal. |
| JSON | `dsml validate --format json` | A script reads it. |
| SARIF | `dsml validate --format sarif` | A code review tool reads it, for example GitHub code scanning. |

### Text format

Each finding has one line, then one line with the fix hint. The last line gives the number of findings of each severity. This report comes from the golden file `tests/golden/validate/order-service.findings.txt`:

```text
docs/model/examples/order-service.sysml:103:9: warning: COV-006: The verification V-001 refers to the test file "app/features/order/read_order/test_endpoint.py". This file does not exist.
  fix: Correct the path in `testFiles`, or add the test file. The path is relative to the folder of the configuration file.
Findings: 0 errors, 1 warning, 0 info.
```

Read the first line from left to right: the file, the line 103, the column 9, the severity, the rule and the message.

### JSON format

The JSON object has three keys:

- `findings`: the list of the findings.
- `waived`: the list of the waived findings. Each waived finding also has its waiver.
- `summary`: the number of findings of each severity, and the number of waived findings.

This part comes from the golden file `tests/golden/validate/order-service.findings.json`:

```json
{
  "findings": [
    {
      "element": "V-001",
      "fixHint": "Correct the path in `testFiles`, or add the test file. The path is relative to the folder of the configuration file.",
      "location": {
        "column": 9,
        "file": "docs/model/examples/order-service.sysml",
        "line": 103
      },
      "message": "The verification V-001 refers to the test file \"app/features/order/read_order/test_endpoint.py\". This file does not exist.",
      "rule": "COV-006",
      "severity": "warning"
    }
  ],
  "summary": {
    "error": 0,
    "info": 0,
    "waived": 0,
    "warning": 1
  },
  "waived": []
}
```

### SARIF format

SARIF 2.1.0 is a standard JSON format for the results of analysis tools. The SARIF file has the metadata of each rule: the ID, the default severity, the short description and the fix hint. Each finding is a `result` with a `ruleId`, a `level` and a location.

The generated pipeline `pr.gen.yml` uploads the SARIF file to GitHub code scanning. Then GitHub shows each finding on the line of the model file in the pull request.

### Exit code

| Result | Exit code |
| --- | --- |
| No error finding | 0 |
| One or more error findings | 1 |
| A usage error or an internal error | 2 |

With `dsml validate --fail-on warning`, a warning also gives the exit code 1. The configuration file can increase the severity of a rule, or turn off a rule with the default severity `warning` or `info`. The [configuration file](../configuration.md) page gives the key `rules.severity`.

## Waivers

A waiver stops one rule for one element. Use a waiver only when you know the cause of a finding and accept it for a time. To add a waiver, write `@Waiver` in the body of the element. Give these attributes:

- `rule`: the ID of the rule.
- `reason`: why the finding is acceptable.
- `owner`: the person or the team that is responsible for the waiver.
- `expires` (optional): the date when the waiver stops, in the form `YYYY-MM-DD`.

In this model, the requirement R-001 has no satisfying element yet. The waiver stops the rule COV-003 for R-001:

```sysml
package Tasks {
    private import DSML::*;
    @DsmlVersion { major = 1; minor = 0; }

    #Stakeholder part def TeamLead;

    #Need concern <'N-001'> seeOpenTasks {
        doc /* The team lead must see the open tasks of the team. */
        :>> title = "See open tasks";
        :>> priority = Priority::must;
        :>> status = Status::approved;
        subject;
        stakeholder lead : TeamLead;
    }

    #Requirement requirement <'R-001'> listTasks {
        doc /* The API must return a list of the tasks. */
        :>> title = "List tasks";
        :>> kind = RequirementKind::functional;
        :>> priority = Priority::must;
        :>> status = Status::approved;
        frame seeOpenTasks;
        @Waiver {
            rule = "COV-003";
            reason = "The API comes in the next release.";
            owner = "Task team";
            expires = "2027-06-30";
        }
    }
}
```

If the model file is `model/tasks.sysml`, `dsml validate` writes this report:

```text
model/tasks.sysml:16:5: warning: COV-004: The requirement R-001 has the status "approved" but no verification.
  fix: Add a verification with `verify <requirement>;` in its objective.
Findings: 0 errors, 1 warning, 0 info.
Waived findings: 1.
model/tasks.sysml:16:5: warning: COV-003: The requirement R-001 has the status "approved" but no satisfying element.
  waiver: The API comes in the next release. (owner: Task team, expires 2027-06-30)
```

The waived finding stays visible in a separate group. The waiver does not stop COV-004, because it names only COV-003. In the JSON format, the waived finding is in the list `waived`, with the key `waiver`. In the SARIF format, the waived finding has a `suppressions` item with the reason as the `justification`.

These rules apply to waivers:

- After the `expires` date, the finding comes back, and the rule STR-014 reports the expired waiver. Remove the waiver, or give it a new date.
- The rule STR-015 reports a waiver with no reason, no owner, or an unknown rule. A waiver cannot stop STR-014 or STR-015.
- The validator does not read the clock. The date of the expiry check is the commit date of `HEAD`. The option `--date` gives a different date, for example `dsml validate --date 2026-10-13`.

## Trace reports

The subcommand `trace` writes one of four reports. Give the name of the report after `trace`:

```shell
dsml trace coverage
dsml trace orphans --format csv
dsml trace impact --baseline v1.0.0 --format json
dsml trace suspect --output suspect.html
```

Each report is available in three formats. The option `--format` selects the format:

- `html` (the default): one file with no external resources. Open it in a web browser.
- `csv`: one row for each item. The first three lines start with `#` and give the report name, the model commit and the baseline commit.
- `json`: the same data as an object with the keys `report`, `modelCommit`, `baselineCommit`, `columns` and `rows`.

Each report gives the Git commit of the model, and no date or time. If the model is not in a Git repository, the value of the model commit starts with `none`.

### The report `coverage`

The coverage report answers the question "Is each requirement covered?". It has one row for each requirement. This part comes from the golden file `tests/golden/trace/order-service.coverage.csv`:

```text
requirement,needs,satisfiedBy,generatedFiles,traceComments,verifications,status
R-001,N-001,OrderService::orderApi,,app/features/order/read_order/test_endpoint.py:1,V-001,verified
R-002,N-001,OrderService::prod::orderDbProd,,,V-002,verified
```

| Column | Meaning |
| --- | --- |
| `requirement` | The ID of the requirement. |
| `needs` | The needs that the requirement frames. |
| `satisfiedBy` | The elements that satisfy the requirement. |
| `generatedFiles` | The generated files of the satisfying elements. |
| `traceComments` | The trace comments in hand-written code that name the requirement, with the file and the line. |
| `verifications` | The verifications of the requirement. |
| `status` | The coverage status. |

| Status | Meaning | The work to do |
| --- | --- | --- |
| `missing` | No element satisfies the requirement. | Add the application or infrastructure element, and connect it with `satisfy`. If the work comes in a later release, add a waiver for COV-003. |
| `satisfied` | An element satisfies the requirement, but no verification verifies it. | Add a verification with `verify`. For a test, write the test and give its file in `testFiles`. |
| `verified` | An element satisfies the requirement, and a verification verifies it. | No work. Examine the row again when the requirement changes. |

### The report `orphans`

The orphans report answers the question "What has no link?". It has one row for each item, with its category and its location. This part comes from the golden file `tests/golden/trace/order-service.orphans.csv`:

```text
category,item,location
element-without-requirement,OrderService::CancelOrder,model/order-service.sysml:49
element-without-requirement,OrderService::Order,model/order-service.sysml:42
```

| Category | Meaning | The work to do |
| --- | --- | --- |
| `need-without-requirement` | No requirement frames the need. | Write a requirement that frames the need, or remove the need. |
| `requirement-without-need` | The requirement frames no need. | Connect the requirement to its need with `frame`, or derive it from a different requirement. |
| `element-without-requirement` | The element satisfies no requirement. | Connect the element to its requirement with `satisfy`. An element that only supports other elements can stay in this list, for example a network. |
| `unknown-trace-id` | A trace comment names an ID that is not in the model. | Correct the ID in the comment, or add the element to the model. |
| `test-file-without-verification` | No verification gives this test file in `testFiles`. | Add the file to the `testFiles` of its verification, or add a verification. |

### The report `impact`

The impact report answers the question "What does a change affect?". It compares the model with a baseline: an earlier Git commit of the model. It has one row for each element that changed after the baseline. This part comes from the golden file `tests/golden/trace/order-service.impact.csv`:

```text
element,change,needs,requirements,verifications,generatedFiles,hclAddresses
R-001,changed,N-001,R-001,V-001,app/main_gen.py; infra/envs/prod/main.gen.tf,aws_ecs_service.api_service
```

The column `change` is `added`, `changed` or `removed`. The other columns give the affected needs, requirements, verifications, generated files and HCL resource addresses. An HCL address names one AWS resource in the infrastructure code.

Use the report before a release, or in the review of a pull request:

1. Examine each affected requirement. Make sure that it is still correct.
2. Run the affected verifications again.
3. Examine the changes of the affected generated files in Git.
4. Examine the `tofu plan` of the affected HCL addresses before you apply it.

### The report `suspect`

The suspect report answers the question "Which links need a review?". A link is suspect if one of its ends changed after the baseline. For example, if a requirement changed, its `satisfy` link is suspect: the element possibly does not satisfy the new text. This part comes from the golden file `tests/golden/trace/order-service.suspect.csv`:

```text
linkType,source,target,changedEnds,changedElements
frame,R-001,N-001,source,R-001
verify,V-001,R-001,target,R-001
```

The column `changedEnds` tells which end of the link changed: `source`, `target` or the two. The column `changedElements` gives the elements that changed.

For each row, examine the two ends of the link. Make sure that the link is still true. If it is not true, change the model. When the review is complete, move the baseline.

### The baseline

The reports `impact` and `suspect` compare the model with a baseline. The baseline is a Git reference, for example a tag or a commit:

1. The option `--baseline`, for example `dsml trace impact --baseline v1.0.0`.
2. If there is no option, the key `trace.baseline` of the configuration file.
3. If there is no key, the newest release tag `v*` before `HEAD`.

An element counts as changed if its content in the IR is different from its content in the baseline. A change of only the line or the column of the element does not count.

## Trace comments in hand-written code

A trace comment connects hand-written code to a model element. Write the comment on the line before a function or a class. The comment applies to the next symbol in the file. If no symbol follows, it applies to the file.

The form is `trace:` and one or more IDs, separated by commas. An ID is the short name of a need, a requirement or a verification, or the qualified name of a different element.

| Language | Example |
| --- | --- |
| Python | `# trace: R-001, V-001` |
| TypeScript | `// trace: R-001` |
| HCL | `# trace: R-002` |
| YAML | `# trace: R-001` |

The create-once file `handler.py` of a custom operation already has a trace comment. This part comes from the golden file `app/features/order/cancel_order/handler.py` of the order service:

```python
# trace: OrderService::CancelOrder
async def handle(data: CancelOrderInput, session: AsyncSession, user: User) -> CancelOrderOutput:
```

Add the IDs of the requirements that your logic implements, for example `# trace: OrderService::CancelOrder, R-001`.

The toolchain reads trace comments in the hand-written files of the output folders, and in the test folders of the key `trace.tests`. It does not read trace comments in generated files. The coverage report shows each trace comment in the column `traceComments`. The orphans report shows each trace comment with an unknown ID.

## The trace manifest

The generator writes the trace manifest `.dsml/trace.gen.json` beside the configuration file. It gives, for each model element, each generated file and each symbol in that file. A symbol is a class, a function, a route, an HCL resource or a workflow job. Each symbol has its first line and its last line. This part comes from the golden file `tests/golden/fastapi/order-service/.dsml/trace.gen.json`:

```json
{
  "element": "OrderService::CancelOrder",
  "files": [
    {
      "path": "services/order-api/app/features/order/cancel_order/endpoint_gen.py",
      "symbols": [
        {
          "firstLine": 33,
          "kind": "function",
          "lastLine": 41,
          "name": "cancel_order"
        },
        {
          "firstLine": 33,
          "kind": "route",
          "lastLine": 41,
          "name": "POST /orders/{orderId}/cancel"
        }
      ]
    },
```

Use the trace manifest to find the code of an element:

- To find the code of a model element, look for its identity in the key `element`.
- To find the model element of an AWS resource, read its tag `dsml:element`. Then look for the HCL address of the resource in the manifest.
- To find the model elements of a generated file, read the line `Elements:` in the header of the file.

The trace manifest is a generated file. Commit it with the code, and do not change it. The reports read it, so they can give the generated files and the HCL addresses of each element.

## Next steps

- Read the [generated code](generated-code.md) page to see where the generator writes each file.
- Read the [reference](reference/README.md) for each validation rule.
- Read about the [configuration file](../configuration.md).
