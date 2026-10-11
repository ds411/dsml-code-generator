# trace: PRD-CICD-001, PRD-CORE-005, PRD-CORE-026
"""The pipeline generator: the GitHub Actions workflows of the product.

The generator reads only the IR and the configuration (PRD-CORE-026). It
writes its files in the folder of the key `pipelines.output`, normally
`.github/workflows`. Without this key, it writes no file. The workflows
run their commands in the folder of the configuration file. Thus the
configuration file must be in the root of the repository.

This module writes `pr.gen.yml` (PRD-CICD-001). The trigger is
`pull_request`. These are the jobs:

- `validate`: `dsml validate`, and the upload of the SARIF findings to
  GitHub code scanning (PRD-CICD-002).
- `generate-check`: `dsml generate --check` (PRD-CICD-003).
- `check-output`: `dsml check-output` (PRD-CICD-005).
- `test-<application>`: for each FastAPI application, the lockfile check,
  `uv sync --frozen`, ruff, pyright and pytest (PRD-CICD-004).
- `plan-dev`: `tofu plan` of the root module of the environment `dev` with
  the plan role, and the plan text in the job summary (PRD-CICD-006). The
  job is only in the workflow if the model has the environment `dev` and the
  configuration has the key `infrastructure.output`.

Until the toolchain GitHub Action of PRD-CORE-050 is available, the jobs
install the toolchain with `uv tool install`. The package index is the
URL in the repository variable `DSML_INDEX_URL`.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import PurePosixPath
from typing import Any, Final

from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.generate import fastapi
from dsml.generate import names as safe_names
from dsml.generate.header import PROG, FileType
from dsml.generate.infrastructure import names
from dsml.generate.infrastructure.generator import EnvironmentRoot, environment_roots
from dsml.generate.pipelines.workflow import job_symbols, pinned_action
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import PIPELINES, Kind, OutputFile
from dsml.ir.model import Element, Ir
from dsml.versions import Pin, load_baseline, pinned_version

PR_WORKFLOW: Final = "pr.gen.yml"
"""The file name of the pull request workflow."""

PLAN_ENVIRONMENT: Final = "dev"
"""The environment that the pull request workflow plans (PRD-CICD-006)."""

INDEX_VARIABLE: Final = "DSML_INDEX_URL"
"""The repository variable with the URL of the package index of the toolchain."""

ACTIONS: Final = {
    "checkout": "action-checkout",
    "configure_aws_credentials": "action-configure-aws-credentials",
    "setup_opentofu": "action-setup-opentofu",
    "setup_uv": "action-setup-uv",
    "upload_sarif": "action-upload-sarif",
}
"""The template name and the baseline item of each third-party action."""

MODEL_JOBS: Final = ("check-output", "generate-check", "validate")
"""The jobs that examine the full model. Their elements are the root packages."""


# trace: PRD-CICD-004
@dataclass(frozen=True, slots=True)
class ApplicationJob:
    """The test job of one application."""

    element: Element
    folder: str
    """The output folder of the application, or "." for the folder of the configuration file."""

    @property
    def job(self) -> str:
        """The job ID, for example `test-order-api`."""
        return f"test-{safe_names.kebab_case(self.element.name)}"

    @property
    def name(self) -> str:
        """The name of the application in the model."""
        return self.element.name


# trace: PRD-CICD-006, PRD-CICD-010
@dataclass(frozen=True, slots=True)
class PlanJob:
    """The plan job of one environment."""

    root: EnvironmentRoot
    folder: str
    """The folder of the root module of the environment."""

    @property
    def job(self) -> str:
        """The job ID, for example `plan-dev`."""
        return f"plan-{self.root.name}"

    @property
    def environment(self) -> str:
        """The name of the environment."""
        return self.root.name

    @property
    def region(self) -> str:
        """The AWS Region of the environment."""
        return self.root.region

    @property
    def role_arn(self) -> str:
        """The ARN of the plan role of the environment account (PRD-IAC-027)."""
        role = names.plan_role(self.root.product, self.root.name)
        return f"arn:aws:iam::{self.root.account_id}:role/{role}"


def root_packages(ir: Ir) -> tuple[str, ...]:
    """Give the identities of the packages that no element owns, sorted."""
    return tuple(
        sorted(
            element.identity
            for element in ir.elements
            if element.kind == "Package" and element.owner is None
        )
    )


# trace: PRD-CICD-004
def application_jobs(ir: Ir, configuration: Configuration) -> tuple[ApplicationJob, ...]:
    """Give the test job of each FastAPI application, sorted by identity."""
    jobs: list[ApplicationJob] = []
    for element in fastapi.applications(ir):
        folder = fastapi.output_folder(element, configuration).rstrip("/")
        jobs.append(ApplicationJob(element, folder or "."))
    seen: set[str] = set()
    for job in jobs:
        if job.job in seen:
            raise ToolchainError(
                f'Two applications give the job ID "{job.job}". Give them different names.'
            )
        seen.add(job.job)
    return tuple(jobs)


# trace: PRD-CICD-006
def plan_job(ir: Ir, configuration: Configuration) -> PlanJob | None:
    """Give the plan job of the environment `dev`, or `None`."""
    if configuration.infrastructure is None:
        return None
    for root in environment_roots(ir):
        if root.name == PLAN_ENVIRONMENT:
            folder = PurePosixPath(configuration.infrastructure, "envs", root.name)
            return PlanJob(root, folder.as_posix())
    return None


# trace: PRD-CICD-014, PRD-TOP-008
def actions(baseline: dict[str, Pin]) -> dict[str, str]:
    """Give the value of the key `uses:` of each third-party action, by template name."""
    return {name: pinned_action(item, baseline).uses for name, item in ACTIONS.items()}


def _value(baseline: dict[str, Pin], name: str) -> str:
    value = baseline[name].value
    if value is None:
        raise ToolchainError(f'The version baseline has no value for the item "{name}".')
    return value


# trace: PRD-CICD-001, PRD-CICD-002, PRD-CICD-003, PRD-CICD-004, PRD-CICD-005,
# PRD-CICD-006, PRD-CICD-010, PRD-CICD-011, PRD-CICD-014
def pr_data(ir: Ir, configuration: Configuration, version: str | None = None) -> dict[str, Any]:
    """Give the template data of `pr.gen.yml`.

    `version` is the toolchain version that the workflow installs. Without
    `version`, the function uses the version of the installed toolchain.
    """
    baseline = load_baseline()
    apps = application_jobs(ir, configuration)
    plan = plan_job(ir, configuration)
    elements = [*root_packages(ir), *(app.element.identity for app in apps)]
    if plan is not None:
        elements.append(plan.root.element.identity)
    return {
        "file_type": FileType.YAML.value,
        "elements": elements,
        "actions": actions(baseline),
        "applications": apps,
        "index_variable": INDEX_VARIABLE,
        "opentofu_version": pinned_version("opentofu", baseline),
        "plan": plan,
        "python_line": baseline["python"].line,
        "runner": _value(baseline, "github-runner"),
        "toolchain": PROG,
        "toolchain_version": metadata.version(PROG) if version is None else version,
        "uv_version": pinned_version("uv", baseline),
    }


# trace: PRD-CICD-001, PRD-CORE-005, PRD-CORE-026, PRD-TRACE-006
class PipelineGenerator:
    """The generator of the GitHub Actions workflows."""

    name = "pipelines"
    fixed_names: Collection[str] = ()

    def __init__(self, engine: TemplateEngine | None = None, version: str | None = None) -> None:
        self._engine = engine
        self._version = version

    def generate(
        self, ir: Ir, configuration: Configuration, parts: Collection[str] | None
    ) -> Sequence[OutputFile]:
        """Give the workflow files."""
        output = configuration.pipelines
        if output is None or (parts is not None and PIPELINES not in parts):
            return []
        engine = TemplateEngine() if self._engine is None else self._engine
        data = pr_data(ir, configuration, self._version)
        content = engine.render_bytes(f"pipelines/{PR_WORKFLOW}.j2", data)
        job_elements: dict[str, tuple[str, ...]] = dict.fromkeys(MODEL_JOBS, root_packages(ir))
        for app in data["applications"]:
            job_elements[app.job] = (app.element.identity,)
        if data["plan"] is not None:
            job_elements[data["plan"].job] = (data["plan"].root.element.identity,)
        symbols = job_symbols(content.decode("utf-8"), lambda job: job_elements.get(job, ()))
        path = PurePosixPath(output, PR_WORKFLOW).as_posix()
        return [OutputFile(path, content, Kind.GENERATED, PIPELINES, symbols)]
