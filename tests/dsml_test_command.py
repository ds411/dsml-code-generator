# trace: PRD-CORE-015, PRD-CORE-028, PRD-TRACE-006, PRD-TRACE-007
"""Run the command `dsml` with a test generator and an optional changed clock.

The determinism tests in `tests/test_determinism.py` run this script in a
subprocess with a changed environment:

    python tests/dsml_test_command.py generate --config dsml.toml

The real generators come in a later milestone (M6). Until then, the
script adds the test generator `IrGenerator`. The test generator reads only
the IR, like a real generator (PRD-CORE-026). Its output files contain the
IR, the output of a template and the header, so that a change in the IR or
in the template engine changes them. The test generator also gives the
symbols of its generated files, so `dsml generate` writes a trace manifest.

The script reads these environment variables before it imports `dsml`:

- `DSML_TEST_CLOCK_OFFSET`: a number of seconds. The script adds it to the
  clock of `time` and `datetime`.
- `DSML_TEST_HOST_NAME`: the host name that `socket.gethostname()` and
  `platform.node()` give.
"""

import datetime
import os
import platform
import socket
import sys
import time
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Self

CLOCK_OFFSET = "DSML_TEST_CLOCK_OFFSET"
HOST_NAME = "DSML_TEST_HOST_NAME"
TEMPLATES = Path(__file__).resolve().parent / "templates"


def _change_clock(offset: float) -> None:
    """Add an offset to the clock of `time` and `datetime`."""
    real_time = time.time
    real_time_ns = time.time_ns
    real_datetime = datetime.datetime
    real_date = datetime.date

    class ChangedDateTime(real_datetime):
        @classmethod
        def now(cls, tz: datetime.tzinfo | None = None) -> Self:
            return cls.fromtimestamp(time.time(), tz)

        @classmethod
        def utcnow(cls) -> Self:
            return cls.now(datetime.UTC).replace(tzinfo=None)

        @classmethod
        def today(cls) -> Self:
            return cls.now()

    class ChangedDate(real_date):
        @classmethod
        def today(cls) -> Self:
            return cls.fromtimestamp(time.time())

    time.time = lambda: real_time() + offset
    time.time_ns = lambda: real_time_ns() + int(offset * 1_000_000_000)
    datetime.datetime = ChangedDateTime
    datetime.date = ChangedDate


def _change_host_name(name: str) -> None:
    """Give a different host name to `socket` and `platform`."""
    socket.gethostname = lambda: name
    platform.node = lambda: name


if CLOCK_OFFSET in os.environ:
    _change_clock(float(os.environ[CLOCK_OFFSET]))
if HOST_NAME in os.environ:
    _change_host_name(os.environ[HOST_NAME])

# Import the toolchain after the changes, so that it sees only the changed
# functions.
from dsml.cli import main  # noqa: E402
from dsml.config import Configuration  # noqa: E402
from dsml.generate import generators  # noqa: E402
from dsml.generate.header import FileType, header  # noqa: E402
from dsml.generate.names import pascal_case, python_name, snake_case  # noqa: E402
from dsml.generate.templates import TemplateEngine  # noqa: E402
from dsml.generate.trace import Symbol, SymbolKind  # noqa: E402
from dsml.generate.writer import (  # noqa: E402
    INFRASTRUCTURE,
    Kind,
    OutputFile,
    application_part,
)
from dsml.ir.model import Element, Ir  # noqa: E402
from dsml.ir.writer import write_ir  # noqa: E402

AWS_RESOURCE_TYPES = {
    "AwsCognito": "aws_cognito_user_pool",
    "AwsEcsService": "aws_ecs_service",
    "AwsRdsPostgres": "aws_db_instance",
    "AwsVpc": "aws_vpc",
}
"""The HCL resource type of each AWS realization kind of the test generator."""


# trace: PRD-TRACE-006
def python_symbols(content: bytes, elements: dict[str, tuple[str, ...]]) -> tuple[Symbol, ...]:
    """Give a symbol for each top-level `def` and `class` of Python text.

    `elements` maps a symbol name to the identities of its model elements. A
    symbol ends at its last line that is not empty.
    """
    lines = content.decode("utf-8").split("\n")[:-1]
    starts = [
        number for number, line in enumerate(lines, start=1) if line.startswith(("def ", "class "))
    ]
    symbols: list[Symbol] = []
    for index, first in enumerate(starts):
        last = starts[index + 1] - 1 if index + 1 < len(starts) else len(lines)
        while not lines[last - 1].strip():
            last -= 1
        line = lines[first - 1]
        kind = SymbolKind.FUNCTION if line.startswith("def ") else SymbolKind.CLASS
        name = line.split()[1].split("(")[0].rstrip(":")
        if name in elements:
            symbols.append(Symbol(kind, name, first, last, elements[name]))
    return tuple(symbols)


# trace: PRD-TRACE-006, PRD-TRACE-007
def hcl_file(ir: Ir) -> OutputFile:
    """Give `infra/main.gen.tf` with one resource for each AWS realization.

    The address of each resource is a symbol of the AWS realization and of
    the logical element that it realizes.
    """
    realized = {link.source: link.target for link in ir.links if link.type == "realizes"}
    aws: list[Element] = sorted(
        (element for element in ir.elements if element.kind in AWS_RESOURCE_TYPES),
        key=lambda element: element.identity,
    )
    text = header(FileType.HCL, [element.identity for element in aws])
    symbols: list[Symbol] = []
    for element in aws:
        address = f"{AWS_RESOURCE_TYPES[element.kind]}.{snake_case(element.name)}"
        resource_type, name = address.split(".")
        block = (
            f'\nresource "{resource_type}" "{name}" {{\n'
            "  tags = {\n"
            f'    "dsml:element" = "{element.identity}"\n'
            "  }\n"
            "}\n"
        )
        first = text.count("\n") + 2
        text += block
        identities = [element.identity]
        if element.identity in realized:
            identities.append(realized[element.identity])
        symbols.append(
            Symbol(SymbolKind.RESOURCE, address, first, text.count("\n"), tuple(identities))
        )
    return OutputFile(
        "infra/main.gen.tf", text.encode(), Kind.GENERATED, INFRASTRUCTURE, tuple(symbols)
    )


# trace: PRD-CORE-015, PRD-CORE-026, PRD-CORE-028, PRD-TRACE-006
class IrGenerator:
    """The test generator. Its output files come from the IR only.

    - `infra/ir.gen.json`: the IR as canonical JSON.
    - `infra/main.gen.tf`: one HCL resource for each AWS realization.
    - `app/<application>/service_gen.py`: the output of the template
      `example/service_gen.py.j2` for each application.
    - `app/<application>/handler.py`: a create-once file.

    The HCL file and the Python files have symbols.
    """

    name = "test-ir"
    fixed_names: Collection[str] = ()

    def generate(
        self, ir: Ir, configuration: Configuration, parts: Collection[str] | None
    ) -> Sequence[OutputFile]:
        engine = TemplateEngine.for_folder(TEMPLATES)
        files = [
            OutputFile("infra/ir.gen.json", write_ir(ir), Kind.GENERATED, INFRASTRUCTURE),
            hcl_file(ir),
        ]
        operations = [element for element in ir.elements if element.kind == "Operation"]
        entities = [element.name for element in ir.elements if element.kind == "Entity"]
        for application in ir.elements:
            if application.kind != "Application":
                continue
            part = application_part(application.name)
            data = {
                "file_type": "python",
                "elements": [application.identity, *(item.identity for item in operations)],
                "service": application.name,
                "operations": operations,
                "entities": entities,
            }
            content = engine.render_bytes("example/service_gen.py.j2", data)
            symbol_elements = {
                python_name(operation.name): (operation.identity,) for operation in operations
            }
            symbol_elements[pascal_case(application.name)] = (application.identity,)
            symbols = python_symbols(content, symbol_elements)
            folder = f"app/{application.name}"
            files.append(
                OutputFile(f"{folder}/service_gen.py", content, Kind.GENERATED, part, symbols)
            )
            files.append(
                OutputFile(f"{folder}/handler.py", b"# Your code.\n", Kind.CREATE_ONCE, part)
            )
        return files


if __name__ == "__main__":
    generators.GENERATORS[:] = [IrGenerator()]
    raise SystemExit(main(sys.argv[1:]))
