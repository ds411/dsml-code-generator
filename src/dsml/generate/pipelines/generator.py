# trace: PRD-CICD-001, PRD-CORE-005, PRD-CORE-026
"""The pipeline generator: the GitHub Actions workflows of the product.

The generator reads only the IR and the configuration (PRD-CORE-026). It
writes its files in the folder of the key `pipelines.output`, normally
`.github/workflows`. Without this key, it writes no file. The workflows
run their commands in the folder of the configuration file. Thus the
configuration file must be in the root of the repository.

This module writes `pr.gen.yml`, `main.gen.yml` and `promote.gen.yml`
(PRD-CICD-001), and `README.gen.md` with the repository settings that the
workflows need (PRD-CICD-013). The trigger of `pr.gen.yml` is
`pull_request`. These are its jobs:

- `validate`: `dsml validate`, and the upload of the SARIF findings to
  GitHub code scanning (PRD-CICD-002).
- `generate-check`: `dsml generate --check` (PRD-CICD-003).
- `check-output`: `dsml check-output` (PRD-CICD-005).
- `test-<application>`: for each FastAPI application, the lockfile check,
  `uv sync --frozen`, ruff, pyright and pytest. For each `react` and
  each `nextjs` application, `pnpm install --frozen-lockfile`, the type
  checker, the linters, the format check and the tests (PRD-CICD-004).
- `plan-dev`: `tofu plan` of the root module of the environment `dev` with
  the plan role, and the plan text in the job summary (PRD-CICD-006). The
  job is only in the workflow if the model has the environment `dev` and the
  configuration has the key `infrastructure.output`.

`main.gen.yml` and `promote.gen.yml` are only in the output if the
configuration has the key `infrastructure.output` and the model has a
container application or a static site. `main.gen.yml` builds each image
and the static files of each static site one time, and deploys them to
`dev`. `promote.gen.yml` deploys the images and the static files of one
main build to `staging`, then to `prod`. The module
`dsml.generate.pipelines.deploy` gives their jobs.

Each job that runs `dsml` uses the toolchain GitHub Action of
PRD-CORE-050, at the release tag of the toolchain version that wrote the
workflow. The action installs the wheel from the GitHub release (Q63).
The job `check-output` also installs the language tools that
`dsml check-output` runs, at the versions of the version baseline.
"""

import json
import re
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
from dsml.generate.infrastructure.modules import CONTAINER_NAME
from dsml.generate.pipelines.deploy import (
    MAIN_ENVIRONMENT,
    MIGRATION_STREAM_PREFIX,
    PROMOTE_ENVIRONMENTS,
    RUNTIME_CONFIGURATION,
    BuildJob,
    DeployJob,
    SiteBuildJob,
    build_jobs,
    check_job_ids,
    deploy_jobs,
    site_builds,
    site_deploys,
)
from dsml.generate.pipelines.workflow import job_symbols, pinned_action
from dsml.generate.templates import TemplateEngine
from dsml.generate.trace import Symbol
from dsml.generate.writer import PIPELINES, Kind, OutputFile
from dsml.ir.model import Element, EnumValue, Ir
from dsml.versions import Pin, load_baseline, pinned_version

PR_WORKFLOW: Final = "pr.gen.yml"
"""The file name of the pull request workflow."""

MAIN_WORKFLOW: Final = "main.gen.yml"
"""The file name of the main workflow."""

PROMOTE_WORKFLOW: Final = "promote.gen.yml"
"""The file name of the promote workflow."""

README: Final = "README.gen.md"
"""The file name of the README with the repository settings (PRD-CICD-013)."""

REVIEWED_ENVIRONMENT: Final = "prod"
"""The GitHub environment that must have required reviewers (PRD-CICD-013, PRD-CICD-020)."""

MAIN_BRANCH: Final = "main"
"""The main branch. The trust policy of the push role permits only this branch (PRD-IAC-028)."""

RELEASE_TAGS: Final = "v*"
"""The pattern of the release tags that start `promote.gen.yml` (PRD-CICD-001)."""

FIND_BUILD_JOB: Final = "find-build"
"""The job of `promote.gen.yml` that finds the image digests and the static files of a build."""

PNPM_TARGETS: Final = frozenset({"nextjs", "react"})
"""The targets of the applications that pnpm builds and tests (PRD-CICD-004)."""

PLAN_ENVIRONMENT: Final = "dev"
"""The environment that the pull request workflow plans (PRD-CICD-006)."""

TOOLCHAIN_ACTION: Final = "ds411/dsml-code-generator"
"""The repository of the toolchain GitHub Action (PRD-CORE-050)."""

ACTIONS: Final = {
    "checkout": "action-checkout",
    "configure_aws_credentials": "action-configure-aws-credentials",
    "download_artifact": "action-download-artifact",
    "setup_node": "action-setup-node",
    "setup_opentofu": "action-setup-opentofu",
    "setup_pnpm": "action-setup-pnpm",
    "setup_uv": "action-setup-uv",
    "upload_artifact": "action-upload-artifact",
    "upload_sarif": "action-upload-sarif",
}
"""The template name and the baseline item of each third-party action."""

_JOB_NAME = re.compile(r"^  [A-Za-z_][A-Za-z0-9_-]*:\n    name: (.+)$", re.MULTILINE)

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

    @property
    def package_json(self) -> str:
        """The path of `package.json` of the application, for the pnpm setup action."""
        return PurePosixPath(self.folder, "package.json").as_posix()


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


def _uses_pnpm(element: Element) -> bool:
    return any(
        attribute.name == "target"
        and isinstance(attribute.value, EnumValue)
        and attribute.value.literal in PNPM_TARGETS
        for attribute in element.attributes
    )


def _jobs(ir: Ir, configuration: Configuration, elements: list[Element]) -> list[ApplicationJob]:
    jobs: list[ApplicationJob] = []
    for element in elements:
        folder = fastapi.output_folder(element, configuration).rstrip("/")
        jobs.append(ApplicationJob(element, folder or "."))
    return jobs


# trace: PRD-CICD-004
def application_jobs(ir: Ir, configuration: Configuration) -> tuple[ApplicationJob, ...]:
    """Give the test job of each FastAPI application, sorted by identity."""
    jobs = _jobs(ir, configuration, fastapi.applications(ir))
    check_job_ids(job.job for job in (*jobs, *pnpm_jobs(ir, configuration)))
    return tuple(jobs)


# trace: PRD-CICD-004
def pnpm_jobs(ir: Ir, configuration: Configuration) -> tuple[ApplicationJob, ...]:
    """Give the test job of each `react` and each `nextjs` application, sorted by identity."""
    elements = sorted(
        (item for item in ir.elements if item.kind == "Application" and _uses_pnpm(item)),
        key=Element.sort_key,
    )
    return tuple(_jobs(ir, configuration, elements))


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


# trace: PRD-CORE-050, PRD-CICD-014
def toolchain_action(version: str) -> str:
    """Give the value of the key `uses:` of the toolchain action for a toolchain version.

    The value is the release tag `v<version>`, not a commit SHA. The
    toolchain cannot know the commit of its own release tag, because the
    tag comes after the commit. PRD-CICD-014 is for third-party actions.
    """
    return f"{TOOLCHAIN_ACTION}@v{version}"


# trace: PRD-CICD-005, PRD-CORE-011, PRD-IAC-038
def check_tools(baseline: dict[str, Pin]) -> dict[str, str]:
    """Give the versions and the SHA-256 hashes of the tools of `dsml check-output`."""
    return {
        "pyright": pinned_version("pyright", baseline),
        "ruff": pinned_version("ruff", baseline),
        "ruleset": pinned_version("tflint-ruleset-aws", baseline),
        "ruleset_sha256": _value(baseline, "tflint-ruleset-aws-sha256"),
        "tflint": pinned_version("tflint", baseline),
        "tflint_sha256": _value(baseline, "tflint-sha256"),
    }


# trace: PRD-CICD-001, PRD-CICD-002, PRD-CICD-003, PRD-CICD-004, PRD-CICD-005
# trace: PRD-CICD-006, PRD-CICD-010, PRD-CICD-011, PRD-CICD-014, PRD-CORE-050
def pr_data(ir: Ir, configuration: Configuration, version: str | None = None) -> dict[str, Any]:
    """Give the template data of `pr.gen.yml`.

    `version` is the toolchain version that the workflow installs. Without
    `version`, the function uses the version of the installed toolchain.
    """
    baseline = load_baseline()
    toolchain_version = metadata.version(PROG) if version is None else version
    apps = application_jobs(ir, configuration)
    web = pnpm_jobs(ir, configuration)
    plan = plan_job(ir, configuration)
    elements = [*root_packages(ir), *(app.element.identity for app in (*apps, *web))]
    if plan is not None:
        elements.append(plan.root.element.identity)
    return {
        "file_type": FileType.YAML.value,
        "elements": elements,
        "actions": actions(baseline),
        "applications": apps,
        "pnpm_applications": web,
        "node_version": pinned_version("node", baseline),
        "pnpm_version": pinned_version("pnpm", baseline),
        "check_infrastructure": configuration.infrastructure is not None,
        "opentofu_version": pinned_version("opentofu", baseline),
        "plan": plan,
        "python_line": baseline["python"].line,
        "runner": _value(baseline, "github-runner"),
        "tools": check_tools(baseline),
        "toolchain_action": toolchain_action(toolchain_version),
        "toolchain_version": toolchain_version,
        "uv_version": pinned_version("uv", baseline),
    }


# trace: PRD-CICD-008, PRD-CICD-010
@dataclass(frozen=True, slots=True)
class FindBuildJob:
    """The job of `promote.gen.yml` that finds the image digests and the static files of a
    main build.
    """

    build: BuildJob | None
    """A build job, or `None` if the model has no container application. All build jobs use
    the same tooling account and push role."""

    @property
    def job(self) -> str:
        """The job ID."""
        return FIND_BUILD_JOB

    @property
    def role_arn(self) -> str:
        """The ARN of the push role of the tooling account (PRD-IAC-028)."""
        if self.build is None:
            raise ToolchainError("The model has no container application.")
        return self.build.role_arn

    @property
    def region(self) -> str:
        """The AWS Region of the tooling account."""
        if self.build is None:
            raise ToolchainError("The model has no container application.")
        return self.build.region


def _base_data(baseline: dict[str, Pin]) -> dict[str, Any]:
    """Give the template data that the workflows with deploy jobs use."""
    return {
        "file_type": FileType.YAML.value,
        "actions": actions(baseline),
        "container_name": CONTAINER_NAME,
        "migration_stream_prefix": MIGRATION_STREAM_PREFIX,
        "node_version": pinned_version("node", baseline),
        "opentofu_version": pinned_version("opentofu", baseline),
        "pnpm_version": pinned_version("pnpm", baseline),
        "runner": _value(baseline, "github-runner"),
        "runtime_configuration": RUNTIME_CONFIGURATION,
    }


def _deploy_elements(
    builds: Sequence[BuildJob], sites: Sequence[SiteBuildJob], deploys: Sequence[DeployJob]
) -> list[str]:
    """Give the identities of the elements of a workflow with deploy jobs, sorted."""
    identities = {build.account.element.identity for build in builds}
    for build in builds:
        identities.update((build.application.identity, build.repository.service.identity))
    for site in sites:
        identities.update((site.application.identity, site.site.identity))
    identities.update(deploy.root.element.identity for deploy in deploys)
    return sorted(identities)


# trace: PRD-CICD-001, PRD-CICD-007, PRD-CICD-009, PRD-CICD-010, PRD-CICD-011
# trace: PRD-CICD-012, PRD-CICD-014, PRD-CICD-016, PRD-CICD-017, PRD-CICD-018, PRD-CICD-019
# trace: PRD-CICD-021, PRD-APP-233
def main_data(ir: Ir, configuration: Configuration) -> dict[str, Any] | None:
    """Give the template data of `main.gen.yml`, or `None` if the workflow has no build job.

    The deploy job downloads the static files from the build jobs of the
    same workflow run.
    """
    builds = build_jobs(ir, configuration)
    sites = site_builds(ir, configuration)
    if not builds and not sites:
        return None
    check_job_ids(job.job for job in (*builds, *sites))
    deploys = deploy_jobs(
        ir,
        configuration,
        (MAIN_ENVIRONMENT,),
        builds,
        digest="needs.{job}.outputs.{output}",
        commit="github.sha",
        first_needs=tuple(build.job for build in (*builds, *sites)),
        sites=site_deploys(ir, sites, artifact="needs.{job}.outputs.{output}", run="github.run_id"),
    )
    return {
        **_base_data(load_baseline()),
        "elements": _deploy_elements(builds, sites, deploys),
        "builds": builds,
        "sites": sites,
        "deploys": deploys,
        "main_branch": MAIN_BRANCH,
    }


# trace: PRD-CICD-001, PRD-CICD-008, PRD-CICD-009, PRD-CICD-010, PRD-CICD-011
# trace: PRD-CICD-012, PRD-CICD-014, PRD-CICD-016, PRD-CICD-017, PRD-CICD-018, PRD-CICD-019
# trace: PRD-CICD-020, PRD-CICD-021
def promote_data(ir: Ir, configuration: Configuration) -> dict[str, Any] | None:
    """Give the template data of `promote.gen.yml`, or `None` if the workflow has no deploy job.

    The first deploy job needs the job that finds the build. Each next
    deploy job also needs the deploy job before it. Thus prod starts only
    after the deployment of the same build to staging succeeded
    (PRD-CICD-020). The deploy jobs download the static files from the
    workflow run of the main build. The workflow builds nothing
    (PRD-CICD-008).
    """
    builds = build_jobs(ir, configuration)
    sites = site_builds(ir, configuration)
    find = f"needs.{FIND_BUILD_JOB}.outputs.{{output}}"
    deploys = deploy_jobs(
        ir,
        configuration,
        PROMOTE_ENVIRONMENTS,
        builds,
        digest=find,
        commit=f"needs.{FIND_BUILD_JOB}.outputs.commit",
        first_needs=(FIND_BUILD_JOB,),
        sites=site_deploys(ir, sites, artifact=find, run=find),
        other_run=True,
    )
    if not deploys:
        return None
    return {
        **_base_data(load_baseline()),
        "elements": _deploy_elements(builds, sites, deploys),
        "builds": builds,
        "sites": sites,
        "deploys": deploys,
        "main_branch": MAIN_BRANCH,
        "release_tags": RELEASE_TAGS,
        "resolve": FindBuildJob(builds[0] if builds else None),
    }


def _deploy_symbols(content: bytes, data: dict[str, Any]) -> tuple[Symbol, ...]:
    """Give the job symbols of a workflow with deploy jobs.

    A build job gives the application. The job that finds the build gives
    the applications. A deploy job gives its environment.
    """
    builds: Sequence[BuildJob | SiteBuildJob] = (*data["builds"], *data["sites"])
    job_elements: dict[str, tuple[str, ...]] = {
        build.job: (build.application.identity,) for build in builds
    }
    job_elements[FIND_BUILD_JOB] = tuple(sorted(build.application.identity for build in builds))
    for deploy in data["deploys"]:
        job_elements[deploy.job] = (deploy.root.element.identity,)
    return job_symbols(content.decode("utf-8"), lambda job: job_elements.get(job, ()))


# trace: PRD-CICD-013
def job_names(content: str) -> tuple[str, ...]:
    """Give the value of the key `name:` of each job of a workflow, in the order of the jobs.

    GitHub gives this name to the check of the job.
    """
    return tuple(
        json.loads(value) if value.startswith('"') else value
        for value in _JOB_NAME.findall(content)
    )


# trace: PRD-CICD-013
@dataclass(frozen=True, slots=True)
class GitHubEnvironment:
    """A GitHub environment that a deploy job uses."""

    name: str
    workflow: str
    """The file name of the workflow with the deploy job."""
    refs: tuple[str, ...]
    """The branches and the tags that can deploy to the environment."""

    @property
    def reviewed(self) -> bool:
        """Tell if the environment must have required reviewers."""
        return self.name == REVIEWED_ENVIRONMENT


# trace: PRD-CICD-013, PRD-CICD-012, PRD-CICD-020
def readme_data(
    configuration: Configuration,
    pr: dict[str, Any],
    pr_content: bytes,
    main: dict[str, Any] | None,
    promote: dict[str, Any] | None,
) -> dict[str, Any]:
    """Give the template data of `README.gen.md`.

    The README gives the GitHub environments of the deploy jobs and the
    required status checks of the main branch (the jobs of `pr.gen.yml`).
    The workflows use no repository variable. The deploy jobs can start
    only from the main branch and from the release tags. The trust policy of the push role
    permits only these (PRD-IAC-028).
    """
    environments: list[GitHubEnvironment] = []
    for workflow, data, refs in (
        (MAIN_WORKFLOW, main, (f"Branch `{MAIN_BRANCH}`",)),
        (PROMOTE_WORKFLOW, promote, (f"Branch `{MAIN_BRANCH}`", f"tags `{RELEASE_TAGS}`")),
    ):
        if data is not None:
            environments.extend(
                GitHubEnvironment(deploy.environment, workflow, refs) for deploy in data["deploys"]
            )
    return {
        "checks": job_names(pr_content.decode("utf-8")),
        "environments": environments,
        "infrastructure": (
            None
            if configuration.infrastructure is None
            else configuration.infrastructure.as_posix()
        ),
        "plan": pr["plan"] is not None,
        "main_branch": MAIN_BRANCH,
        "pr_workflow": PR_WORKFLOW,
        "tooling": main is not None and bool(main["builds"]),
    }


# trace: PRD-CICD-001, PRD-CICD-013, PRD-CORE-005, PRD-CORE-026, PRD-TRACE-006
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
        """Give the workflow files and the README."""
        output = configuration.pipelines
        if output is None or (parts is not None and PIPELINES not in parts):
            return []
        engine = TemplateEngine() if self._engine is None else self._engine
        data = pr_data(ir, configuration, self._version)
        content = engine.render_bytes(f"pipelines/{PR_WORKFLOW}.j2", data)
        job_elements: dict[str, tuple[str, ...]] = dict.fromkeys(MODEL_JOBS, root_packages(ir))
        for app in (*data["applications"], *data["pnpm_applications"]):
            job_elements[app.job] = (app.element.identity,)
        if data["plan"] is not None:
            job_elements[data["plan"].job] = (data["plan"].root.element.identity,)
        symbols = job_symbols(content.decode("utf-8"), lambda job: job_elements.get(job, ()))
        files = [
            OutputFile(
                PurePosixPath(output, PR_WORKFLOW).as_posix(),
                content,
                Kind.GENERATED,
                PIPELINES,
                symbols,
            )
        ]
        main = main_data(ir, configuration)
        promote = promote_data(ir, configuration)
        readme = readme_data(configuration, data, content, main, promote)
        for name, workflow_data in ((MAIN_WORKFLOW, main), (PROMOTE_WORKFLOW, promote)):
            if workflow_data is None:
                continue
            content = engine.render_bytes(f"pipelines/{name}.j2", workflow_data)
            files.append(
                OutputFile(
                    PurePosixPath(output, name).as_posix(),
                    content,
                    Kind.GENERATED,
                    PIPELINES,
                    _deploy_symbols(content, workflow_data),
                )
            )
        files.append(
            OutputFile(
                PurePosixPath(output, README).as_posix(),
                engine.render_bytes(f"pipelines/{README}.j2", readme),
                Kind.GENERATED,
                PIPELINES,
            )
        )
        return files
