"""Tests of the network module and the secret store module (story #79).

The example model has a network but no secret store. The test model
`tests/models/ir/solution-layers.sysml` has a network with
`natGatewayCount = 1` in dev and 2 in prod, and a secret store. Its golden
files are in `tests/golden/infrastructure/shop/`. If a change of the output is
correct, run `uv run python scripts/write_golden_infrastructure.py`.
"""

import dataclasses
import importlib.util
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.generate.infrastructure import modules
from dsml.generate.infrastructure.generator import InfrastructureGenerator
from dsml.generate.infrastructure.modules import MODULE_FILES, module_calls, zone_count
from dsml.generate.writer import check_files
from dsml.ir.model import Attribute, Element, IntegerValue, Ir, Location

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
SHOP = Path("tests/models/ir/solution-layers.sysml")
INFRA = PurePosixPath("infra")

_RESOURCE = re.compile(r'^resource "([a-z0-9_]+)" "([a-z0-9_]+)" \{$', re.MULTILINE)
_DATA = re.compile(r'^data "([a-z0-9_]+)" "([a-z0-9_]+)" \{$', re.MULTILINE)


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "write_golden_infrastructure", ROOT / "scripts/write_golden_infrastructure.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


write_golden: Any = _load_script()

UNTAGGED = frozenset({"aws_kms_alias", "aws_route", "aws_route_table_association"})
"""The resource types that do not accept tags."""


@pytest.fixture(scope="module")
def shop() -> Ir:
    return make_ir([SHOP], ROOT)


@pytest.fixture(scope="module")
def example() -> Ir:
    return make_ir([EXAMPLE], ROOT)


def _files(ir: Ir) -> dict[str, str]:
    files = InfrastructureGenerator().generate(ir, Configuration(infrastructure=INFRA), None)
    check_files(list(files))
    return {file.path: file.content.decode("utf-8") for file in files}


def _call(text: str, address: str) -> dict[str, str]:
    """Give the arguments of a module call in the text of a main.gen.tf file."""
    match = re.search(rf'^module "{address}" \{{\n(.*?)^\}}$', text, re.MULTILINE | re.DOTALL)
    assert match is not None, address
    return dict(
        (key.strip(), value.strip())
        for key, value in (
            line.split("=", 1) for line in match.group(1).splitlines() if "=" in line
        )
    )


# trace: PRD-CORE-030, PRD-IAC-001, PRD-TRACE-006, PRD-TRACE-007
def test_output_of_the_test_model_agrees_with_the_golden_files() -> None:
    output = write_golden.generate_test_model("shop")
    golden = write_golden.read_tree(write_golden.golden_folder("shop"))
    assert sorted(output) == sorted(golden)
    for path, content in output.items():
        assert content == golden[path], (
            f"The file {path} is different from the golden file. If the change is correct, "
            "run scripts/write_golden_infrastructure.py."
        )


# trace: PRD-IAC-001
def test_generator_writes_a_module_only_for_a_kind_with_an_element(shop: Ir, example: Ir) -> None:
    def folders(ir: Ir) -> set[str]:
        return {path.split("/")[2] for path in _files(ir) if path.startswith("infra/modules/")}

    assert folders(shop) == {"container-service", "network", "secret-store"}
    assert folders(example) == {
        "container-service",
        "network",
        "relational-database",
        "user-directory",
    }
    for folder in ("network", "secret-store"):
        for name in MODULE_FILES:
            assert f"infra/modules/{folder}/{name}.gen.tf" in _files(shop)


# trace: PRD-IAC-011, PRD-DSML-042
def test_nat_gateway_count_of_each_environment_gives_the_subnets_and_the_nat_gateways(
    shop: Ir,
) -> None:
    files = _files(shop)
    dev = _call(files["infra/envs/dev/main.gen.tf"], "net")
    prod = _call(files["infra/envs/prod/main.gen.tf"], "net")
    assert dev == {
        "source": '"../../modules/network"',
        "element": '"Shop::net"',
        "name": '"shop-dev-net"',
        "nat_gateway_count": "1",
        "zone_count": "2",
    }
    assert prod["nat_gateway_count"] == "2"
    assert prod["zone_count"] == "2"


def _with_nat_gateways(ir: Ir, count: int | None) -> Ir:
    """Give the IR with a different natGatewayCount on the realization of the network."""
    elements: list[Element] = []
    for element in ir.elements:
        if element.identity == "Shop::netAws":
            attributes = tuple(a for a in element.attributes if a.name != "natGatewayCount")
            if count is not None:
                location = Location(file=SHOP.as_posix(), line=1, column=1)
                attributes += (Attribute("natGatewayCount", IntegerValue(count), location),)
            element = dataclasses.replace(element, attributes=attributes)
        elif element.identity == "Shop::prod::netProd":
            continue
        elements.append(element)
    return dataclasses.replace(ir, elements=tuple(elements))


# trace: PRD-IAC-011
@pytest.mark.parametrize(
    ("count", "nat_gateways", "zones"),
    [(0, 0, 2), (1, 1, 2), (3, 3, 3), (None, 1, 2)],
)
def test_two_or_more_zones_and_one_zone_for_each_nat_gateway(
    shop: Ir, count: int | None, nat_gateways: int, zones: int
) -> None:
    files = _files(_with_nat_gateways(shop, count))
    for environment in ("dev", "prod"):
        call = _call(files[f"infra/envs/{environment}/main.gen.tf"], "net")
        assert call["nat_gateway_count"] == str(nat_gateways)
        assert call["zone_count"] == str(zones)


def test_zone_count() -> None:
    assert [zone_count(count) for count in range(5)] == [2, 2, 2, 3, 4]


# trace: PRD-IAC-011
def test_network_module_has_a_public_and_a_private_subnet_in_each_zone(shop: Ir) -> None:
    text = _files(shop)["infra/modules/network/main.gen.tf"]
    resources = _RESOURCE.findall(text)
    assert ("aws_vpc", "this") in resources
    assert ("aws_internet_gateway", "this") in resources
    for kind in ("public", "private"):
        block = re.search(rf'resource "aws_subnet" "{kind}" \{{\n  count = (.+)\n', text)
        assert block is not None and block.group(1) == "var.zone_count"
    nat = re.search(r'resource "aws_nat_gateway" "this" \{\n  count = (.+)\n', text)
    assert nat is not None and nat.group(1) == "var.nat_gateway_count"
    assert "map_public_ip_on_launch = false" in text
    assert _DATA.findall(text) == [("aws_availability_zones", "available")]


# trace: PRD-IAC-020, PRD-IAC-030, PRD-TOP-006
def test_secret_store_module_has_one_secret_and_one_key_and_no_secret_value(shop: Ir) -> None:
    files = _files(shop)
    text = files["infra/modules/secret-store/main.gen.tf"]
    resources = sorted(_RESOURCE.findall(text))
    assert resources == [
        ("aws_kms_alias", "this"),
        ("aws_kms_key", "this"),
        ("aws_secretsmanager_secret", "this"),
    ]
    assert "kms_key_id              = aws_kms_key.this.arn" in text
    assert "enable_key_rotation     = true" in text
    for content in files.values():
        assert "aws_secretsmanager_secret_version" not in content
        assert "secret_string" not in content
        assert "secret_binary" not in content
    assert _call(files["infra/envs/prod/main.gen.tf"], "secrets") == {
        "source": '"../../modules/secret-store"',
        "element": '"Shop::secrets"',
        "key_alias": '"alias/shop-prod-secrets"',
        "name": '"shop-prod-secrets"',
    }


# trace: PRD-IAC-007
def test_output_uses_only_aws_resources_and_local_modules(shop: Ir, example: Ir) -> None:
    for ir in (shop, example):
        for path, text in _files(ir).items():
            for kind, _ in _RESOURCE.findall(text) + _DATA.findall(text):
                assert kind.startswith("aws_"), (path, kind)
            for source in re.findall(r"^  source = (.+)$", text, re.MULTILINE):
                assert re.fullmatch(r'"\.\./\.\./modules/[a-z-]+"', source), (path, source)


# trace: PRD-IAC-035
def test_each_resource_has_the_tag_dsml_element(shop: Ir) -> None:
    files = _files(shop)
    for folder in ("network", "secret-store"):
        text = files[f"infra/modules/{folder}/main.gen.tf"]
        assert re.search(r'^  tags += \{ "dsml:element" = var.element \}$', text, re.MULTILINE)
        for block in re.findall(
            r'^resource "([a-z0-9_]+)" "[a-z0-9_]+" \{\n(.*?)^\}$', text, re.MULTILINE | re.DOTALL
        ):
            kind, body = block
            if kind not in UNTAGGED:
                assert "tags = merge(local.tags, " in body, (folder, kind)


# trace: PRD-TRACE-006, PRD-TRACE-007
def test_trace_manifest_gives_the_hcl_addresses_of_the_network_and_the_secret_store() -> None:
    def addresses(name: str, element: str) -> set[tuple[str, str]]:
        path = write_golden.golden_folder(name) / ".dsml" / "trace.gen.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            (file["path"], symbol["name"])
            for item in data["elements"]
            if item["element"] == element
            for file in item["files"]
            for symbol in file["symbols"]
        }

    network = addresses("order-service", "OrderService::network")
    assert network == addresses("order-service", "OrderService::networkAws")
    for environment in ("dev", "prod", "staging"):
        assert (f"infra/envs/{environment}/main.gen.tf", "module.network") in network
        assert (f"infra/envs/{environment}/outputs.gen.tf", "output.network_vpc_id") in network
    for address in ("aws_vpc.this", "aws_subnet.public", "aws_nat_gateway.this"):
        assert ("infra/modules/network/main.gen.tf", address) in network
    secrets = addresses("shop", "Shop::secrets")
    for address in ("aws_kms_key.this", "aws_secretsmanager_secret.this"):
        assert ("infra/modules/secret-store/main.gen.tf", address) in secrets
    assert ("infra/envs/prod/main.gen.tf", "module.secrets") in secrets
    assert ("infra/modules/network/main.gen.tf", "aws_vpc.this") not in secrets


# trace: PRD-DSML-037
def test_logical_element_with_no_realization_gives_an_error(shop: Ir) -> None:
    ir = dataclasses.replace(
        shop, links=tuple(link for link in shop.links if link.source != "Shop::secretsAws")
    )
    environment = next(element for element in shop.elements if element.identity == "Shop::dev")
    with pytest.raises(ToolchainError, match='"Shop::secrets" must have one AWS realization'):
        module_calls(ir, environment, "shop")


# trace: PRD-IAC-008
def test_two_elements_with_the_same_address_give_an_error(shop: Ir) -> None:
    elements = tuple(
        dataclasses.replace(element, name="net") if element.identity == "Shop::secrets" else element
        for element in shop.elements
    )
    environment = next(element for element in shop.elements if element.identity == "Shop::dev")
    with pytest.raises(ToolchainError, match=re.escape('the same HCL address "module.net"')):
        module_calls(dataclasses.replace(shop, elements=elements), environment, "shop")


def test_modules_are_in_the_order_of_their_calls() -> None:
    assert [module.folder for module in modules.MODULES] == [
        "network",
        "secret-store",
        "relational-database",
        "user-directory",
        "container-service",
    ]
