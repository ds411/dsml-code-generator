"""The build jobs and the deploy jobs of `main.gen.yml` and `promote.gen.yml`.

The values come only from the IR and the configuration (PRD-CORE-026). The
names of the roles, the repositories, the task families and the log groups
come from `dsml.generate.infrastructure.names`, so the workflows use the
same names as the generated HCL. The deploy jobs read the other values from
the outputs of the environment root module (PRD-IAC-010).

A container application gets an image build (`BuildJob`). A `react`
application on a static site gets a build of its static files
(`SiteBuildJob`). The deploy job of an environment deploys the two kinds.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import PurePosixPath
from typing import Final

from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.generate import fastapi
from dsml.generate import names as safe_names
from dsml.generate.infrastructure import names
from dsml.generate.infrastructure.accounts import Account, Repository, repositories, tooling_account
from dsml.generate.infrastructure.generator import EnvironmentRoot, environment_roots, product_name
from dsml.generate.infrastructure.modules import (
    directory_applications,
    image_variable,
    site_application,
)
from dsml.ir.model import Element, Ir

MAIN_ENVIRONMENT: Final = "dev"
"""The environment that `main.gen.yml` deploys to (PRD-CICD-007)."""

PROMOTE_ENVIRONMENTS: Final = ("staging", "prod")
"""The environments that `promote.gen.yml` deploys to, in their order (PRD-CICD-008)."""

MIGRATION_STREAM_PREFIX: Final = "migration"
"""The log stream prefix of the migration task in the container service module."""

STATIC_FILES: Final = "dist"
"""The folder that `pnpm build` writes the static files to (PRD-APP-233)."""

RUNTIME_CONFIGURATION: Final = "config.json"
"""The file of the site with the values of the environment (PRD-APP-230)."""

CONFIGURATION_KEYS: Final = ("apiBaseUrl", "region", "userPoolId", "appClientId", "loginDomain")
"""The keys of `/config.json`, in their order in the file (PRD-APP-230).

The React target must read these keys.
"""


# trace: PRD-CICD-007, PRD-CICD-010
@dataclass(frozen=True, slots=True)
class BuildJob:
    """The job that builds and pushes the image of one container application."""

    repository: Repository
    folder: str
    """The output folder of the application, or "." for the folder of the configuration file."""
    account: Account
    """The tooling account with the ECR repository."""

    @property
    def application(self) -> Element:
        """The application in the model."""
        return self.repository.application

    @property
    def job(self) -> str:
        """The job ID, for example `build-order-api`."""
        return f"build-{safe_names.kebab_case(self.application.name)}"

    @property
    def variable(self) -> str:
        """The root module variable of the image digest, for example `order_api_image_digest`."""
        return image_variable(self.application)

    @property
    def output(self) -> str:
        """The job output and the environment variable of the digest, for example
        `ORDER_API_IMAGE_DIGEST`.
        """
        return self.variable.upper()

    @property
    def registry(self) -> str:
        """The host name of the ECR registry of the tooling account."""
        return f"{self.account.account_id}.dkr.ecr.{self.account.region}.amazonaws.com"

    @property
    def region(self) -> str:
        """The AWS Region of the tooling account."""
        return self.account.region

    @property
    def role_arn(self) -> str:
        """The ARN of the push role of the tooling account (PRD-IAC-028)."""
        role = names.push_role(self.repository.product)
        return f"arn:aws:iam::{self.account.account_id}:role/{role}"


# trace: PRD-CICD-007, PRD-APP-233
@dataclass(frozen=True, slots=True)
class SiteBuildJob:
    """The job that builds the static files of one `react` application one time."""

    application: Element
    site: Element
    """The static site of the application."""
    folder: str
    """The output folder of the application, or "." for the folder of the configuration file."""

    @property
    def job(self) -> str:
        """The job ID, for example `build-order-portal`."""
        return f"build-{safe_names.kebab_case(self.application.name)}"

    @property
    def label(self) -> str:
        """The name of the application in kebab case, for the job summary."""
        return safe_names.kebab_case(self.application.name)

    @property
    def artifact(self) -> str:
        """The name of the workflow artifact, for example `static-files-order-portal`."""
        return f"static-files-{self.label}"

    @property
    def files(self) -> str:
        """The folder of the static files, for example `apps/order-portal/dist`."""
        return PurePosixPath(self.folder, STATIC_FILES).as_posix()

    @property
    def package_json(self) -> str:
        """The path of `package.json` of the application, for the pnpm setup action."""
        return PurePosixPath(self.folder, "package.json").as_posix()

    @property
    def output(self) -> str:
        """The job output and the environment variable of the artifact ID, for example
        `ORDER_PORTAL_ARTIFACT_ID`.
        """
        return f"{names.hcl_address(self.application.name).upper()}_ARTIFACT_ID"

    @property
    def run_output(self) -> str:
        """The environment variable of the workflow run of the artifact, for example
        `ORDER_PORTAL_RUN_ID`.
        """
        return f"{names.hcl_address(self.application.name).upper()}_RUN_ID"


# trace: PRD-CICD-017, PRD-CICD-018
@dataclass(frozen=True, slots=True)
class Rollout:
    """The migration and the rollout of one container service in one environment."""

    service: Element
    application: Element
    product: str
    environment: str
    migrates: bool
    """True if the service uses a database. Then the job runs the migration task."""

    @property
    def label(self) -> str:
        """The name of the application in kebab case, for the job summary."""
        return safe_names.kebab_case(self.application.name)

    @property
    def address(self) -> str:
        """The HCL address of the module call, the prefix of its root module outputs."""
        return names.hcl_address(self.service.name)

    @property
    def task_family(self) -> str:
        """The family of the task definition of the service."""
        element = safe_names.kebab_case(self.service.name)
        return names.aws_name(self.product, self.environment, element, "ecs_task_definition")

    @property
    def log_group(self) -> str:
        """The CloudWatch log group of the service and its migration task."""
        element = safe_names.kebab_case(self.service.name)
        return names.aws_name(self.product, self.environment, element, "cloudwatch_log_group")


# trace: PRD-CICD-016, PRD-CICD-021
@dataclass(frozen=True, slots=True)
class Digest:
    """The image digest of one application in a deploy job."""

    name: str
    """The environment variable of the digest in the job, for example `ORDER_API_IMAGE_DIGEST`."""
    variable: str
    """The root module variable, for example `order_api_image_digest`."""
    expression: str
    """The GitHub Actions expression that gives the digest, without `${{` and `}}`."""
    label: str
    """The name of the application in kebab case, for the job summary."""


# trace: PRD-CICD-019, PRD-APP-230
@dataclass(frozen=True, slots=True)
class SiteDeploy:
    """The deployment of the static files of one `react` application in one environment.

    The names are the prefixes of the root module outputs (PRD-IAC-010).
    """

    build: SiteBuildJob
    site: str
    """The HCL address of the static site."""
    api: str
    """The HCL address of the container service of the called application."""
    directory: str
    """The HCL address of the user directory of the application."""
    artifact: str
    """The GitHub Actions expression that gives the artifact ID, without `${{` and `}}`."""
    run: str
    """The GitHub Actions expression that gives the workflow run of the artifact."""

    @property
    def client(self) -> str:
        """The key of the app client of the application in `<directory>_app_client_ids`."""
        return names.hcl_address(self.build.application.name)

    @property
    def path(self) -> str:
        """The folder of the downloaded static files in the temporary folder of the runner."""
        return f"static-files/{self.build.label}"


# trace: PRD-CICD-009, PRD-CICD-010, PRD-CICD-012, PRD-CICD-016
@dataclass(frozen=True, slots=True)
class DeployJob:
    """The deploy job of one environment."""

    root: EnvironmentRoot
    folder: str
    """The folder of the root module of the environment."""
    needs: tuple[str, ...]
    """The jobs that must succeed before this job starts."""
    digests: tuple[Digest, ...]
    commit: str
    """The expression of the commit of the build."""
    rollouts: tuple[Rollout, ...]
    sites: tuple[SiteDeploy, ...] = ()
    other_run: bool = False
    """True if the static files come from a different workflow run: the main build."""

    @property
    def job(self) -> str:
        """The job ID, for example `deploy-dev`."""
        return f"deploy-{self.root.name}"

    @property
    def environment(self) -> str:
        """The name of the environment and of its GitHub environment."""
        return self.root.name

    @property
    def concurrency(self) -> str:
        """The concurrency group. All workflows use the same group for one environment."""
        return f"deploy-{self.root.name}"

    @property
    def region(self) -> str:
        """The AWS Region of the environment."""
        return self.root.region

    @property
    def role_arn(self) -> str:
        """The ARN of the deploy role of the environment account (PRD-IAC-027)."""
        role = names.deploy_role(self.root.product, self.root.name)
        return f"arn:aws:iam::{self.root.account_id}:role/{role}"


# trace: PRD-CICD-007
def build_jobs(ir: Ir, configuration: Configuration) -> tuple[BuildJob, ...]:
    """Give the build job of each container application, sorted by application identity.

    Without the key `infrastructure.output`, there is no ECR repository and
    thus no build job.
    """
    if configuration.infrastructure is None:
        return ()
    product = partial(product_name, ir)
    found = repositories(ir, product)
    if not found:
        return ()
    account = tooling_account(ir, product)
    if account is None:
        raise ToolchainError(
            "The model has container applications but no #ToolingAccount element. "
            "Add a #ToolingAccount element for the ECR repositories."
        )
    jobs: list[BuildJob] = []
    for repository in found:
        folder = fastapi.output_folder(repository.application, configuration).rstrip("/")
        jobs.append(BuildJob(repository, folder or ".", account))
    check_job_ids(job.job for job in jobs)
    return tuple(jobs)


# trace: PRD-CICD-007, PRD-IAC-021
def site_builds(ir: Ir, configuration: Configuration) -> tuple[SiteBuildJob, ...]:
    """Give the build job of each `react` application on a static site, sorted by identity.

    Without the key `infrastructure.output`, there is no static site and
    thus no build job.
    """
    if configuration.infrastructure is None:
        return ()
    jobs: list[SiteBuildJob] = []
    for site in sorted(
        (element for element in ir.elements if element.kind == "StaticSite"), key=Element.sort_key
    ):
        application = site_application(ir, site)
        folder = fastapi.output_folder(application, configuration).rstrip("/")
        jobs.append(SiteBuildJob(application, site, folder or "."))
    return tuple(sorted(jobs, key=lambda job: job.application.identity))


def check_job_ids(job_ids: Iterable[str]) -> None:
    """Make sure that two jobs of applications do not have the same job ID."""
    seen: set[str] = set()
    for job in job_ids:
        if job in seen:
            raise ToolchainError(
                f'Two applications give the job ID "{job}". Give them different names.'
            )
        seen.add(job)


def _api_service(ir: Ir, application: Element) -> Element:
    """Give the container service of the one application that a `react` application calls.

    The deploy job writes the API URL of this service in `/config.json`
    (PRD-APP-230).
    """
    by_identity = {element.identity: element for element in ir.elements}
    services: list[Element] = []
    for link in ir.links:
        if link.type != "calls" or link.source != application.identity:
            continue
        called = by_identity.get(link.target)
        if called is None or called.kind != "Application":
            continue
        services.extend(
            by_identity[item.target]
            for item in ir.links
            if item.type == "allocate"
            and item.source == called.identity
            and item.target in by_identity
            and by_identity[item.target].kind == "ContainerService"
        )
    if len(services) != 1:
        raise ToolchainError(
            f'The application "{application.identity}" must call one application on a '
            f"container service, not {len(services)}. The deploy job writes the API URL of "
            "this service in /config.json."
        )
    return services[0]


def _user_directory(ir: Ir, application: Element) -> Element:
    """Give the one user directory of a `react` application (PRD-APP-230)."""
    found = sorted(
        (
            element
            for element in ir.elements
            if element.kind == "UserDirectory"
            and application in directory_applications(ir, element)
        ),
        key=Element.sort_key,
    )
    if len(found) != 1:
        raise ToolchainError(
            f'The application "{application.identity}" must use one user directory, not '
            f"{len(found)}. The deploy job writes its user pool in /config.json."
        )
    return found[0]


# trace: PRD-CICD-019, PRD-APP-230
def site_deploys(
    ir: Ir, sites: Sequence[SiteBuildJob], artifact: str, run: str
) -> tuple[SiteDeploy, ...]:
    """Give the deployment of the static files of each site build.

    `artifact` and `run` are the expressions of the artifact ID and of the
    workflow run, with `{job}`, `{output}` and `{run_output}` in them.
    """
    return tuple(
        SiteDeploy(
            build=site,
            site=names.hcl_address(site.site.name),
            api=names.hcl_address(_api_service(ir, site.application).name),
            directory=names.hcl_address(_user_directory(ir, site.application).name),
            artifact=artifact.format(job=site.job, output=site.output),
            run=run.format(job=site.job, output=site.run_output),
        )
        for site in sites
    )


def _uses_database(ir: Ir, service: Element) -> bool:
    """Tell if a container service uses (`#Uses`) a relational database."""
    kinds = {element.identity: element.kind for element in ir.elements}
    return any(
        link.type == "uses"
        and link.source == service.identity
        and kinds.get(link.target) == "RelationalDatabase"
        for link in ir.links
    )


# trace: PRD-CICD-017, PRD-CICD-018
def rollouts(ir: Ir, root: EnvironmentRoot, builds: tuple[BuildJob, ...]) -> tuple[Rollout, ...]:
    """Give the rollout of each container service in an environment, sorted by service identity."""
    return tuple(
        sorted(
            (
                Rollout(
                    service=build.repository.service,
                    application=build.application,
                    product=root.product,
                    environment=root.name,
                    migrates=_uses_database(ir, build.repository.service),
                )
                for build in builds
            ),
            key=lambda rollout: rollout.service.identity,
        )
    )


# trace: PRD-CICD-009, PRD-CICD-012, PRD-CICD-016, PRD-CICD-019
def deploy_jobs(
    ir: Ir,
    configuration: Configuration,
    environments: tuple[str, ...],
    builds: tuple[BuildJob, ...],
    digest: str,
    commit: str,
    first_needs: tuple[str, ...],
    sites: tuple[SiteDeploy, ...] = (),
    other_run: bool = False,
) -> tuple[DeployJob, ...]:
    """Give the deploy jobs of the environments that the model has, in the order of `environments`.

    `digest` is the expression of the digest of a build job, with `{job}`
    and `{output}` in it. `commit` is the expression of the commit of the
    build. `sites` gives the static files to deploy. `other_run` is true if
    the static files come from a different workflow run. The first job
    needs the jobs of `first_needs`. Each next job also needs the job
    before it.
    """
    if configuration.infrastructure is None or not (builds or sites):
        return ()
    roots = {root.name: root for root in environment_roots(ir)}
    jobs: list[DeployJob] = []
    for name in environments:
        root = roots.get(name)
        if root is None:
            continue
        needs = first_needs if not jobs else (*first_needs, jobs[-1].job)
        folder = PurePosixPath(configuration.infrastructure, "envs", root.name).as_posix()
        digests = tuple(
            Digest(
                name=build.output,
                variable=build.variable,
                expression=digest.format(job=build.job, output=build.output),
                label=safe_names.kebab_case(build.application.name),
            )
            for build in builds
        )
        jobs.append(
            DeployJob(
                root,
                folder,
                needs,
                digests,
                commit,
                rollouts(ir, root, builds),
                sites,
                other_run,
            )
        )
    return tuple(jobs)
