# trace: PRD-IAC-001, PRD-IAC-002, PRD-IAC-023, PRD-CORE-026
"""The infrastructure generator: one root module for each environment.

The generator reads only the IR and the configuration (PRD-CORE-026). It
writes its files in the folder of the key `infrastructure.output`. Without
this key, or with no environment in the model, it writes no file.

For each environment, the folder `envs/<environment>/` gets these files
(PRD-IAC-001):

- `versions.gen.tf`: the `required_version` and the exact AWS provider
  version of the version baseline (PRD-IAC-003, PRD-IAC-005).
- `backend.gen.tf`: the S3 backend with S3 native state locks and
  encryption. The state bucket is in the account of the environment
  (PRD-IAC-006). With the IaC option `iac.opentofu.state_encryption`, the
  file also has the OpenTofu state encryption, and a comment that names
  OpenTofu as the only tool that accepts it (PRD-IAC-004).
- `providers.gen.tf`: the AWS provider with `allowed_account_ids` and
  `default_tags` (PRD-IAC-024, PRD-IAC-035).
- `main.gen.tf`: the values of the environment. The local modules of the
  environment come in this file.
- `variables.gen.tf`: the variable `model_commit` (PRD-IAC-036).
- `outputs.gen.tf`: the values that the pipelines need (PRD-IAC-010).

The module `dsml.generate.infrastructure.accounts` gives the files of the
folders `tooling/` and `bootstrap/<account>/` (PRD-IAC-022, PRD-IAC-026).

All environments use the same templates. Only the attributes of the
environment make two root modules different (PRD-IAC-023).
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Final

from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.generate import names as safe_names
from dsml.generate.header import FileType
from dsml.generate.infrastructure import hcl, names
from dsml.generate.infrastructure.accounts import Account, account_files
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import INFRASTRUCTURE, Kind, OutputFile
from dsml.ir.environments import environments
from dsml.ir.model import Element, Ir, StringValue
from dsml.versions import load_baseline, pinned_version

ROOT_FILES: Final = ("backend", "main", "outputs", "providers", "variables", "versions")
"""The files of each environment root module, without `.gen.tf`."""

TEMPLATE_FOLDER: Final = "infrastructure/envs"
"""The folder of the templates of the environment root modules."""


# trace: PRD-IAC-024, PRD-DSML-041
@dataclass(frozen=True, slots=True)
class EnvironmentRoot:
    """The values of one environment root module."""

    element: Element
    product: str
    account_id: str
    region: str

    @property
    def name(self) -> str:
        """The name of the environment in kebab case, for example `dev`."""
        return safe_names.kebab_case(self.element.name)


# trace: PRD-IAC-008
def product_name(ir: Ir, element: Element) -> str:
    """Give the product name: the kebab case of the root package of an element."""
    by_identity = {item.identity: item for item in ir.elements}
    root = element
    while root.owner is not None and root.owner in by_identity:
        root = by_identity[root.owner]
    return safe_names.kebab_case(root.name)


def _text_attribute(element: Element, name: str) -> str:
    """Give the text value of an attribute of an element."""
    for attribute in element.attributes:
        if attribute.name == name and isinstance(attribute.value, StringValue):
            return attribute.value.value
    raise ToolchainError(
        f'The environment "{element.identity}" has no text value for the attribute "{name}".'
    )


# trace: PRD-IAC-023, PRD-DSML-041
def environment_roots(ir: Ir) -> tuple[EnvironmentRoot, ...]:
    """Give the values of the root module of each environment, sorted by identity."""
    return tuple(
        EnvironmentRoot(
            element=element,
            product=product_name(ir, element),
            account_id=_text_attribute(element, "accountId"),
            region=_text_attribute(element, "region"),
        )
        for element in environments(ir)
    )


# trace: PRD-IAC-003, PRD-IAC-004, PRD-IAC-005, PRD-IAC-006, PRD-IAC-024, PRD-IAC-035,
# PRD-IAC-036, PRD-IAC-037
def template_data(root: EnvironmentRoot, configuration: Configuration) -> dict[str, Any]:
    """Give the template data of the files of one environment root module."""
    baseline = load_baseline()
    required_version = baseline["hcl-required-version"].value
    if required_version is None:
        raise ToolchainError('The version baseline has no value for "hcl-required-version".')
    encryption = configuration.opentofu is not None and configuration.opentofu.state_encryption
    return {
        "file_type": FileType.HCL.value,
        "elements": [root.element.identity],
        "account_id": root.account_id,
        "aws_provider_version": pinned_version("aws-provider", baseline),
        "environment": root.name,
        "environment_tag": names.tag_value(root.name),
        "product": root.product,
        "product_tag": names.tag_value(root.product),
        "region": root.region,
        "required_version": required_version,
        "state_bucket": names.state_bucket(root.product, root.name, root.account_id),
        "state_encryption": encryption,
        "state_key": names.state_key(root.name),
        "state_kms_alias": names.state_kms_alias(root.product, root.name),
    }


# trace: PRD-IAC-001, PRD-IAC-002, PRD-CORE-005, PRD-CORE-026
class InfrastructureGenerator:
    """The generator of the OpenTofu and Terraform code."""

    name = "infrastructure"
    fixed_names: Collection[str] = ()

    def __init__(self, engine: TemplateEngine | None = None) -> None:
        self._engine = TemplateEngine() if engine is None else engine

    # trace: PRD-IAC-001, PRD-TRACE-005, PRD-TRACE-006, PRD-TRACE-007
    def generate(
        self, ir: Ir, configuration: Configuration, parts: Collection[str] | None
    ) -> Sequence[OutputFile]:
        """Give the files of each environment root module."""
        output = configuration.infrastructure
        if output is None or (parts is not None and INFRASTRUCTURE not in parts):
            return []
        files: list[OutputFile] = []
        for root in environment_roots(ir):
            data = template_data(root, configuration)
            identity = root.element.identity

            def elements(address: str, identity: str = identity) -> tuple[str, ...]:
                return (identity,)

            for file in ROOT_FILES:
                content = self._engine.render_bytes(f"{TEMPLATE_FOLDER}/{file}.gen.tf.j2", data)
                path = PurePosixPath(output, "envs", root.name, f"{file}.gen.tf").as_posix()
                symbols = hcl.block_symbols(content.decode("utf-8"), elements)
                files.append(OutputFile(path, content, Kind.GENERATED, INFRASTRUCTURE, symbols))
        files.extend(_account_files(self._engine, ir, configuration, PurePosixPath(output)))
        return files


# trace: PRD-IAC-001, PRD-IAC-022, PRD-IAC-026
def _account_files(
    engine: TemplateEngine, ir: Ir, configuration: Configuration, output: PurePosixPath
) -> list[OutputFile]:
    """Give the files of the tooling root module and of the bootstrap root modules."""
    accounts = [
        Account(root.element, root.name, root.product, root.account_id, root.region)
        for root in environment_roots(ir)
    ]
    return account_files(
        engine, ir, configuration, output, lambda element: product_name(ir, element), accounts
    )
