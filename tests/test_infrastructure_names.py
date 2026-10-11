"""Tests of the names of the infrastructure (story #76).

The names module gives the HCL addresses, the AWS names, the shorter names
with a hash, the shorter tag values and the names of the CI roles.
"""

import hashlib

import pytest

from dsml.generate.infrastructure import hcl, names


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:8]


# trace: PRD-IAC-008
@pytest.mark.parametrize(
    ("name", "address"),
    [("apiService", "api_service"), ("orderDb", "order_db"), ("network", "network")],
)
def test_hcl_address_is_the_snake_case_of_the_element_name(name: str, address: str) -> None:
    assert names.hcl_address(name) == address


# trace: PRD-IAC-008
def test_aws_name_has_the_form_product_environment_element() -> None:
    assert names.aws_name("order-service", "dev", "apiService", "ecs_service") == (
        "order-service-dev-api-service"
    )
    assert names.aws_name("OrderService", "prod", "orderDb", "db_instance") == (
        "order-service-prod-order-db"
    )


# trace: PRD-IAC-008
def test_aws_name_longer_than_the_limit_gets_a_hash_of_the_full_name() -> None:
    full = "order-service-staging-order-api-service"
    name = names.aws_name("order-service", "staging", "orderApiService", "alb")
    assert len(full) > names.NAME_LIMITS["alb"]
    assert name == f"order-service-staging-o-{_hash(full)}"
    assert len(name) == names.NAME_LIMITS["alb"]


# trace: PRD-IAC-008
def test_two_long_names_with_the_same_start_get_different_names() -> None:
    first = names.aws_name("order-service", "staging", "orderApiServiceOne", "target_group")
    second = names.aws_name("order-service", "staging", "orderApiServiceTwo", "target_group")
    assert first != second
    assert first[:-8] == second[:-8]


# trace: PRD-IAC-008
def test_shorter_name_does_not_end_the_start_with_a_hyphen() -> None:
    full = "abcdefghijklmnopqrstuvw-xyz-0123456789"
    assert names.shorten(full, 32) == f"abcdefghijklmnopqrstuvw-{_hash(full)}"
    assert names.shorten("a" * 22 + "-" + "b" * 20, 32) == "a" * 22 + "-" + _hash(
        "a" * 22 + "-" + "b" * 20
    )


def test_name_at_the_limit_does_not_change() -> None:
    assert names.shorten("a" * 32, 32) == "a" * 32


def test_unknown_resource_type_and_small_limit_give_an_error() -> None:
    with pytest.raises(ValueError, match="has no name limit"):
        names.aws_name("p", "dev", "x", "aws_unknown")
    with pytest.raises(ValueError, match="too small"):
        names.shorten("abc", 9)


# trace: PRD-IAC-037
def test_tag_value_of_256_characters_does_not_change() -> None:
    value = "x" * 256
    assert names.tag_value(value) == value


# trace: PRD-IAC-037
def test_tag_value_longer_than_256_characters_gets_a_hash_of_the_full_value() -> None:
    value = "Package::" + "y" * 300
    shorter = names.tag_value(value)
    assert len(shorter) == names.TAG_VALUE_LIMIT
    assert shorter == f"{value[:247]}-{_hash(value)}"


# trace: PRD-IAC-027, PRD-IAC-028
def test_ci_role_names() -> None:
    assert names.plan_role("order-service", "dev") == "order-service-dev-ci-plan"
    assert names.deploy_role("order-service", "prod") == "order-service-prod-ci-deploy"
    assert names.push_role("order-service") == "order-service-tooling-ci-push"


# trace: PRD-IAC-027
def test_long_ci_role_name_has_64_characters_or_fewer() -> None:
    product = "a-very-long-product-name-for-the-order-service-of-the-shop"
    role = names.deploy_role(product, "staging")
    assert len(role) == names.NAME_LIMITS["iam_role"]
    assert role.endswith(_hash(f"{product}-staging-ci-deploy"))


# trace: PRD-IAC-006
def test_state_bucket_ends_with_the_account_id() -> None:
    assert names.state_bucket("order-service", "dev", "222222222222") == (
        "order-service-dev-tfstate-222222222222"
    )
    product = "a-very-long-product-name-for-the-order-service"
    bucket = names.state_bucket(product, "staging", "333333333333")
    assert len(bucket) == names.NAME_LIMITS["s3_bucket"]
    assert bucket.endswith(f"-{_hash(f'{product}-staging-tfstate')}-333333333333")


# trace: PRD-IAC-004, PRD-IAC-006
def test_state_key_and_kms_alias() -> None:
    assert names.state_key("dev") == "envs/dev/terraform.tfstate"
    assert names.state_kms_alias("order-service", "dev") == "alias/order-service-dev-tfstate"


# trace: PRD-IAC-003
@pytest.mark.parametrize(
    ("value", "literal"),
    [
        ("eu-west-1", '"eu-west-1"'),
        ('a "b" \\ c', '"a \\"b\\" \\\\ c"'),
        ("${var.x} %{if}", '"$${var.x} %%{if}"'),
        ("a\nb", '"a\\nb"'),
    ],
)
def test_hcl_string_escapes_special_characters(value: str, literal: str) -> None:
    assert hcl.string(value) == literal


# trace: PRD-TRACE-006, PRD-TRACE-007
@pytest.mark.parametrize(
    ("line", "address"),
    [
        ('resource "aws_vpc" "network" {', "aws_vpc.network"),
        ('data "aws_iam_policy_document" "pull" {', "data.aws_iam_policy_document.pull"),
        ('module "network" {', "module.network"),
        ('variable "model_commit" {', "var.model_commit"),
        ('output "environment" {', "output.environment"),
        ('provider "aws" {', "provider.aws"),
        ("terraform {", "terraform"),
        ("locals {", "locals"),
        ('  backend "s3" {', None),
        ("# resource {", None),
    ],
)
def test_hcl_block_address(line: str, address: str | None) -> None:
    assert hcl.address(line) == address


def test_hcl_block_with_no_end_gives_an_error() -> None:
    with pytest.raises(ValueError, match="has no end"):
        hcl.block_symbols(
            'resource "aws_vpc" "x" {\n  cidr_block = "10.0.0.0/16"\n', lambda _: ("A",)
        )


# trace: PRD-IAC-015, PRD-IAC-022
def test_container_service_names() -> None:
    assert names.ecr_repository("order-service", "orderApi") == "order-service-tooling-order-api"
    assert (
        names.task_execution_role("order-service", "dev", "apiService")
        == "order-service-dev-api-service-execution"
    )
    assert (
        names.task_role("order-service", "dev", "apiService")
        == "order-service-dev-api-service-task"
    )
    long_role = names.task_role("order-service", "staging", "a" * 60)
    assert len(long_role) == names.NAME_LIMITS["iam_role"]
