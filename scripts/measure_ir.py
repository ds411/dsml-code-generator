# trace: PRD-CORE-001, PRD-TOP-012
"""Measure the time of `dsml ir`, `dsml validate` and `dsml generate`.

Story #33 measured `dsml ir`. Story #139 added `dsml validate` and
`dsml generate`. docs/notes/ir-performance.md records the results. CI runs
this script on Linux x64. Run it from the root of the repository:

    uv run python scripts/measure_ir.py

The script writes the model and `dsml.toml` into a temporary folder. The
model has the elements of all five layers. It has a FastAPI application and
the infrastructure of one container service, so that `dsml generate` writes
the FastAPI code, the HCL and the workflows. The IR of the model has exactly
the number of elements that `--elements` gives.

Decision Q50 gives the limit: `dsml validate` and `dsml generate` on a model
with 1,000 elements must finish in less than 10 seconds, on a GitHub-hosted
Linux runner with 4 vCPUs. If the model has 1,000 elements or fewer and a
command takes 10 seconds or more, the script stops with exit code 1. Q50
gives no time limit for larger models.
"""

import argparse
import json
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from pathlib import Path

RUNS = 5
MODEL_FILE = "large-model.sysml"
CONFIGURATION = """\
schema = 1

[model]
paths = ["large-model.sysml"]

[applications.itemApi]
output = "services/items"

[infrastructure]
output = "infra"

[pipelines]
output = ".github/workflows"
"""
OUTPUT = (".dsml", ".github", "infra", "services")
"""The folders that `dsml generate` writes."""
UNIT_ELEMENTS = 7
"""The IR elements of one unit: a need, a requirement, an entity, two fields,
an exposed part and a verification."""
SOLUTION_ELEMENTS = 14
"""The IR elements of the roles, the application and the infrastructure."""
LIMIT_ELEMENTS = 1000
"""Q50 gives a time limit for models with this number of elements or fewer."""
LIMIT_MS = 10_000.0
"""The time limit of Q50 for `dsml validate` and for `dsml generate`."""


def make_model(elements: int) -> str:
    """Give the text of a model with this number of IR elements.

    The package is one element. The solution part gives 14 elements. Each
    unit gives seven elements. One or more stakeholders give the remaining
    elements.
    """
    minimum = 1 + SOLUTION_ELEMENTS + UNIT_ELEMENTS + 1
    if elements < minimum:
        raise ValueError(f"The model must have {minimum} or more elements.")
    units = (elements - 2 - SOLUTION_ELEMENTS) // UNIT_ELEMENTS
    stakeholders = elements - 1 - SOLUTION_ELEMENTS - units * UNIT_ELEMENTS
    lines = [
        "package LargeModel {",
        "    private import DSML::*;",
        "    private import ScalarValues::*;",
        "    @DsmlVersion { major = 1; minor = 0; }",
        "",
    ]
    lines += [f"    #Stakeholder part def Owner{s};" for s in range(1, stakeholders + 1)]
    exposed: list[str] = []
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
            f"    satisfy requirement{i} by itemApi;",
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
        exposed += [
            f"        #Exposed part items{i} : Item{i} [*] {{",
            "            :>> crud = (CrudKind::read, CrudKind::list);",
            "            :>> allowedRoles = (AppRoles::reader);",
            "        }",
        ]
    lines += [
        "",
        "    #Roles enum def AppRoles { reader; }",
        "    #Application part itemApi {",
        "        :>> target = Target::fastapi;",
        *exposed,
        "    }",
        "",
        "    #Network part network;",
        "    #ContainerService part apiService;",
        "    #RelationalDatabase part itemDb;",
        "    #UserDirectory part users;",
        "    #Uses dependency from apiService to itemDb;",
        "    #Uses dependency from apiService to users;",
        "    allocate itemApi to apiService;",
        "",
        "    #AwsVpc part networkAws;",
        "    #AwsEcsService part apiServiceAws { :>> cpu default = 512; "
        ":>> memory default = 1024; :>> desiredCount default = 1; }",
        '    #AwsRdsPostgres part itemDbAws { :>> instanceClass default = "db.t4g.micro"; '
        ":>> multiAz default = true; }",
        "    #AwsCognito part usersAws;",
        "    #Realizes dependency from networkAws to network;",
        "    #Realizes dependency from apiServiceAws to apiService;",
        "    #Realizes dependency from itemDbAws to itemDb;",
        "    #Realizes dependency from usersAws to users;",
        "",
        '    #ToolingAccount part tooling { :>> accountId = "111111111111"; '
        ':>> region = "eu-west-1"; }',
    ]
    for number, environment in enumerate(("dev", "staging", "prod"), start=2):
        domain = (
            "items.example.com" if environment == "prod" else f"items.{environment}.example.com"
        )
        lines.append(
            f'    #Environment part {environment} {{ :>> accountId = "{str(number) * 12}"; '
            f':>> region = "eu-west-1"; :>> domain = "{domain}"; }}'
        )
    lines.append("}")
    return "".join(f"{line}\n" for line in lines)


def write_project(folder: Path, elements: int) -> str:
    """Write the model and `dsml.toml` into `folder`. Give the text of the model."""
    model = make_model(elements)
    (folder / MODEL_FILE).write_text(model, encoding="utf-8", newline="\n")
    (folder / "dsml.toml").write_text(CONFIGURATION, encoding="utf-8", newline="\n")
    return model


def remove_output(folder: Path) -> None:
    """Delete the files of `dsml generate`, so that the next run writes all files again."""
    for name in OUTPUT:
        shutil.rmtree(folder / name, ignore_errors=True)


def run_command(folder: Path, arguments: Sequence[str]) -> tuple[float, bytes]:
    """Run `dsml` with these arguments in `folder`. Give the time in ms and the output."""
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "dsml", *arguments],
        cwd=folder,
        capture_output=True,
        check=False,
    )
    elapsed = (time.perf_counter() - start) * 1000
    if result.returncode != 0:
        command = " ".join(["dsml", *arguments])
        raise RuntimeError(
            f"{command} failed with exit code {result.returncode}: "
            f"{result.stdout.decode()}{result.stderr.decode()}"
        )
    return elapsed, result.stdout


def run_ir(folder: Path) -> tuple[float, bytes]:
    """Run `dsml ir` on the model in `folder`. Give the time in ms and the IR."""
    return run_command(folder, ["ir", MODEL_FILE])


def run_validate(folder: Path) -> tuple[float, bytes]:
    """Run `dsml validate` on the project in `folder`. Give the time in ms and the findings."""
    return run_command(folder, ["validate"])


def run_generate(folder: Path) -> tuple[float, bytes]:
    """Run `dsml generate` on the project in `folder`. Give the time in ms and the file list.

    The function first deletes the output of an earlier run, so that each
    run writes all files.
    """
    remove_output(folder)
    return run_command(folder, ["generate"])


# trace: PRD-TOP-012
def over_limit(medians: dict[str, float], elements: int) -> list[str]:
    """Give the commands that take 10 seconds or more (Q50).

    Only `dsml validate` and `dsml generate` have a limit. Models with more
    than 1,000 elements have no limit.
    """
    if elements > LIMIT_ELEMENTS:
        return []
    return [
        command
        for command in ("dsml validate", "dsml generate")
        if medians.get(command, 0.0) >= LIMIT_MS
    ]


def median_time(folder: Path, run: Callable[[Path], tuple[float, bytes]]) -> float:
    """Give the median time in ms of `RUNS` runs, after one run that starts the cache."""
    run(folder)
    return statistics.median(run(folder)[0] for _ in range(RUNS))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure the time of dsml ir, dsml validate and dsml generate."
    )
    parser.add_argument("--elements", type=int, default=1000, help="the IR elements of the model")
    args = parser.parse_args()
    print(f"platform: {platform.system().lower()}-{platform.machine().lower()}")
    medians: dict[str, float] = {}
    with tempfile.TemporaryDirectory() as name:
        folder = Path(name)
        model = write_project(folder, args.elements)
        # The first run can include the download of sysml-grpc.
        run_ir(folder)
        medians["dsml ir"] = median_time(folder, run_ir)
        data = json.loads(run_ir(folder)[1])
        medians["dsml validate"] = median_time(folder, run_validate)
        medians["dsml generate"] = median_time(folder, run_generate)
        files = len(run_generate(folder)[1].decode().splitlines())
    print(
        f"model: {len(data['elements'])} elements, {len(data['links'])} links, "
        f"{len(model.splitlines())} lines; dsml generate writes {files} files"
    )
    for command, value in medians.items():
        print(f"{command} (median of {RUNS}): {value:.0f} ms")
    failed = over_limit(medians, args.elements)
    for command in failed:
        print(
            f"error: {command} takes {medians[command]:.0f} ms. "
            f"The limit of Q50 is {LIMIT_MS:.0f} ms.",
            file=sys.stderr,
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
