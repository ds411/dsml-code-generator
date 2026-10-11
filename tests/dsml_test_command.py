# trace: PRD-CORE-015, PRD-CORE-028
"""Run the command `dsml` with a test generator and an optional changed clock.

The determinism tests in `tests/test_determinism.py` run this script in a
subprocess with a changed environment:

    python tests/dsml_test_command.py generate --config dsml.toml

The real generators come in a later milestone (M6). Until then, the
script adds the test generator `IrGenerator`. The test generator reads only
the IR, like a real generator (PRD-CORE-026). Its output files contain the
IR, the output of a template and the header, so that a change in the IR or
in the template engine changes them.

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
from dsml.generate.templates import TemplateEngine  # noqa: E402
from dsml.generate.writer import (  # noqa: E402
    INFRASTRUCTURE,
    Kind,
    OutputFile,
    application_part,
)
from dsml.ir.model import Ir  # noqa: E402
from dsml.ir.writer import write_ir  # noqa: E402


# trace: PRD-CORE-015, PRD-CORE-026, PRD-CORE-028
class IrGenerator:
    """The test generator. Its output files come from the IR only.

    - `infra/ir.gen.json`: the IR as canonical JSON.
    - `app/<application>/service_gen.py`: the output of the template
      `example/service_gen.py.j2` for each application.
    - `app/<application>/handler.py`: a create-once file.
    """

    name = "test-ir"
    fixed_names: Collection[str] = ()

    def generate(
        self, ir: Ir, configuration: Configuration, parts: Collection[str] | None
    ) -> Sequence[OutputFile]:
        engine = TemplateEngine.for_folder(TEMPLATES)
        files = [OutputFile("infra/ir.gen.json", write_ir(ir), Kind.GENERATED, INFRASTRUCTURE)]
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
            folder = f"app/{application.name}"
            files.append(OutputFile(f"{folder}/service_gen.py", content, Kind.GENERATED, part))
            files.append(
                OutputFile(f"{folder}/handler.py", b"# Your code.\n", Kind.CREATE_ONCE, part)
            )
        return files


if __name__ == "__main__":
    generators.GENERATORS[:] = [IrGenerator()]
    raise SystemExit(main(sys.argv[1:]))
