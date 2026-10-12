# trace: PRD-IAC-001, PRD-IAC-002, PRD-IAC-023, PRD-CORE-026
"""The infrastructure generator: the root module of each environment and the local modules.

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
  `default_tags` (PRD-IAC-024, PRD-IAC-035). A root module with a static
  site also gets a second AWS provider for `us-east-1` (PRD-IAC-021).
- `main.gen.tf`: the values of the environment, and one call of a local
  module for each logical element (PRD-IAC-023).
- `variables.gen.tf`: the variable `model_commit` (PRD-IAC-036) and the
  variables of the module calls, for example the image digest of an
  application (PRD-IAC-009).
- `outputs.gen.tf`: the values that the pipelines need, and the outputs of
  the module calls (PRD-IAC-010).

For each logical kind with one or more elements, the folder
`modules/<module>/` gets the files `main.gen.tf`, `variables.gen.tf` and
`outputs.gen.tf`. `dsml.generate.infrastructure.modules` gives the modules.

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
from dsml.generate.infrastructure import hcl, modules, names
from dsml.generate.infrastructure.accounts import Account, account_files
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import INFRASTRUCTURE, Kind, OutputFile
from dsml.ir.environments import environments
from dsml.ir.model import Element, Ir, StringValue
from dsml.versions import load_baseline, pinned_version

ROOT_FILES: Final = ("backend", "main", "outputs", "providers", "variables", "versions")
"""The files of each environment root module, without `.gen.tf`."""

CALL_FILES: Final = frozenset({"main", "outputs"})
"""The files of a root module that contain the module calls and their outputs."""

TEMPLATE_FOLDER: Final = "infrastructure/envs"
"""The folder of the templates of the environment root modules."""

US_EAST_1_FOLDERS: Final = frozenset({"static-site"})
"""The local modules that need the second AWS provider of the Region `us-east-1`.

CloudFront accepts only ACM certificates of `us-east-1` (PRD-IAC-021).
"""


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


# trace: PRD-IAC-003, PRD-IAC-004, PRD-IAC-005, PRD-IAC-006, PRD-IAC-024, PRD-IAC-035
# trace: PRD-IAC-036, PRD-IAC-037
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
        """Give the files of each environment root module and of each local module."""
        output = configuration.infrastructure
        if output is None or (parts is not None and INFRASTRUCTURE not in parts):
            return []
        files: list[OutputFile] = []
        module_elements: dict[str, set[str]] = {}
        for root in environment_roots(ir):
            calls = modules.module_calls(ir, root.element, root.product)
            files.extend(self._root_files(root, configuration, calls, output))
            for call in calls:
                module_elements.setdefault(call.folder, set()).update(call.identities)
        for module in modules.MODULES:
            if module.folder in module_elements:
                identities = tuple(sorted(module_elements[module.folder]))
                files.extend(self._module_files(module, identities, output))
        files.extend(_account_files(self._engine, ir, configuration, PurePosixPath(output)))
        return files

    # trace: PRD-IAC-001, PRD-IAC-021, PRD-IAC-023, PRD-TRACE-005, PRD-TRACE-007
    def _root_files(
        self,
        root: EnvironmentRoot,
        configuration: Configuration,
        calls: Sequence[modules.ModuleCall],
        output: PurePosixPath,
    ) -> list[OutputFile]:
        """Give the files of one environment root module.

        A module call, its outputs and its variables are symbols of the
        logical element and of its AWS realization. The other blocks are symbols of the
        environment.
        """
        data = template_data(root, configuration)
        data["calls"] = calls
        data["us_east_1_provider"] = any(call.folder in US_EAST_1_FOLDERS for call in calls)
        call_elements = tuple(sorted({item for call in calls for item in call.identities}))
        by_address: dict[str, tuple[str, ...]] = {}
        for call in calls:
            by_address[f"module.{call.address}"] = call.identities
            for item in call.outputs:
                by_address[f"output.{item.name}"] = call.identities
            for variable in call.variables:
                by_address[f"var.{variable.name}"] = call.identities
        variable_elements = tuple(
            sorted({item for call in calls if call.variables for item in call.identities})
        )
        identity = root.element.identity

        def elements(address: str) -> tuple[str, ...]:
            return by_address.get(address, (identity,))

        files: list[OutputFile] = []
        for file in ROOT_FILES:
            file_elements = [identity]
            if file in CALL_FILES:
                file_elements.extend(call_elements)
            elif file == "variables":
                file_elements.extend(variable_elements)
            content = self._engine.render_bytes(
                f"{TEMPLATE_FOLDER}/{file}.gen.tf.j2",
                {**data, "elements": sorted(file_elements)},
            )
            path = PurePosixPath(output, "envs", root.name, f"{file}.gen.tf").as_posix()
            symbols = hcl.block_symbols(content.decode("utf-8"), elements)
            files.append(OutputFile(path, content, Kind.GENERATED, INFRASTRUCTURE, symbols))
        return files

    # trace: PRD-IAC-001, PRD-IAC-007, PRD-TRACE-005, PRD-TRACE-007
    def _module_files(
        self, module: modules.LocalModule, identities: tuple[str, ...], output: PurePosixPath
    ) -> list[OutputFile]:
        """Give the files of one local module.

        Each block of the module is a symbol of each element that calls the
        module, and of its AWS realization.
        """
        folder = module.folder
        data = {
            **module.template_data(),
            "file_type": FileType.HCL.value,
            "elements": list(identities),
        }
        files: list[OutputFile] = []
        for file in modules.MODULE_FILES:
            content = self._engine.render_bytes(
                f"{modules.TEMPLATE_FOLDER}/{folder}/{file}.gen.tf.j2", data
            )
            path = PurePosixPath(output, "modules", folder, f"{file}.gen.tf").as_posix()
            symbols = hcl.block_symbols(content.decode("utf-8"), lambda _: identities)
            files.append(OutputFile(path, content, Kind.GENERATED, INFRASTRUCTURE, symbols))
        return files


# trace: PRD-IAC-001, PRD-IAC-021, PRD-IAC-022, PRD-IAC-026
def _account_files(
    engine: TemplateEngine, ir: Ir, configuration: Configuration, output: PurePosixPath
) -> list[OutputFile]:
    """Give the files of the tooling root module and of the bootstrap root modules."""
    sites = [element for element in ir.elements if element.kind == "StaticSite"]
    accounts = [
        Account(
            root.element,
            root.name,
            root.product,
            root.account_id,
            root.region,
            tuple(
                sorted(
                    names.site_bucket(root.product, root.name, site.name, root.account_id)
                    for site in sites
                )
            ),
        )
        for root in environment_roots(ir)
    ]
    return account_files(
        engine, ir, configuration, output, lambda element: product_name(ir, element), accounts
    )
