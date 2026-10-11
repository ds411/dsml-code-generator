# trace: PRD-CORE-022, PRD-CORE-025, PRD-CORE-026
"""The intermediate representation (IR) of a model.

The IR adapter (`dsml.adapter`) converts a model into the IR. Validators and
generators read only the IR. This package does not import OpenSysML, and the
IR holds no OpenSysML type, object or internal ID.

- `dsml.ir.model`: the typed IR models.
- `dsml.ir.writer`: the canonical JSON writer.
- `dsml.ir.schema`: the JSON Schema of the IR, as package data.
"""

from dsml.ir.model import IR_VERSION

__all__ = ["IR_VERSION"]
