"""Tests of the README of the pipelines with the repository settings (story #89).

The golden README is `tests/golden/pipelines/order-service/.github/workflows/README.gen.md`.
`tests/test_pipeline_generator.py` compares the full output with the golden files.
"""

import re
from pathlib import Path, PurePosixPath

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Application, Configuration
from dsml.generate.pipelines.generator import PipelineGenerator, job_names
from dsml.ir.model import Ir

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
GOLDEN = ROOT / "tests/golden/pipelines/order-service/.github/workflows"
README_PATH = ".github/workflows/README.gen.md"
WORKFLOWS = PurePosixPath(".github/workflows")
CONFIGURATION = Configuration(
    applications=(Application("orderApi", PurePosixPath("services/order-api")),),
    infrastructure=PurePosixPath("infra"),
    pipelines=WORKFLOWS,
)


@pytest.fixture(scope="module")
def ir() -> Ir:
    return make_ir([EXAMPLE], ROOT)


def _readme(ir: Ir, configuration: Configuration = CONFIGURATION) -> str:
    files = PipelineGenerator(version="0.1.0").generate(ir, configuration, None)
    by_path = {file.path: file for file in files}
    assert by_path[README_PATH].symbols == ()
    return by_path[README_PATH].content.decode("utf-8")


def _section(text: str, heading: str) -> str:
    """Give the text of a section of level 2, without its heading."""
    start = text.index(f"\n## {heading}\n") + len(heading) + 5
    end = text.find("\n## ", start)
    return text[start:] if end == -1 else text[start:end]


def _first_column(section: str) -> list[str]:
    """Give the values in code font of the first column of the table of a section."""
    return re.findall(r"^\| `([^`]+)` \|", section, flags=re.MULTILINE)


def _golden_workflows() -> str:
    return "".join(path.read_text(encoding="utf-8") for path in sorted(GOLDEN.glob("*.yml")))


# trace: PRD-CICD-013, PRD-CICD-012
def test_readme_names_each_environment_of_the_golden_workflows() -> None:
    workflows = _golden_workflows()
    environments = re.findall(r'^    environment: "([^"]+)"$', workflows, flags=re.MULTILINE)
    assert environments
    readme = (GOLDEN / "README.gen.md").read_text(encoding="utf-8")
    assert _first_column(_section(readme, "GitHub environments")) == sorted(
        set(environments), key=environments.index
    )
    assert "vars." not in workflows
    assert "secrets." not in workflows
    assert "no repository variable and no repository secret" in _section(
        readme, "Variables and secrets"
    )


# trace: PRD-CICD-013, PRD-CICD-020
def test_only_prod_has_required_reviewers(ir: Ir) -> None:
    readme = _readme(ir)
    rows = re.findall(
        r"^\| `(\w+)` \| `[\w.]+` \| [^|]+ \| ([^|]+) \|$",
        _section(readme, "GitHub environments"),
        flags=re.MULTILINE,
    )
    assert rows == [("dev", "None"), ("staging", "None"), ("prod", "One or more")]
    assert "### Required reviewers of `prod`\n" in readme


# trace: PRD-CICD-013, PRD-IAC-028
def test_deployments_start_only_from_the_main_branch_and_the_release_tags(ir: Ir) -> None:
    section = _section(_readme(ir), "GitHub environments")
    assert "| `dev` | `main.gen.yml` | Branch `main` |" in section
    assert "| `prod` | `promote.gen.yml` | Branch `main`, tags `v*` |" in section


# trace: PRD-CICD-013
def test_main_branch_requires_the_checks_of_the_pull_request_workflow(ir: Ir) -> None:
    section = _section(_readme(ir), "Branch protection of the main branch")
    checks = re.findall(r"^   - `([^`]+)`$", section, flags=re.MULTILINE)
    pr_workflow = (GOLDEN / "pr.gen.yml").read_text(encoding="utf-8")
    assert checks == list(job_names(pr_workflow))
    assert checks == [
        "Validate the model",
        "Check the generated files",
        "Check the generated code",
        "Test orderApi",
        "Plan dev",
    ]
    assert "Add a branch ruleset for the branch `main`" in section
    assert '"Require a pull request before merging"' in section
    assert '"Block force pushes"' in section


# trace: PRD-CICD-013, PRD-IAC-026, PRD-IAC-029
def test_setup_applies_the_bootstrap_modules_before_the_github_settings(ir: Ir) -> None:
    steps = re.findall(r"^\d\. (.+)$", _section(_readme(ir), "Order of the setup"), re.MULTILINE)
    assert steps[0].startswith(
        "Apply the bootstrap root module of each account in `infra/bootstrap/`."
    )
    assert steps[1].startswith("Apply the tooling root module in `infra/tooling/`")
    assert steps[2] == "Make the GitHub settings in this file."


# trace: PRD-CICD-013
def test_no_infrastructure_folder_gives_only_the_github_settings(ir: Ir) -> None:
    configuration = Configuration(applications=CONFIGURATION.applications, pipelines=WORKFLOWS)
    readme = _readme(ir, configuration)
    assert "## Order of the setup" not in readme
    assert "## GitHub environments" not in readme
    assert "`Plan dev`" not in readme
    assert "## Branch protection of the main branch" in readme
    assert "DSML_INDEX_URL" not in readme


def test_job_names_reads_plain_and_quoted_names() -> None:
    text = (
        'jobs:\n  a:\n    name: Plain name\n  b:\n    name: "Quoted \\"name\\""\n  c:\n    x: 1\n'
    )
    assert job_names(text) == ("Plain name", 'Quoted "name"')
