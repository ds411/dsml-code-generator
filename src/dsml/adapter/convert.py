# trace: PRD-CORE-021, PRD-CORE-022, PRD-CORE-024, PRD-CORE-025, PRD-CORE-054, PRD-TRACE-003
"""Convert a parsed model into the IR.

Each layer module gives the elements and the links of its layers. This
module puts them into one `Ir` with the results of the formal constraints
and the SYN findings of the parse.
"""

from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from dsml.adapter import constraints, needs, solution
from dsml.adapter.engine import Engine, ParsedModel
from dsml.adapter.findings import syn_findings
from dsml.adapter.source import SourceGraph
from dsml.errors import ToolchainError
from dsml.ir.model import Element, Ir, Link
from dsml.library import library_document


# trace: PRD-CORE-021, PRD-CORE-024, PRD-CORE-054, PRD-TRACE-003
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
    elements: list[Element] = [
        *needs.convert_elements(graph),
        *solution.convert_elements(graph, model),
    ]
    links: list[Link] = [*needs.convert_links(graph), *solution.convert_links(graph)]
    return Ir(
        files=tuple(sorted(files)),
        elements=tuple(elements),
        links=tuple(links),
        constraint_results=constraints.evaluate_constraints(graph, model, elements),
        findings=findings,
    )


# trace: PRD-CORE-001, PRD-CORE-020, PRD-CORE-033
def make_ir(paths: Sequence[Path], root: Path) -> Ir:
    """Parse the model files with the DSML library and convert them into the IR.

    The IR gives each file name relative to `root`, with "/" as the separator,
    so the IR does not contain an absolute path (PRD-CORE-033). A file must be
    in `root`. The function starts and stops one OpenSysML service.
    """
    documents = sorted({_document(path, root) for path in paths})
    with Engine() as engine:
        model = engine.parse_texts([library_document(), *documents])
        return build_ir(model, [name for name, _ in documents])


def _document(path: Path, root: Path) -> tuple[str, str]:
    try:
        name = PurePosixPath(path.resolve().relative_to(root.resolve())).as_posix()
    except ValueError:
        raise ToolchainError(f"The model file {path} is not in the folder {root}.") from None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ToolchainError(f"Cannot read the model file {path}: {error.strerror}.") from None
    except UnicodeDecodeError:
        raise ToolchainError(f"The model file {path} does not have UTF-8 encoding.") from None
    return (name, text)
