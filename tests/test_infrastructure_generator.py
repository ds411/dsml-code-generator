"""Tests of the infrastructure generator: the environment root modules (story #76).

The golden files in `tests/golden/infrastructure/order-service/` are the
output of `dsml generate --infrastructure` for the example model, with the
manifest and the trace manifest. If a change of the output is correct, run
`uv run python scripts/write_golden_infrastructure.py`.
"""

import importlib.util
import re
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Configuration, OpenTofuOptions
from dsml.generate.generators import GENERATORS
from dsml.generate.infrastructure.generator import ROOT_FILES, InfrastructureGenerator
from dsml.generate.infrastructure.modules import MODULE_FILES
from dsml.generate.trace import SymbolKind
from dsml.generate.writer import INFRASTRUCTURE, Kind, OutputFile, application_part, check_files
from dsml.ir.model import Ir
from dsml.versions import pinned_version

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
ENVIRONMENTS = ("dev", "prod", "staging")
MODULE_FOLDERS = ("container-service", "network", "relational-database", "user-directory")
"""The local modules of the example model, sorted."""
CALLS = {
    "api_service": ("OrderService::apiService", "OrderService::apiServiceAws"),
    "network": ("OrderService::network", "OrderService::networkAws"),
    "order_db": ("OrderService::orderDb", "OrderService::orderDbAws"),
    "users": ("OrderService::users", "OrderService::usersAws"),
}
"""The elements of each module call of the example model."""
DOMAINS = {
    "dev": "orders.dev.example.com",
    "prod": "orders.example.com",
    "staging": "orders.staging.example.com",
}
INFRA = PurePosixPath("infra")


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "write_golden_infrastructure", ROOT / "scripts/write_golden_infrastructure.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


write_golden: Any = _load_script()


@pytest.fixture(scope="module")
def ir() -> Ir:
    return make_ir([EXAMPLE], ROOT)


def _generate(ir: Ir, configuration: Configuration | None = None) -> dict[str, OutputFile]:
    if configuration is None:
        configuration = Configuration(infrastructure=INFRA)
    files = InfrastructureGenerator().generate(ir, configuration, None)
    return {file.path: file for file in files}


def _root_and_module_files(files: dict[str, OutputFile]) -> dict[str, OutputFile]:
    return {
        path: file
        for path, file in files.items()
        if path.startswith(("infra/envs/", "infra/modules/"))
    }


def _environment_files(files: dict[str, OutputFile]) -> dict[str, OutputFile]:
    return {path: file for path, file in files.items() if path.startswith("infra/envs/")}


def _text(files: dict[str, OutputFile], environment: str, name: str) -> str:
    return files[f"infra/envs/{environment}/{name}.gen.tf"].content.decode("utf-8")


# trace: PRD-CORE-030, PRD-IAC-001, PRD-TRACE-005, PRD-TRACE-006, PRD-TRACE-007
def test_output_of_the_example_model_agrees_with_the_golden_files(tmp_path: Path) -> None:
    output = write_golden.generate("order-service", tmp_path)
    golden = write_golden.read_tree(write_golden.golden_folder("order-service"))
    assert sorted(output) == sorted(golden)
    for path, content in output.items():
        assert content == golden[path], (
            f"The file {path} is different from the golden file. If the change is correct, "
            "run scripts/write_golden_infrastructure.py."
        )


# trace: PRD-IAC-001, PRD-IAC-002
def test_generator_writes_the_root_modules_and_the_local_modules(ir: Ir) -> None:
    files = _root_and_module_files(_generate(ir))
    assert sorted(files) == [
        *(
            f"infra/envs/{environment}/{name}.gen.tf"
            for environment in ENVIRONMENTS
            for name in ROOT_FILES
        ),
        *(
            f"infra/modules/{folder}/{name}.gen.tf"
            for folder in MODULE_FOLDERS
            for name in MODULE_FILES
        ),
    ]
    for file in files.values():
        assert file.kind is Kind.GENERATED
        assert file.part == INFRASTRUCTURE
    check_files(list(files.values()))


def test_generator_is_in_the_list_of_generators() -> None:
    assert any(isinstance(generator, InfrastructureGenerator) for generator in GENERATORS)


def test_no_output_folder_or_other_part_gives_no_file(ir: Ir) -> None:
    generator = InfrastructureGenerator()
    assert generator.generate(ir, Configuration(), None) == []
    configuration = Configuration(infrastructure=INFRA)
    assert generator.generate(ir, configuration, {application_part("orderApi")}) == []
    assert len(generator.generate(ir, configuration, {INFRASTRUCTURE})) == 64


def test_model_with_no_environment_gives_no_file() -> None:
    assert InfrastructureGenerator().generate(Ir(), Configuration(infrastructure=INFRA), None) == []


# trace: PRD-TRACE-005
def test_each_file_starts_with_the_header_of_its_elements(ir: Ir) -> None:
    files = _generate(ir)
    for environment in ENVIRONMENTS:
        for name in ROOT_FILES:
            elements = f"OrderService::{environment}"
            if name in ("main", "outputs"):
                identities = [item for call in CALLS.values() for item in call]
                elements = ", ".join(sorted([elements, *identities]))
            elif name == "variables":
                elements = ", ".join(sorted([elements, *CALLS["api_service"]]))
            assert _text(files, environment, name).startswith(
                f"# Generated by dsml 0. Do not edit.\n# Elements: {elements}\n\n"
            )
    for name in MODULE_FILES:
        assert files[f"infra/modules/network/{name}.gen.tf"].content.startswith(
            b"# Generated by dsml 0. Do not edit.\n"
            b"# Elements: OrderService::network, OrderService::networkAws\n\n"
        )


# trace: PRD-IAC-003, PRD-IAC-005
def test_versions_pin_the_tools_and_the_exact_aws_provider_version(ir: Ir) -> None:
    text = _text(_generate(ir), "dev", "versions")
    assert '  required_version = ">= 1.13.0"\n' in text
    assert f'      version = "{pinned_version("aws-provider")}"\n' in text
    assert re.fullmatch(r"6\.[0-9]+\.[0-9]+", pinned_version("aws-provider"))


# trace: PRD-IAC-006
def test_backend_is_s3_with_locks_and_encryption_in_the_account_of_the_environment(
    ir: Ir,
) -> None:
    text = _text(_generate(ir), "staging", "backend")
    assert '  backend "s3" {\n' in text
    assert '    bucket       = "order-service-staging-tfstate-333333333333"\n' in text
    assert '    key          = "envs/staging/terraform.tfstate"\n' in text
    assert "    encrypt      = true\n" in text
    assert "    use_lockfile = true\n" in text


# trace: PRD-IAC-024, PRD-IAC-035
def test_provider_sets_the_account_and_the_default_tags(ir: Ir) -> None:
    files = _generate(ir)
    main = _text(files, "prod", "main")
    assert '  aws_account_id = "444444444444"\n' in main
    assert '  aws_region     = "eu-west-1"\n' in main
    providers = _text(files, "prod", "providers")
    assert "  allowed_account_ids = [local.aws_account_id]\n" in providers
    assert '      "dsml:environment"  = "prod"\n' in providers
    assert '      "dsml:model-commit" = var.model_commit\n' in providers
    assert '      "dsml:product"      = "order-service"\n' in providers


# trace: PRD-IAC-036
def test_generated_files_do_not_contain_a_commit(ir: Ir) -> None:
    files = _generate(ir)
    assert 'variable "model_commit" {' in _text(files, "dev", "variables")
    for file in files.values():
        assert not re.search(
            rb"(?<![0-9a-f])([0-9a-f]{40}|[0-9a-f]{64})(?![0-9a-f])", file.content
        ), file.path


# trace: PRD-IAC-004
def test_state_encryption_gives_the_opentofu_comment(ir: Ir) -> None:
    configuration = Configuration(
        infrastructure=INFRA, opentofu=OpenTofuOptions(state_encryption=True)
    )
    text = _text(_generate(ir, configuration), "dev", "backend")
    assert (
        "  # Only OpenTofu accepts this block (iac.opentofu.state_encryption = true).\n"
        "  # Terraform does not accept this root module.\n"
        "  encryption {\n"
    ) in text
    assert '      kms_key_id = "alias/order-service-dev-tfstate"\n' in text


# trace: PRD-IAC-003, PRD-IAC-004
@pytest.mark.parametrize("options", [None, OpenTofuOptions(state_encryption=False)])
def test_no_state_encryption_gives_no_opentofu_comment(
    ir: Ir, options: OpenTofuOptions | None
) -> None:
    files = _generate(ir, Configuration(infrastructure=INFRA, opentofu=options))
    for file in _environment_files(files).values():
        assert b"OpenTofu" not in file.content
        assert b"encryption" not in file.content


# trace: PRD-IAC-023
def test_environments_differ_only_in_their_attributes(ir: Ir) -> None:
    files = _generate(ir)
    values = {
        "dev": ("dev", "222222222222"),
        "prod": ("prod", "444444444444"),
        "staging": ("staging", "333333333333"),
    }
    for name in ROOT_FILES:
        texts: set[str] = set()
        for environment, (label, account) in values.items():
            # The header lists the elements in sorted order. Another test examines it.
            text = _text(files, environment, name).split("\n", 2)[2]
            text = text.replace(DOMAINS[environment], "<domain>")
            # The override of orderDb in prod, and deletion protection in prod only.
            text = re.sub(r"(multi_az|deletion_protection) += (true|false)", r"\1", text)
            # The override of apiService in prod changes desiredCount, minCount and maxCount.
            text = re.sub(r"((?:desired|min|max)_count) += [0-9]+", r"\1", text)
            # A long AWS name gets a hash (PRD-IAC-008), for example in staging.
            text = re.sub(
                r'"order-service-{label}-[a-z0-9-]+"'.replace("{label}", label), '"<name>"', text
            )
            text = re.sub(rf"(?<![a-z]){label}(?![a-z])", "<environment>", text)
            texts.add(text.replace(account, "<account>"))
        assert len(texts) == 1, name


# trace: PRD-TRACE-006, PRD-TRACE-007
def test_each_top_level_block_is_a_symbol_of_the_environment(ir: Ir) -> None:
    files = _generate(ir)
    symbols = {
        name: [
            (symbol.name, symbol.first_line, symbol.last_line)
            for symbol in files[f"infra/envs/dev/{name}.gen.tf"].symbols
        ]
        for name in ROOT_FILES
    }
    assert symbols == {
        "backend": [("terraform", 4, 12)],
        "main": [
            ("locals", 4, 9),
            ("module.network", 11, 18),
            ("module.order_db", 20, 35),
            ("module.users", 37, 51),
            ("module.api_service", 53, 102),
        ],
        "outputs": [
            ("output.aws_account_id", 4, 7),
            ("output.aws_region", 9, 12),
            ("output.environment", 14, 17),
            ("output.product", 19, 22),
            ("output.network_private_subnet_ids", 24, 27),
            ("output.network_public_subnet_ids", 29, 32),
            ("output.network_vpc_id", 34, 37),
            ("output.users_app_client_ids", 39, 42),
            ("output.users_login_domain", 44, 47),
            ("output.users_user_pool_id", 49, 52),
            ("output.api_service_api_url", 54, 57),
            ("output.api_service_cluster_name", 59, 62),
            ("output.api_service_migration_task_definition", 64, 67),
            ("output.api_service_private_subnet_ids", 69, 72),
            ("output.api_service_security_group_id", 74, 77),
            ("output.api_service_service_name", 79, 82),
        ],
        "providers": [("provider.aws", 4, 15)],
        "variables": [("var.model_commit", 4, 13), ("var.order_api_image_digest", 15, 24)],
        "versions": [("terraform", 4, 13)],
    }
    folders = {
        "api_service": "container-service",
        "network": "network",
        "order_db": "relational-database",
        "users": "user-directory",
    }
    for file in _root_and_module_files(files).values():
        for symbol in file.symbols:
            assert symbol.kind is SymbolKind.RESOURCE
            calls = [
                address
                for address, folder in folders.items()
                if file.path.startswith(f"infra/modules/{folder}/")
                or symbol.name == f"module.{address}"
                or symbol.name.startswith(f"output.{address}_")
                or (address == "api_service" and symbol.name == "var.order_api_image_digest")
            ]
            if calls:
                assert symbol.elements == CALLS[calls[0]]
            else:
                assert symbol.elements == (f"OrderService::{file.path.split('/')[2]}",)
