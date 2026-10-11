# trace: PRD-VAL-001, PRD-VAL-003, PRD-VAL-004, PRD-VAL-006, PRD-VAL-007
"""The validator: the rule interface, the rule registry and the rule engine.

- `dsml.validate.rule`: the metadata and the function of one rule.
- `dsml.validate.rules`: the registry. It has one module for each category.
- `dsml.validate.engine`: runs the enabled rules on the IR.
- `dsml.validate.report`: writes the findings as text or as JSON.
- `dsml.validate.sarif`: writes the findings as SARIF 2.1.0.
"""
