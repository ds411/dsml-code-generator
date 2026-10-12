"""Tests of the local module static-site and of its module calls (story #162).

The golden files in `tests/golden/infrastructure/order-portal/` hold the full
output of the phase 2 reference model. These tests examine the values that
the requirements give. If a change of the output is correct, run
`uv run python scripts/write_golden_infrastructure.py`.
"""

import dataclasses
import importlib.util
import re
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.generate.infrastructure import modules, names, policies
from dsml.generate.infrastructure.generator import InfrastructureGenerator
from dsml.ir.model import Attribute, EnumValue, Ir
from dsml.versions import load_baseline

ROOT = Path(__file__).resolve().parent.parent
PORTAL = ROOT / "docs" / "model" / "examples" / "order-portal" / "order-portal.sysml"
ORDER_SERVICE = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
MODULE = "infra/modules/static-site"
ENVIRONMENTS = {
    "dev": ("222222222222", "portal.dev.example.com"),
    "prod": ("444444444444", "portal.example.com"),
    "staging": ("333333333333", "portal.staging.example.com"),
}
SITE = "OrderPortal::portalSite"
PORTAL_APPLICATION = "OrderPortal::orderPortal"


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
    return make_ir([PORTAL], ROOT)


def _generate(ir: Ir) -> dict[str, str]:
    output = InfrastructureGenerator().generate(
        ir, Configuration(infrastructure=PurePosixPath("infra")), None
    )
    return {file.path: file.content.decode("utf-8") for file in output}


@pytest.fixture(scope="module")
def files(ir: Ir) -> dict[str, str]:
    return _generate(ir)


def _block(text: str, start: str) -> str:
    """Give the top-level block that starts with the line `start`."""
    lines = text.split("\n")
    first = lines.index(start)
    last = lines.index("}", first)
    return "\n".join(lines[first : last + 1])


def _flat(text: str) -> str:
    """Give the text with one space before each "="."""
    return re.sub(r" +=", " =", text)


def _call(files: dict[str, str], environment: str) -> str:
    text = files[f"infra/envs/{environment}/main.gen.tf"]
    return _flat(_block(text, 'module "portal_site" {'))


def _without_allocation(ir: Ir) -> Ir:
    links = tuple(
        link for link in ir.links if not (link.type == "allocate" and link.target == SITE)
    )
    return dataclasses.replace(ir, links=links)


def _with_target(ir: Ir, target: str) -> Ir:
    def change(attribute: Attribute) -> Attribute:
        if attribute.name == "target" and isinstance(attribute.value, EnumValue):
            return dataclasses.replace(
                attribute, value=dataclasses.replace(attribute.value, literal=target)
            )
        return attribute

    elements = tuple(
        dataclasses.replace(element, attributes=tuple(change(item) for item in element.attributes))
        if element.identity == PORTAL_APPLICATION
        else element
        for element in ir.elements
    )
    return dataclasses.replace(ir, elements=elements)


# trace: PRD-CORE-030, PRD-IAC-001, PRD-IAC-021
def test_output_of_the_order_portal_agrees_with_the_golden_files(tmp_path: Path) -> None:
    output = write_golden.generate("order-portal", tmp_path)
    golden = write_golden.read_tree(write_golden.golden_folder("order-portal"))
    assert sorted(output) == sorted(golden)
    for path, content in golden.items():
        assert output[path] == content, path


# trace: PRD-IAC-001, PRD-IAC-021
def test_generator_writes_the_static_site_module(files: dict[str, str]) -> None:
    for file in ("main", "outputs", "variables"):
        assert f"{MODULE}/{file}.gen.tf" in files


# trace: PRD-IAC-001
def test_model_with_no_static_site_gives_no_static_site_module() -> None:
    files = _generate(make_ir([ORDER_SERVICE], ROOT))
    assert not [path for path in files if path.startswith(MODULE)]
    for environment in ENVIRONMENTS:
        assert "us_east_1" not in files[f"infra/envs/{environment}/providers.gen.tf"]


# trace: PRD-IAC-008, PRD-IAC-021, PRD-IAC-023, PRD-IAC-035
@pytest.mark.parametrize("environment", sorted(ENVIRONMENTS))
def test_each_environment_calls_the_module_with_its_values(
    files: dict[str, str], environment: str
) -> None:
    account, domain = ENVIRONMENTS[environment]
    call = _call(files, environment)
    assert 'source = "../../modules/static-site"' in call
    assert f'application = "{PORTAL_APPLICATION}"' in call
    assert f'element = "{SITE}"' in call
    assert f'bucket_name = "order-portal-{environment}-portal-site-{account}"' in call
    assert f'domain_name = "order-portal.{domain}"' in call
    assert f'origin_access_control_name = "order-portal-{environment}-portal-site"' in call
    assert f'zone_name = "{domain}"' in call
    assert "aws = aws\n" in call
    assert "aws.us_east_1 = aws.us_east_1\n" in call


# trace: PRD-IAC-021, PRD-IAC-024, PRD-IAC-035
@pytest.mark.parametrize("environment", sorted(ENVIRONMENTS))
def test_root_module_has_a_second_provider_for_us_east_1(
    files: dict[str, str], environment: str
) -> None:
    account, _ = ENVIRONMENTS[environment]
    providers = _flat(files[f"infra/envs/{environment}/providers.gen.tf"])
    assert providers.count('provider "aws" {') == 2
    second = providers[providers.index('alias = "us_east_1"') :]
    assert 'region = "us-east-1"' in second
    assert "allowed_account_ids = [local.aws_account_id]" in second
    assert f'"dsml:environment" = "{environment}"' in second
    assert '"dsml:model-commit" = var.model_commit' in second
    assert account in files[f"infra/envs/{environment}/main.gen.tf"]


# trace: PRD-IAC-010
@pytest.mark.parametrize("environment", sorted(ENVIRONMENTS))
def test_root_module_outputs_the_bucket_and_the_distribution(
    files: dict[str, str], environment: str
) -> None:
    outputs = _flat(files[f"infra/envs/{environment}/outputs.gen.tf"])
    for name, value in (
        ("portal_site_bucket_name", "module.portal_site.bucket_name"),
        ("portal_site_distribution_id", "module.portal_site.distribution_id"),
        ("portal_site_url", "module.portal_site.url"),
    ):
        assert f"value = {value}" in _block(outputs, f'output "{name}" {{')


# trace: PRD-IAC-019, PRD-IAC-021
@pytest.mark.parametrize("environment", sorted(ENVIRONMENTS))
def test_app_client_of_the_react_application_uses_the_site_domain(
    files: dict[str, str], environment: str
) -> None:
    _, domain = ENVIRONMENTS[environment]
    call = _flat(_block(files[f"infra/envs/{environment}/main.gen.tf"], 'module "users" {'))
    portal = call[call.index("order_portal = {") :]
    portal = portal[: portal.index("}")]
    assert f'name = "order-portal-{environment}-order-portal"' in portal
    assert f'callback_urls = ["https://order-portal.{domain}/auth/callback"]' in portal
    assert f'logout_urls = ["https://order-portal.{domain}/"]' in portal
    api = call[call.index("order_api = {") :]
    api = api[: api.index("}")]
    assert f'callback_urls = ["https://{domain}/auth/callback"]' in api


# trace: PRD-IAC-021
def test_module_writes_a_private_versioned_bucket(files: dict[str, str]) -> None:
    main = _flat(files[f"{MODULE}/main.gen.tf"])
    assert 'resource "aws_s3_bucket" "site" {' in main
    assert 'status = "Enabled"' in _block(main, 'resource "aws_s3_bucket_versioning" "site" {')
    ownership = _block(main, 'resource "aws_s3_bucket_ownership_controls" "site" {')
    assert 'object_ownership = "BucketOwnerEnforced"' in ownership


# trace: PRD-IAC-021, PRD-IAC-031, PRD-IAC-033
def test_bucket_policy_permits_reads_only_by_the_distribution(files: dict[str, str]) -> None:
    main = _flat(files[f"{MODULE}/main.gen.tf"])
    document = _block(main, 'data "aws_iam_policy_document" "site" {')
    assert document.count("statement {") == 1
    assert 'actions = ["s3:GetObject"]' in document
    assert 'resources = ["${aws_s3_bucket.site.arn}/*"]' in document
    assert 'type = "Service"' in document
    assert 'identifiers = ["cloudfront.amazonaws.com"]' in document
    assert 'variable = "AWS:SourceArn"' in document
    assert "values = [aws_cloudfront_distribution.site.arn]" in document
    policy = _block(main, 'resource "aws_s3_bucket_policy" "site" {')
    assert "policy = data.aws_iam_policy_document.site.json" in policy


# trace: PRD-IAC-021, PRD-IAC-034
def test_distribution_uses_the_bucket_with_origin_access_control(files: dict[str, str]) -> None:
    main = _flat(files[f"{MODULE}/main.gen.tf"])
    control = _block(main, 'resource "aws_cloudfront_origin_access_control" "site" {')
    assert 'origin_access_control_origin_type = "s3"' in control
    assert 'signing_behavior = "always"' in control
    assert 'signing_protocol = "sigv4"' in control
    distribution = _block(main, 'resource "aws_cloudfront_distribution" "site" {')
    assert "domain_name = aws_s3_bucket.site.bucket_regional_domain_name" in distribution
    assert "origin_access_control_id = aws_cloudfront_origin_access_control.site.id" in distribution
    assert "aliases = [var.domain_name]" in distribution
    assert 'viewer_protocol_policy = "redirect-to-https"' in distribution
    assert 'allowed_methods = ["GET", "HEAD"]' in distribution
    assert 'ssl_support_method = "sni-only"' in distribution
    policy = load_baseline()["cloudfront-tls-policy"].value
    assert policy is not None
    assert f'minimum_protocol_version = "{policy}"' in distribution


# trace: PRD-IAC-021
def test_distribution_returns_the_index_for_paths_that_do_not_exist(
    files: dict[str, str],
) -> None:
    main = _flat(files[f"{MODULE}/main.gen.tf"])
    distribution = _block(main, 'resource "aws_cloudfront_distribution" "site" {')
    responses = re.findall(r"custom_error_response \{\n(.*?)\n  \}", distribution, re.DOTALL)
    codes: set[str] = set()
    for response in responses:
        assert "response_code = 200" in response
        assert 'response_page_path = "/index.html"' in response
        code = re.search(r"error_code = (\d+)", response)
        assert code is not None
        codes.add(code.group(1))
    assert codes == {"403", "404"}


# trace: PRD-IAC-021
def test_certificate_is_in_us_east_1_with_a_route_53_alias(files: dict[str, str]) -> None:
    main = _flat(files[f"{MODULE}/main.gen.tf"])
    assert "configuration_aliases = [aws.us_east_1]" in _block(main, "terraform {")
    certificate = _block(main, 'resource "aws_acm_certificate" "site" {')
    assert "provider = aws.us_east_1" in certificate
    assert 'validation_method = "DNS"' in certificate
    validation = _block(main, 'resource "aws_acm_certificate_validation" "site" {')
    assert "provider = aws.us_east_1" in validation
    distribution = _block(main, 'resource "aws_cloudfront_distribution" "site" {')
    assert (
        "acm_certificate_arn = aws_acm_certificate_validation.site.certificate_arn" in distribution
    )
    alias = _block(main, 'resource "aws_route53_record" "site" {')
    assert 'for_each = toset(["A", "AAAA"])' in alias
    assert "name = aws_cloudfront_distribution.site.domain_name" in alias
    assert "zone_id = aws_cloudfront_distribution.site.hosted_zone_id" in alias


# trace: PRD-IAC-035
def test_module_resources_have_the_element_and_application_tags(files: dict[str, str]) -> None:
    main = _flat(files[f"{MODULE}/main.gen.tf"])
    tags = _block(main, "locals {")
    assert '"dsml:application" = var.application' in tags
    assert '"dsml:element" = var.element' in tags
    for start in (
        'resource "aws_s3_bucket" "site" {',
        'resource "aws_acm_certificate" "site" {',
        'resource "aws_cloudfront_distribution" "site" {',
    ):
        assert "tags = local.tags" in _block(main, start), start


# trace: PRD-TRACE-007
def test_module_blocks_are_symbols_of_the_site_and_its_realization(ir: Ir) -> None:
    output = InfrastructureGenerator().generate(
        ir, Configuration(infrastructure=PurePosixPath("infra")), None
    )
    main = next(file for file in output if file.path == f"{MODULE}/main.gen.tf")
    assert main.symbols
    for symbol in main.symbols:
        assert symbol.elements == ("OrderPortal::portalSite", "OrderPortal::portalSiteAws")


# trace: PRD-IAC-021
def test_static_site_needs_one_allocated_application(ir: Ir) -> None:
    with pytest.raises(ToolchainError, match="must have one allocated application, not 0"):
        _generate(_without_allocation(ir))


# trace: PRD-IAC-021
def test_static_site_serves_only_a_react_application(ir: Ir) -> None:
    with pytest.raises(ToolchainError, match='cannot serve the target "fastapi"'):
        _generate(_with_target(ir, "fastapi"))


# trace: PRD-IAC-008, PRD-IAC-021
def test_site_bucket_ends_with_the_account_id() -> None:
    assert names.site_bucket("order-portal", "dev", "portalSite", "222222222222") == (
        "order-portal-dev-portal-site-222222222222"
    )
    bucket = names.site_bucket("a-very-long-product-name", "staging", "x" * 40, "333333333333")
    assert len(bucket) == names.NAME_LIMITS["s3_bucket"]
    assert bucket.endswith("-333333333333")


# trace: PRD-IAC-021, PRD-IAC-027, PRD-IAC-033
def test_deploy_role_can_change_the_static_sites(files: dict[str, str]) -> None:
    iam = _flat(files["infra/bootstrap/dev/iam.gen.tf"])
    for sid in (
        "SiteRead",
        "SiteCertificateRequest",
        "SiteCertificates",
        "SiteDistributions",
        "SiteBuckets",
    ):
        assert f'sid = "{sid}"' in iam, sid
    assert '"arn:aws:s3:::order-portal-dev-portal-site-222222222222/*"' in iam
    assert '"arn:aws:acm:us-east-1:222222222222:*"' in iam
    assert '"cloudfront:CreateInvalidation"' in iam


# trace: PRD-IAC-027, PRD-IAC-033
def test_deploy_policy_with_no_site_has_no_site_statement() -> None:
    policy = policies.deploy_policy("p", "dev", "222222222222", "eu-west-1", (), False)
    assert not [item for item in policy.statements if item.sid.startswith("Site")]


# trace: PRD-IAC-027, PRD-IAC-033
def test_site_bucket_statement_does_not_apply_to_the_state_bucket() -> None:
    policy = policies.deploy_policy(
        "p", "dev", "222222222222", "eu-west-1", (), False, ("p-dev-site-222222222222",)
    )
    statement = next(item for item in policy.statements if item.sid == "SiteBuckets")
    assert statement.resources == (
        '"arn:aws:s3:::p-dev-site-222222222222"',
        '"arn:aws:s3:::p-dev-site-222222222222/*"',
    )
    for action in policy.actions:
        assert policies.is_permitted_action(action), action


# trace: PRD-IAC-021
def test_site_domain_has_the_form_of_the_api_domain(ir: Ir) -> None:
    by_identity = {element.identity: element for element in ir.elements}
    application = by_identity[PORTAL_APPLICATION]
    environment = by_identity["OrderPortal::dev"]
    assert modules.site_domain(application, environment) == "order-portal.portal.dev.example.com"
