# trace: PRD-CORE-021, PRD-CORE-022, PRD-CORE-024, PRD-CORE-025, PRD-TRACE-003
"""Convert a parsed model into the IR.

Each layer module gives the elements and the links of its layers. This
module puts them into one `Ir` with the SYN findings of the parse.
"""

from collections.abc import Sequence

from dsml.adapter import needs
from dsml.adapter.engine import ParsedModel
from dsml.adapter.findings import syn_findings
from dsml.adapter.source import SourceGraph
from dsml.ir.model import Element, Ir, Link


# trace: PRD-CORE-021, PRD-CORE-024, PRD-TRACE-003
def build_ir(model: ParsedModel, files: Sequence[str]) -> Ir:
    """Convert the model into the IR.

    `files` gives the names of the model files, relative to the repository
    root, as the parse got them. The DSML library is not a model file. If the
    parse gives an error, the IR holds only the files and the SYN findings,
    because the elements of the model are not complete.
    """
    findings = syn_findings(model.diagnostics)
    if any(item.severity == "error" for item in model.diagnostics):
        return Ir(files=tuple(sorted(files)), findings=findings)
    graph = SourceGraph(model.api_elements(), files)
    elements: list[Element] = list(needs.convert_elements(graph))
    links: list[Link] = list(needs.convert_links(graph))
    return Ir(
        files=tuple(sorted(files)),
        elements=tuple(elements),
        links=tuple(links),
        findings=findings,
    )
