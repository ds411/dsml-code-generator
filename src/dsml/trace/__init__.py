# trace: PRD-CORE-026, PRD-TRACE-004
"""The traceability engine.

The engine reads only the IR (PRD-CORE-026). It does not import OpenSysML or
the IR adapter.

- `dsml.trace.comments`: the trace comments in the hand-written files.
- `dsml.trace.graph`: the link graph and its queries in the two directions.
- `dsml.trace.hashes`: the hash of the IR form of an element.
"""

from dsml.trace.graph import TRACE_LINK_TYPES, LinkGraph
from dsml.trace.hashes import element_hash, element_hashes

__all__ = ["TRACE_LINK_TYPES", "LinkGraph", "element_hash", "element_hashes"]
