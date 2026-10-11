# trace: PRD-CORE-005, PRD-CORE-026, PRD-CORE-039
"""The interface of the generators and the list of the generators.

Each generator reads only the IR and the configuration (PRD-CORE-026). It
gives its output files to the file writer and writes no file itself. The
real generators come in a later milestone (M6). Until then, the list
`GENERATORS` is empty, and the tests use a test generator.
"""

from collections import Counter
from collections.abc import Collection, Sequence
from typing import Protocol

from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.generate.writer import OutputFile, check_files
from dsml.ir.model import Ir


# trace: PRD-CORE-005, PRD-CORE-039
class Generator(Protocol):
    """A generator of one target."""

    @property
    def name(self) -> str:
        """The name of the generator, for messages."""
        ...

    @property
    def fixed_names(self) -> Collection[str]:
        """The fixed-name list of the target (PRD-CORE-039). See `is_generated_name`."""
        ...

    def generate(
        self, ir: Ir, configuration: Configuration, parts: Collection[str] | None
    ) -> Sequence[OutputFile]:
        """Give the output files of the selected parts. `None` selects all parts."""
        ...


GENERATORS: list[Generator] = []
"""The generators that `dsml generate` runs, in a fixed order."""


# trace: PRD-CORE-005, PRD-CORE-039
def collect(
    generators: Sequence[Generator],
    ir: Ir,
    configuration: Configuration,
    parts: Collection[str] | None,
) -> list[OutputFile]:
    """Run each generator and check its output files.

    The function gives the files of the selected parts only, sorted by path.
    """
    files: list[OutputFile] = []
    for generator in generators:
        output = [
            file
            for file in generator.generate(ir, configuration, parts)
            if parts is None or file.part in parts
        ]
        try:
            check_files(output, generator.fixed_names)
        except ToolchainError as error:
            raise ToolchainError(
                f"The generator {generator.name} is not correct.\n{error}"
            ) from None
        files.extend(output)
    counts = Counter(file.path for file in files)
    twice = sorted(path for path, count in counts.items() if count > 1)
    if twice:
        raise ToolchainError("\n".join(f'Two generators give the file "{path}".' for path in twice))
    return sorted(files, key=lambda file: file.path)
