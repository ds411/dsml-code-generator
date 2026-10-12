# trace: PRD-CORE-015, PRD-CORE-028, PRD-CORE-032, PRD-CORE-033
"""Tests that the environment and the order of the model files do not change the output (story #39).

Each test runs `dsml ir` and `dsml generate` in a subprocess, with the test
generator of `tests/dsml_test_command.py`. Each run uses a new project
folder, so that an absolute path in the output gives a difference. The tests
compare all output bytes: standard output, standard error, the exit codes
and each file in the project folder.

CI runs these tests on Linux x64 (Q62).

The tests of the order portal (story #177) run the generators of the
toolchain on the phase 2 reference model. The output has the FastAPI
application, the React application, the infrastructure and the workflows.
The tests of the order web (story #189) do the same for the phase 3
reference model. Its output has the Next.js application, the infrastructure
and the workflows.

The tests do not change `HOME`, because the `opensysml` client keeps the
`sysml-grpc` binary in a cache below the home folder.
"""

import getpass
import os
import socket
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
COMMAND = ROOT / "tests" / "dsml_test_command.py"
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
PRD_MODEL = ROOT / "docs" / "model" / "prd"
PORTAL_MODEL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
REACT_GOLDEN = ROOT / "tests" / "golden" / "react" / "order-portal"
WEB_MODEL = ROOT / "docs" / "model" / "examples" / "order-web" / "order-web.sysml"
NEXTJS_GOLDEN = ROOT / "tests" / "golden" / "nextjs" / "order-web"
PORTAL_CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.orderApi]
output = "services/order-api"

[applications.orderPortal]
output = "apps/order-portal"

[infrastructure]
output = "infra"

[pipelines]
output = ".github/workflows"
"""
"""The configuration file of the order portal: all generators write output."""
WEB_CONFIGURATION = """\
schema = 1

[model]
paths = ["model"]

[applications.orderWeb]
output = "apps/order-web"

[infrastructure]
output = "infra"

[pipelines]
output = ".github/workflows"
"""
"""The configuration file of the order web: all generators write output."""
# The requirement IDs of the example model and of the PRD model, for example
# "R-001" and "PRD-CORE-012" (PRD-DSML-051).
PRD_IDS = "'(R|PRD-[A-Z]+)-[0-9]{3,}'"

FAKE_USER = "dsml-test-user-7f3a"
FAKE_HOST = "dsml-test-host-9c2e"
OLD_FILE_TIME = 978_307_200
"""2001-01-01T00:00:00Z. The clock test gives this time to the model files."""
FORTY_YEARS = 40 * 365 * 24 * 60 * 60


@dataclass(frozen=True)
class Variant:
    """A change to the environment of the subprocess."""

    name: str
    environment: Mapping[str, str] = field(default_factory=dict[str, str])
    old_files: bool = False
    """Give an old modification time to the model files."""


# trace: PRD-CORE-015
VARIANTS = (
    Variant(
        "environment-variables",
        {
            "PYTHONHASHSEED": "4242",
            "PYTHONIOENCODING": "latin-1",
            "SOURCE_DATE_EPOCH": "1",
            "COLUMNS": "20",
            "TERM": "dumb",
            "NO_COLOR": "1",
            "CI": "",
            "DSML_UNKNOWN_VARIABLE": "value",
        },
    ),
    Variant("user-name", {"USER": FAKE_USER, "LOGNAME": FAKE_USER, "USERNAME": FAKE_USER}),
    Variant("host-name", {"HOSTNAME": FAKE_HOST, "DSML_TEST_HOST_NAME": FAKE_HOST}),
    Variant("locale-c", {"LC_ALL": "C", "LANG": "C"}),
    Variant("locale-turkish", {"LC_ALL": "tr_TR.UTF-8", "LANG": "tr_TR.UTF-8"}),
    Variant("locale-latin-1", {"LC_ALL": "de_DE.ISO8859-1", "LANG": "de_DE.ISO8859-1"}),
    Variant("time-zone-plus-14", {"TZ": "Pacific/Kiritimati"}),
    Variant("time-zone-minus-3-30", {"TZ": "America/St_Johns"}),
    Variant("clock", {"DSML_TEST_CLOCK_OFFSET": str(FORTY_YEARS)}, old_files=True),
)


def base_environment() -> dict[str, str]:
    """Give the environment of the reference run.

    The reference run has the environment of the test, with a fixed hash
    seed and the time zone UTC.
    """
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("DSML_TEST_") and key not in ("PYTHONIOENCODING", "PYTHONUTF8")
    }
    environment.update({"PYTHONHASHSEED": "0", "TZ": "UTC"})
    return environment


def example_model() -> dict[str, str]:
    """Give the example model, with text that is not ASCII.

    The text that is not ASCII makes sure that the encoding of standard
    output does not change the output.
    """
    text = EXAMPLE_MODEL.read_text(encoding="utf-8")
    changed = text.replace('"Track orders"', '"Track orders: café, Straße, 東京"', 1)
    assert changed != text
    return {"model/order-service.sysml": changed}


def prd_model() -> dict[str, str]:
    """Give the model files of the PRD model, sorted by name."""
    return {
        f"model/{path.name}": path.read_text(encoding="utf-8")
        for path in sorted(PRD_MODEL.glob("*.sysml"))
    }


# trace: PRD-CORE-015, PRD-CORE-032
def make_project(
    folder: Path,
    model: Mapping[str, str],
    paths: Sequence[str] = ("model",),
    old_files: bool = False,
) -> Path:
    """Write a project folder with the model files and `dsml.toml`.

    The function writes the model files in the order of `model`. `paths` is
    the key `model.paths` of the configuration file, in this order.
    """
    folder.mkdir(parents=True)
    for name, text in model.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        if old_files:
            os.utime(path, (OLD_FILE_TIME, OLD_FILE_TIME))
    entries = ", ".join(f'"{path}"' for path in paths)
    (folder / "dsml.toml").write_text(
        f"schema = 1\n\n[model]\npaths = [{entries}]\n\n[ids]\nrequirement = {PRD_IDS}\n",
        encoding="utf-8",
        newline="\n",
    )
    return folder


# trace: PRD-CORE-015, PRD-CORE-028
def run_dsml(project: Path, environment: Mapping[str, str]) -> dict[str, bytes]:
    """Run `dsml ir` and `dsml generate` in a subprocess. Give all the output.

    The result maps a name to the bytes of one output: the standard output,
    the standard error and the exit code of each command, and each file in the
    project folder after the run.
    """
    output: dict[str, bytes] = {}
    for command in (["ir"], ["generate"]):
        result = subprocess.run(
            [sys.executable, str(COMMAND), *command],
            cwd=project,
            env=dict(environment),
            capture_output=True,
            check=False,
        )
        name = command[0]
        output[f"dsml {name}: exit code"] = str(result.returncode).encode()
        output[f"dsml {name}: standard output"] = result.stdout
        output[f"dsml {name}: standard error"] = result.stderr
    for path in sorted(project.rglob("*")):
        if path.is_file():
            output[path.relative_to(project).as_posix()] = path.read_bytes()
    return output


def differences(expected: Mapping[str, bytes], actual: Mapping[str, bytes]) -> list[str]:
    """Give the names of the outputs that are different."""
    return sorted(
        name for name in expected.keys() | actual.keys() if expected.get(name) != actual.get(name)
    )


@pytest.fixture(scope="module")
def reference(tmp_path_factory: pytest.TempPathFactory) -> dict[str, bytes]:
    """The output of the example model in the reference environment."""
    project = make_project(tmp_path_factory.mktemp("reference") / "project", example_model())
    output = run_dsml(project, base_environment())
    assert output["dsml ir: exit code"] == b"0", output["dsml ir: standard error"].decode()
    assert output["dsml generate: exit code"] == b"0", output[
        "dsml generate: standard error"
    ].decode()
    return output


def test_reference_run_writes_the_output_of_the_test_generator(
    reference: Mapping[str, bytes],
) -> None:
    assert sorted(reference) == [
        ".dsml/generated.json",
        ".dsml/trace.gen.json",
        "app/orderApi/handler.py",
        "app/orderApi/service_gen.py",
        "dsml generate: exit code",
        "dsml generate: standard error",
        "dsml generate: standard output",
        "dsml ir: exit code",
        "dsml ir: standard error",
        "dsml ir: standard output",
        "dsml.toml",
        "infra/ir.gen.json",
        "infra/main.gen.tf",
        "model/order-service.sysml",
    ]
    assert reference["dsml ir: standard error"] == b""
    assert reference["dsml generate: standard error"] == b""
    assert reference["infra/ir.gen.json"] == reference["dsml ir: standard output"]
    assert "Straße, 東京".encode() in reference["dsml ir: standard output"]
    assert reference["dsml generate: standard output"] == (
        b"add .dsml/generated.json\n"
        b"add .dsml/trace.gen.json\n"
        b"add app/orderApi/handler.py\n"
        b"add app/orderApi/service_gen.py\n"
        b"add infra/ir.gen.json\n"
        b"add infra/main.gen.tf\n"
    )


# trace: PRD-CORE-015, PRD-CORE-028
@pytest.mark.parametrize("variant", VARIANTS, ids=[variant.name for variant in VARIANTS])
def test_environment_does_not_change_the_output(
    variant: Variant, reference: Mapping[str, bytes], tmp_path: Path
) -> None:
    project = make_project(tmp_path / "project", example_model(), old_files=variant.old_files)
    environment = base_environment()
    environment.update(variant.environment)
    output = run_dsml(project, environment)
    assert differences(reference, output) == []


@dataclass(frozen=True)
class FullProject:
    """A reference model that the generators of the toolchain write in full."""

    name: str
    model: Path
    configuration: str
    folders: frozenset[str]
    """The top-level folders of the output, with the model folder."""
    golden: Path
    """The golden folder of the application output."""
    output: str
    """The output folder of the application of the golden folder, with "/" at the end."""


FULL_PROJECTS = (
    FullProject(
        "order-portal",
        PORTAL_MODEL,
        PORTAL_CONFIGURATION,
        frozenset({".dsml", ".github", "apps", "infra", "model", "services"}),
        REACT_GOLDEN,
        "apps/order-portal/",
    ),
    FullProject(
        "order-web",
        WEB_MODEL,
        WEB_CONFIGURATION,
        frozenset({".dsml", ".github", "apps", "infra", "model"}),
        NEXTJS_GOLDEN,
        "apps/order-web/",
    ),
)
"""The order portal (story #177) and the order web (story #189)."""

MANIFESTS = (".dsml/generated.json", ".dsml/trace.gen.json")
"""The manifests in the folder of the configuration file. The golden folders of
the applications do not compare them with the full output."""


def full_project(reference: FullProject, folder: Path, old_files: bool = False) -> Path:
    """Write a project folder with a reference model and all output folders."""
    folder.mkdir(parents=True)
    model = folder / "model" / reference.model.name
    model.parent.mkdir()
    model.write_bytes(reference.model.read_bytes())
    if old_files:
        os.utime(model, (OLD_FILE_TIME, OLD_FILE_TIME))
    (folder / "dsml.toml").write_text(reference.configuration, encoding="utf-8", newline="\n")
    return folder


def toolchain_environment(variant: Mapping[str, str] | None = None) -> dict[str, str]:
    """Give the environment of a run with the generators of the toolchain."""
    environment = base_environment()
    environment.update(variant or {})
    environment["DSML_TEST_GENERATORS"] = "toolchain"
    return environment


@pytest.fixture(scope="module", params=FULL_PROJECTS, ids=[item.name for item in FULL_PROJECTS])
def full_reference(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> tuple[FullProject, dict[str, bytes]]:
    """The full output of a reference model in the reference environment."""
    reference: FullProject = request.param
    folder = tmp_path_factory.mktemp(f"{reference.name}-reference") / "project"
    output = run_dsml(full_project(reference, folder), toolchain_environment())
    assert output["dsml generate: exit code"] == b"0", output[
        "dsml generate: standard error"
    ].decode()
    return reference, output


# trace: PRD-CORE-028, PRD-CORE-029
def test_reference_run_writes_the_full_output(
    full_reference: tuple[FullProject, Mapping[str, bytes]],
) -> None:
    """The run writes the output of each generator.

    The application output agrees with the golden files.
    """
    reference, output = full_reference
    assert output["dsml ir: standard error"] == b""
    assert output["dsml generate: standard error"] == b""
    folders = {name.split("/")[0] for name in output if "/" in name}
    assert folders == reference.folders
    application = {
        name.removeprefix(reference.output): content
        for name, content in output.items()
        if name.startswith(reference.output)
    }
    golden = {
        path.relative_to(reference.golden).as_posix(): path.read_bytes()
        for path in sorted(reference.golden.rglob("*"))
        if path.is_file() and path.relative_to(reference.golden).as_posix() not in MANIFESTS
    }
    assert application == golden


# trace: PRD-CORE-015, PRD-CORE-028
@pytest.mark.parametrize("variant", VARIANTS, ids=[variant.name for variant in VARIANTS])
def test_environment_does_not_change_the_full_output(
    variant: Variant,
    full_reference: tuple[FullProject, Mapping[str, bytes]],
    tmp_path: Path,
) -> None:
    reference, expected = full_reference
    project = full_project(reference, tmp_path / "project", old_files=variant.old_files)
    output = run_dsml(project, toolchain_environment(variant.environment))
    assert differences(expected, output) == []


@pytest.fixture(scope="module")
def prd_reference(tmp_path_factory: pytest.TempPathFactory) -> dict[str, bytes]:
    """The output of the PRD model, with the files in sorted order and the folder in `dsml.toml`."""
    project = make_project(tmp_path_factory.mktemp("prd-reference") / "project", prd_model())
    output = run_dsml(project, base_environment())
    assert output["dsml generate: exit code"] == b"0", output[
        "dsml generate: standard error"
    ].decode()
    return output


# trace: PRD-CORE-032
@pytest.mark.parametrize(
    ("disk", "configuration"),
    [
        ("reversed", "folder"),
        ("sorted", "reversed-list"),
        ("reversed", "sorted-list"),
        ("reversed", "reversed-list-and-folder"),
    ],
)
def test_order_of_the_model_files_does_not_change_the_output(
    disk: str, configuration: str, prd_reference: Mapping[str, bytes], tmp_path: Path
) -> None:
    """Write the model files in a different order and list them in a different order.

    `disk` is the order in which the test writes the files. `configuration`
    gives the key `model.paths`: the folder, a list of the files, or both.
    """
    files = prd_model()
    names = list(files)
    model = dict(reversed(files.items())) if disk == "reversed" else files
    paths = {
        "folder": ["model"],
        "sorted-list": names,
        "reversed-list": names[::-1],
        "reversed-list-and-folder": [*names[::-1], "model"],
    }[configuration]
    project = make_project(tmp_path / "project", model, paths)
    output = run_dsml(project, base_environment())
    assert [name for name in differences(prd_reference, output) if name != "dsml.toml"] == []


# trace: PRD-CORE-033
@pytest.mark.parametrize("model", ["order-service", "order-portal", "order-web"])
def test_output_has_no_absolute_path_no_user_name_and_no_host_name(
    model: str, tmp_path: Path
) -> None:
    names = {
        "USER": FAKE_USER,
        "LOGNAME": FAKE_USER,
        "USERNAME": FAKE_USER,
        "HOSTNAME": FAKE_HOST,
        "DSML_TEST_HOST_NAME": FAKE_HOST,
    }
    references = {item.name: item for item in FULL_PROJECTS}
    if model in references:
        project = full_project(references[model], tmp_path / "project")
        environment = toolchain_environment(names)
        # The generated code has fixed words that can be real names, for
        # example "root" in the React entry module and "runner" in the
        # workflows. Thus the test examines only the changed names.
        model_text = None
    else:
        project = make_project(tmp_path / "project", example_model())
        environment = base_environment()
        environment.update(names)
        model_text = EXAMPLE_MODEL.read_text(encoding="utf-8")
    output = run_dsml(project, environment)
    assert output["dsml generate: exit code"] == b"0"
    forbidden = {
        str(project),
        str(project.resolve()),
        str(ROOT),
        # A path below the home folder. The home folder alone can be a part
        # of a file name, for example "/root" in "src/_app/layout/root-layout.gen.tsx".
        f"{Path.home()}/",
        FAKE_USER,
        FAKE_HOST,
    }
    # The real names of the test machine. A name that occurs in the model
    # text, for example a short user name, is not a useful check.
    for name in (getpass.getuser(), socket.gethostname()):
        if model_text is not None and len(name) >= 4 and name not in model_text:
            forbidden.add(name)
    found = sorted(
        f"{name}: {text}"
        for name, content in output.items()
        if not name.startswith("model/")
        for text in forbidden
        if text.encode() in content
    )
    assert found == []
