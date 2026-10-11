# trace: PRD-CORE-001
"""Measure the time of `dsml ir` for a generated model with 1,000 elements.

Story #33 records the results in docs/notes/ir-performance.md. CI runs this
script on Linux x64. Run it from the root of the repository:

    uv run python scripts/measure_ir.py

The script writes the model into a temporary folder. The model has the
elements of the needs, requirements, application and verification layers. The
IR of the model has exactly the number of elements that `--elements` gives.
Decision Q50 gives the limit: 10 seconds for 1,000 elements on a GitHub-hosted
Linux runner with 4 vCPUs. The limit applies to `dsml validate` and
`dsml generate`. These commands make the IR first.
"""

import argparse
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RUNS = 5
MODEL_FILE = "large-model.sysml"
UNIT_ELEMENTS = 6
"""The IR elements of one unit: a need, a requirement, an entity, two fields and a verification."""


def make_model(elements: int) -> str:
    """Give the text of a model with this number of IR elements.

    The package is one element. Each unit gives six elements. One or more
    stakeholders give the remaining elements.
    """
    units = (elements - 2) // UNIT_ELEMENTS
    stakeholders = elements - 1 - units * UNIT_ELEMENTS
    if units < 1:
        raise ValueError(f"The model must have {UNIT_ELEMENTS + 2} or more elements.")
    lines = [
        "package LargeModel {",
        "    private import DSML::*;",
        "    private import ScalarValues::*;",
        "    @DsmlVersion { major = 1; minor = 0; }",
        "",
    ]
    lines += [f"    #Stakeholder part def Owner{s};" for s in range(1, stakeholders + 1)]
    for unit in range(1, units + 1):
        i = f"{unit:04d}"
        lines += [
            "",
            f"    #Need concern <'N-{i}'> need{i} {{",
            f"        doc /* The owner must see the data of item {i}. */",
            f'        :>> title = "Need {i}";',
            "        :>> priority = Priority::must;",
            "        :>> status = Status::approved;",
            "        subject;",
            "        stakeholder owner : Owner1;",
            "    }",
            f"    #Requirement requirement <'R-{i}'> requirement{i} {{",
            f"        doc /* The API must return item {i}. */",
            f'        :>> title = "Requirement {i}";',
            "        :>> kind = RequirementKind::functional;",
            "        :>> priority = Priority::must;",
            "        :>> status = Status::approved;",
            f"        frame need{i};",
            "    }",
            f"    #Entity part def Item{i} {{",
            "        #Key attribute id : Uuid [1];",
            "        attribute name : String [1];",
            "    }",
            f"    #Verification verification <'V-{i}'> verification{i} {{",
            f'        :>> title = "Verification {i}";',
            "        :>> method = VerificationMethod::test;",
            f"        objective {{ verify requirement{i}; }}",
            "    }",
        ]
    lines.append("}")
    return "".join(f"{line}\n" for line in lines)


def run_ir(folder: Path) -> tuple[float, bytes]:
    """Run `dsml ir` on the model in `folder`. Give the time in ms and the IR."""
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "dsml", "ir", MODEL_FILE],
        cwd=folder,
        capture_output=True,
        check=False,
    )
    elapsed = (time.perf_counter() - start) * 1000
    if result.returncode != 0:
        raise RuntimeError(f"dsml ir failed: {result.stderr.decode()}")
    return elapsed, result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure the time of dsml ir.")
    parser.add_argument("--elements", type=int, default=1000, help="the IR elements of the model")
    args = parser.parse_args()
    print(f"platform: {platform.system().lower()}-{platform.machine().lower()}")
    with tempfile.TemporaryDirectory() as name:
        folder = Path(name)
        model = make_model(args.elements)
        (folder / MODEL_FILE).write_text(model, encoding="utf-8", newline="\n")
        # The first run can include the download of sysml-grpc.
        run_ir(folder)
        times: list[float] = []
        ir = b""
        for _ in range(RUNS):
            elapsed, ir = run_ir(folder)
            times.append(elapsed)
    data = json.loads(ir)
    print(
        f"dsml ir ({len(data['elements'])} elements, {len(data['links'])} links, "
        f"{len(model.splitlines())} lines, median of {RUNS}): {statistics.median(times):.0f} ms"
    )


if __name__ == "__main__":
    main()
