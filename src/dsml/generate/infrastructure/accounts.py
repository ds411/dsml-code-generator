# trace: PRD-IAC-001, PRD-IAC-022, PRD-IAC-026, PRD-IAC-029, PRD-CORE-026
"""The tooling root module and the bootstrap root module of each AWS account.

The functions read only the IR and the configuration (PRD-CORE-026). They
write these folders in the infrastructure output folder (PRD-IAC-001):

- `tooling/`: the root module of the tooling account. It writes one ECR
  repository for each container application (PRD-IAC-022).
- `bootstrap/<account>/`: one root module for the tooling account and for
  each environment account. It writes the state bucket, the GitHub OIDC
  identity provider and the IAM roles for CI (PRD-IAC-026). It starts with
  local state, and its README gives the command that moves the state into
  the bucket (PRD-IAC-029).

The generator does not create AWS accounts (PRD-IAC-025). The model must
have a `#ToolingAccount` part. Without it, the functions write no file.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Final

from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.generate.header import FileType
from dsml.generate.infrastructure import hcl, names, policies
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import INFRASTRUCTURE, Kind, OutputFile
from dsml.ir.model import Element, Ir, StringValue
from dsml.versions import load_baseline, pinned_version

TOOLING_FILES: Final = ("backend", "main", "outputs", "providers", "variables", "versions")
"""The files of the tooling root module, without `.gen.tf`."""

BOOTSTRAP_FILES: Final = ("iam", "main", "outputs", "providers", "variables", "versions")
"""The HCL files of each bootstrap root module, without `.gen.tf`."""

README: Final = "README.gen.md"
"""The README of each bootstrap root module (PRD-IAC-029)."""

TEMPLATE_FOLDER: Final = "infrastructure"
"""The folder of the infrastructure templates."""


# trace: PRD-IAC-022, PRD-DSML-043
@dataclass(frozen=True, slots=True)
class Account:
    """The values of one AWS account: the tooling account or an environment account."""

    element: Element
    name: str
    """The name of the account in kebab case: `tooling` or the environment name."""
    product: str
    account_id: str
    region: str
    site_buckets: tuple[str, ...] = ()
    """The S3 buckets of the static sites of an environment account, sorted (PRD-IAC-021)."""

    @property
    def is_tooling(self) -> bool:
        """Tell if the account is the tooling account."""
        return self.element.kind == "ToolingAccount"


# trace: PRD-IAC-022
@dataclass(frozen=True, slots=True)
class Repository:
    """The ECR repository of one container application."""

    application: Element
    service: Element
    """The container service of the application."""
    product: str

    @property
    def address(self) -> str:
        """The HCL name of the repository resources."""
        return names.hcl_address(self.application.name)

    @property
    def name(self) -> str:
        """The AWS name of the repository."""
        return names.ecr_repository(self.product, self.application.name)


def _text_attribute(element: Element, name: str) -> str:
    """Give the text value of an attribute of an element."""
    for attribute in element.attributes:
        if attribute.name == name and isinstance(attribute.value, StringValue):
            return attribute.value.value
    raise ToolchainError(
        f'The element "{element.identity}" has no text value for the attribute "{name}".'
    )


# trace: PRD-DSML-043, PRD-IAC-022
def tooling_account(ir: Ir, product: Callable[[Element], str]) -> Account | None:
    """Give the tooling account of the IR, or `None` if the IR has none."""
    found = sorted(
        (element for element in ir.elements if element.kind == "ToolingAccount"),
        key=Element.sort_key,
    )
    if not found:
        return None
    if len(found) > 1:
        raise ToolchainError(f"The model must have one #ToolingAccount element, not {len(found)}.")
    element = found[0]
    return Account(
        element=element,
        name=names.TOOLING,
        product=product(element),
        account_id=_text_attribute(element, "accountId"),
        region=_text_attribute(element, "region"),
    )


# trace: PRD-IAC-022
def repositories(ir: Ir, product: Callable[[Element], str]) -> tuple[Repository, ...]:
    """Give the ECR repository of each container application, sorted by application identity.

    A container application is an application that is allocated to a
    `#ContainerService`.
    """
    by_identity = {element.identity: element for element in ir.elements}
    result: dict[str, Repository] = {}
    for link in sorted(ir.links, key=lambda link: link.sort_key()):
        if link.type != "allocate":
            continue
        application = by_identity.get(link.source)
        service = by_identity.get(link.target)
        if application is None or service is None:
            continue
        if application.kind == "Application" and service.kind == "ContainerService":
            result.setdefault(
                application.identity, Repository(application, service, product(application))
            )
    return tuple(result[identity] for identity in sorted(result))


def _base_data(account: Account, configuration: Configuration) -> dict[str, Any]:
    """Give the template data that all files of an account use."""
    baseline = load_baseline()
    required_version = baseline["hcl-required-version"].value
    if required_version is None:
        raise ToolchainError('The version baseline has no value for "hcl-required-version".')
    encryption = configuration.opentofu is not None and configuration.opentofu.state_encryption
    return {
        "elements": [account.element.identity],
        "calls": [],
        "account": account.name,
        "account_id": account.account_id,
        "element": names.tag_value(account.element.identity),
        "environment": account.name,
        "environment_tag": names.tag_value(account.name),
        "product": account.product,
        "product_tag": names.tag_value(account.product),
        "region": account.region,
        "state_bucket": names.state_bucket(account.product, account.name, account.account_id),
        "state_kms_alias": names.state_kms_alias(account.product, account.name),
        "aws_provider_version": pinned_version("aws-provider", baseline),
        "file_type": FileType.HCL.value,
        "required_version": required_version,
        "state_encryption": encryption,
    }


# trace: PRD-IAC-022, PRD-IAC-033
def tooling_data(
    tooling: Account,
    environments: Sequence[Account],
    found: Sequence[Repository],
    configuration: Configuration,
) -> dict[str, Any]:
    """Give the template data of the tooling root module."""
    data = _base_data(tooling, configuration)
    items: list[dict[str, Any]] = []
    for repository in found:
        roles = [
            "arn:aws:iam::{}:role/{}".format(
                environment.account_id,
                names.task_execution_role(
                    environment.product, environment.name, repository.service.name
                ),
            )
            for environment in environments
        ]
        accounts = [environment.account_id for environment in environments]
        items.append(
            {
                "address": repository.address,
                "name": repository.name,
                "element": names.tag_value(repository.application.identity),
                "policy": policies.pull_policy(f"{repository.address}_pull", accounts, roles)
                if environments
                else None,
            }
        )
    data["state_key"] = names.tooling_state_key()
    data["repositories"] = items
    return data


# trace: PRD-IAC-026, PRD-IAC-027, PRD-IAC-028, PRD-IAC-029, PRD-IAC-033
def bootstrap_data(
    account: Account, found: Sequence[Repository], configuration: Configuration
) -> dict[str, Any]:
    """Give the template data of the bootstrap root module of an account."""
    data = _base_data(account, configuration)
    encryption = bool(data["state_encryption"])
    roles: list[dict[str, Any]] = []
    if account.is_tooling:
        roles.append(
            {
                "address": "push",
                "name": names.push_role(account.product),
                "description": "The CI role that pushes images to ECR.",
                "trust": policies.push_trust(),
                "policy": policies.push_policy(
                    account.account_id, account.region, (item.name for item in found)
                ),
                "managed": None,
            }
        )
    else:
        plan = names.plan_role(account.product, account.name)
        deploy = names.deploy_role(account.product, account.name)
        roles.append(
            {
                "address": "plan",
                "name": plan,
                "description": "The CI role with read-only access for the plans of pull requests.",
                "trust": policies.plan_trust(),
                "policy": policies.plan_policy(account.name, encryption),
                "managed": policies.READ_ONLY_POLICY,
            }
        )
        roles.append(
            {
                "address": "deploy",
                "name": deploy,
                "description": f"The CI role that deploys the environment {account.name}.",
                "trust": policies.deploy_trust(account.name),
                "policy": policies.deploy_policy(
                    account.product,
                    account.name,
                    account.account_id,
                    account.region,
                    (plan, deploy),
                    encryption,
                    account.site_buckets,
                ),
                "managed": None,
            }
        )
    data.update(
        {
            "roles": sorted(roles, key=lambda role: role["address"]),
            "oidc_url": policies.OIDC_URL,
            "oidc_audience": policies.OIDC_AUDIENCE,
            "state_key": names.bootstrap_state_key(),
        }
    )
    return data


# trace: PRD-IAC-001, PRD-IAC-022, PRD-IAC-026, PRD-TRACE-006, PRD-TRACE-007
def account_files(
    engine: TemplateEngine,
    ir: Ir,
    configuration: Configuration,
    output: PurePosixPath,
    product: Callable[[Element], str],
    environments: Sequence[Account],
) -> list[OutputFile]:
    """Give the files of the tooling root module and of each bootstrap root module."""
    tooling = tooling_account(ir, product)
    if tooling is None:
        return []
    found = repositories(ir, product)
    files: list[OutputFile] = []

    data = tooling_data(tooling, environments, found, configuration)
    data["elements"] = [tooling.element.identity, *(item.application.identity for item in found)]
    owners = {
        address: (repository.application.identity,)
        for repository in found
        for address in (
            f"aws_ecr_repository.{repository.address}",
            f"aws_ecr_lifecycle_policy.{repository.address}",
            f"aws_ecr_repository_policy.{repository.address}",
            f"data.aws_iam_policy_document.{repository.address}_pull",
        )
    }
    for file in TOOLING_FILES:
        file_data = data if file == "main" else {**data, "elements": [tooling.element.identity]}
        files.append(
            _hcl_file(
                engine,
                f"tooling/{file}.gen.tf.j2",
                file_data,
                PurePosixPath(output, names.TOOLING, f"{file}.gen.tf"),
                lambda address: owners.get(address, (tooling.element.identity,)),
            )
        )

    for account in (tooling, *environments):
        data = bootstrap_data(account, found, configuration)
        folder = PurePosixPath(output, "bootstrap", account.name)
        identity = account.element.identity
        for file in BOOTSTRAP_FILES:
            files.append(
                _hcl_file(
                    engine,
                    f"bootstrap/{file}.gen.tf.j2",
                    data,
                    folder / f"{file}.gen.tf",
                    lambda address, identity=identity: (identity,),
                )
            )
        content = engine.render_bytes(f"{TEMPLATE_FOLDER}/bootstrap/{README}.j2", data)
        files.append(
            OutputFile((folder / README).as_posix(), content, Kind.GENERATED, INFRASTRUCTURE)
        )
    return files


def _hcl_file(
    engine: TemplateEngine,
    template: str,
    data: dict[str, Any],
    path: PurePosixPath,
    elements: Callable[[str], tuple[str, ...]],
) -> OutputFile:
    content = engine.render_bytes(f"{TEMPLATE_FOLDER}/{template}", data)
    symbols = hcl.block_symbols(content.decode("utf-8"), elements)
    return OutputFile(path.as_posix(), content, Kind.GENERATED, INFRASTRUCTURE, symbols)
