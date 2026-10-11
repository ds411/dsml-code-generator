# trace: PRD-TRACE-013, PRD-TRACE-017, PRD-TRACE-018, PRD-CORE-028
"""The report model of the trace reports and its JSON and CSV writers.

All trace reports use one model: a table with fixed columns and sorted rows.
A cell is one text, or a list of texts. The writers take any report table,
thus each report is available in each format (PRD-TRACE-017).

Each report gives the model commit and the baseline commit, and no date or
time (PRD-TRACE-018). A report that does not compare with a baseline has no
baseline commit.

The output is the same for the same table (PRD-CORE-028):

- JSON: canonical JSON with sorted keys, UTF-8 and LF line ends. Each row is
  an object with one key for each column. A list cell is a JSON list.
- CSV: three comment lines that start with "#" (the report, the model commit
  and the baseline commit), then one header line and one line for each row.
  A list cell has its items in one field, with "; " between them. The line
  end is LF.
"""

import csv
import io
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from dsml.ir.writer import JsonValue, canonical_json

REPORT_VERSION: Final = 1
"""The version of the JSON form of the trace reports."""

LIST_SEPARATOR: Final = "; "
"""The text between the items of a list cell in a CSV field."""

type Cell = str | tuple[str, ...]
"""One cell of a report: one text, or a list of texts."""


def _cell_key(cell: Cell) -> tuple[str, ...]:
    return (cell,) if isinstance(cell, str) else cell


# trace: PRD-TRACE-013, PRD-TRACE-018, PRD-CORE-028
@dataclass(frozen=True, slots=True)
class Report:
    """One trace report: a table with fixed columns and sorted rows.

    The constructor sorts the rows and removes duplicate rows. Each row must
    have one cell for each column. The items of a list cell keep their order.
    """

    name: str
    """The name of the report, for example `coverage`."""
    columns: tuple[str, ...]
    """The names of the columns, in their order."""
    rows: tuple[tuple[Cell, ...], ...]
    model_commit: str
    """The commit of the model, or a text that tells why there is no commit."""
    baseline_commit: str | None = None
    """The commit of the baseline. `None` if the report uses no baseline."""

    def __post_init__(self) -> None:
        if len(set(self.columns)) != len(self.columns):
            raise ValueError(f'The report "{self.name}" has two columns with the same name.')
        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError(
                    f'A row of the report "{self.name}" has {len(row)} cells. '
                    f"The report has {len(self.columns)} columns."
                )
        rows = sorted(set(self.rows), key=lambda row: tuple(_cell_key(cell) for cell in row))
        object.__setattr__(self, "rows", tuple(rows))


# trace: PRD-TRACE-017, PRD-TRACE-018, PRD-CORE-028
def json_report(report: Report) -> str:
    """Write the report as canonical JSON."""
    rows: list[JsonValue] = []
    for row in report.rows:
        rows.append(
            {
                column: cell if isinstance(cell, str) else list(cell)
                for column, cell in zip(report.columns, row, strict=True)
            }
        )
    columns: list[JsonValue] = list(report.columns)
    data: dict[str, JsonValue] = {
        "baselineCommit": report.baseline_commit,
        "columns": columns,
        "modelCommit": report.model_commit,
        "report": report.name,
        "reportVersion": REPORT_VERSION,
        "rows": rows,
    }
    return canonical_json(data).decode()


# trace: PRD-TRACE-017, PRD-TRACE-018, PRD-CORE-028, PRD-CORE-034
def csv_report(report: Report) -> str:
    """Write the report as CSV with LF line ends."""
    baseline = "none" if report.baseline_commit is None else report.baseline_commit
    head = [
        f"# report: {report.name}",
        f"# model commit: {report.model_commit}",
        f"# baseline commit: {baseline}",
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(report.columns)
    writer.writerows(_csv_fields(row) for row in report.rows)
    return "".join(f"{line}\n" for line in head) + buffer.getvalue()


def _csv_fields(row: Sequence[Cell]) -> list[str]:
    return [cell if isinstance(cell, str) else LIST_SEPARATOR.join(cell) for cell in row]


def texts(items: Iterable[str]) -> tuple[str, ...]:
    """Give the items as a list cell, sorted and with no duplicate."""
    return tuple(sorted(set(items)))
