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
from dsml.generate.infrastructure import database, hcl, names, user_directory
from dsml.generate.templates import TemplateEngine
from dsml.generate.writer import INFRASTRUCTURE, Kind, OutputFile
from dsml.ir.environments import environments
from dsml.ir.model import Element, Ir, StringValue
from dsml.versions import Pin, load_baseline, pinned_version

ROOT_FILES: Final = ("backend", "main", "outputs", "providers", "variables", "versions")
"""The files of each environment root module, without `.gen.tf`."""

TEMPLATE_FOLDER: Final = "infrastructure/envs"
"""The folder of the templates of the environment root modules."""

MODULE_FILES: Final = ("main", "outputs", "variables")
"""The files of each local module, without `.gen.tf`."""

MODULE_TEMPLATE_FOLDER: Final = "infrastructure/modules"
"""The folder of the templates of the local modules."""

USER_DIRECTORY_OUTPUTS: Final = ("app_client_ids", "login_domain", "user_pool_id")
"""The outputs of each user directory in an environment root module (PRD-IAC-010)."""


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


# trace: PRD-IAC-017, PRD-IAC-019, PRD-IAC-023
def module_calls(ir: Ir, root: EnvironmentRoot) -> dict[str, Any]:
    """Give the template data of the local module calls of one environment root module."""
    return {
        "databases": database.database_calls(ir, root.product, root.element),
        "user_directories": user_directory.user_directory_calls(ir, root.product, root.element),
    }


# trace: PRD-TRACE-007
def call_elements(calls: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Give the identities of the model elements of each HCL address of the module calls.

    The address `module.<name>` and the outputs `output.<name>_*` of a call
    trace to the elements of the call.
    """
    result: dict[str, tuple[str, ...]] = {}
    for call in (*calls["databases"], *calls["user_directories"]):
        result[f"module.{call.address}"] = call.elements
    for call in calls["user_directories"]:
        for output in USER_DIRECTORY_OUTPUTS:
            result[f"output.{call.address}_{output}"] = call.elements
    return result


# trace: PRD-TRACE-005
def file_elements(file: str, identity: str, by_address: dict[str, tuple[str, ...]]) -> list[str]:
    """Give the identities of the header of one file of an environment root module.

    Each file has the environment. The file `main` also has the elements of
    the module calls, and the file `outputs` the elements of its outputs.
    """
    prefix = {"main": "module.", "outputs": "output."}.get(file)
    found = {identity}
    if prefix is not None:
        for address, identities in by_address.items():
            if address.startswith(prefix):
                found.update(identities)
    return sorted(found)


def local_modules(ir: Ir) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Give the folder name and the element identities of each local module, by folder name."""
    return (
        (database.MODULE, database.module_elements(ir)),
        (user_directory.MODULE, user_directory.module_elements(ir)),
    )


def baseline_line(baseline: dict[str, Pin], name: str) -> str:
    """Give the release line of one item of the version baseline."""
    pin = baseline.get(name)
    if pin is None or pin.line is None:
        raise ToolchainError(f'The version baseline has no release line for "{name}".')
    return pin.line


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
        roots = environment_roots(ir)
        if not roots:
            return []
        files: list[OutputFile] = []
        for root in roots:
            data = template_data(root, configuration)
            calls = module_calls(ir, root)
            data.update(calls)
            by_address = call_elements(calls)
            identity = root.element.identity

            def elements(
                address: str,
                identity: str = identity,
                by_address: dict[str, tuple[str, ...]] = by_address,
            ) -> tuple[str, ...]:
                return tuple(sorted({identity, *by_address.get(address, ())}))

            for file in ROOT_FILES:
                header = {"elements": file_elements(file, identity, by_address)}
                content = self._engine.render_bytes(
                    f"{TEMPLATE_FOLDER}/{file}.gen.tf.j2", data | header
                )
                path = PurePosixPath(output, "envs", root.name, f"{file}.gen.tf").as_posix()
                symbols = hcl.block_symbols(content.decode("utf-8"), elements)
                files.append(OutputFile(path, content, Kind.GENERATED, INFRASTRUCTURE, symbols))
        files.extend(self._module_files(ir, PurePosixPath(output)))
        return files

    # trace: PRD-IAC-001, PRD-IAC-007, PRD-TRACE-005, PRD-TRACE-006, PRD-TRACE-007
    def _module_files(self, ir: Ir, output: PurePosixPath) -> list[OutputFile]:
        """Give the files of each local module that the model needs.

        All environments call the same local modules (PRD-IAC-023). Thus the
        files of a module are the same for each environment. Each top-level
        block of a module file traces to all elements of the module.
        """
        files: list[OutputFile] = []
        baseline = load_baseline()
        for module, identities in local_modules(ir):
            if not identities:
                continue
            data = {
                "file_type": FileType.HCL.value,
                "elements": list(identities),
                "engine_version": baseline_line(baseline, "postgresql"),
            }

            def elements(address: str, identities: tuple[str, ...] = identities) -> tuple[str, ...]:
                return identities

            for file in MODULE_FILES:
                content = self._engine.render_bytes(
                    f"{MODULE_TEMPLATE_FOLDER}/{module}/{file}.gen.tf.j2", data
                )
                path = (output / "modules" / module / f"{file}.gen.tf").as_posix()
                symbols = hcl.block_symbols(content.decode("utf-8"), elements)
                files.append(OutputFile(path, content, Kind.GENERATED, INFRASTRUCTURE, symbols))
        return files
