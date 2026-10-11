# trace: PRD-CORE-026, PRD-TRACE-004
"""The traceability engine.

The engine reads only the IR (PRD-CORE-026). It does not import OpenSysML or
the IR adapter.

- `dsml.trace.changes`: the changed elements, the impact report and the
  suspect report.
- `dsml.trace.comments`: the trace comments in the hand-written files.
- `dsml.trace.commit`: the model commit of the reports.
- `dsml.trace.graph`: the link graph and its queries in the two directions.
- `dsml.trace.hashes`: the hash of the IR form of an element.
- `dsml.trace.report`: the report model and its JSON and CSV writers.
- `dsml.trace.reports`: the coverage report and the orphans report.
"""

from dsml.trace.graph import TRACE_LINK_TYPES, LinkGraph
from dsml.trace.hashes import element_hash, element_hashes

__all__ = ["TRACE_LINK_TYPES", "LinkGraph", "element_hash", "element_hashes"]
