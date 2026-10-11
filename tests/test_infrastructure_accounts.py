"""Tests of the tooling root module and the bootstrap root modules (story #82).

The golden files in `tests/golden/infrastructure/order-service/` include the
output of these tests. If a change of the output is correct, run
`uv run python scripts/write_golden_infrastructure.py`.
"""

import dataclasses
import re
from pathlib import Path, PurePosixPath

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Configuration, OpenTofuOptions
from dsml.errors import ToolchainError
from dsml.generate.infrastructure import names, policies
from dsml.generate.infrastructure.accounts import (
    BOOTSTRAP_FILES,
    README,
    TOOLING_FILES,
    tooling_account,
)
from dsml.generate.infrastructure.generator import InfrastructureGenerator
from dsml.generate.writer import Kind, OutputFile, check_files
from dsml.ir.model import Ir

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
INFRA = PurePosixPath("infra")
ACCOUNTS = {
    "dev": "222222222222",
    "prod": "444444444444",
    "staging": "333333333333",
    "tooling": "111111111111",
}
_ACTIONS = re.compile(r"^( *)actions = \[\n(.*?)^\1\]", re.MULTILINE | re.DOTALL)


@pytest.fixture(scope="module")
def ir() -> Ir:
    return make_ir([EXAMPLE], ROOT)


def _generate(ir: Ir, configuration: Configuration | None = None) -> dict[str, OutputFile]:
    if configuration is None:
        configuration = Configuration(infrastructure=INFRA)
    files = InfrastructureGenerator().generate(ir, configuration, None)
    return {file.path: file for file in files}


def _text(files: dict[str, OutputFile], path: str) -> str:
    return files[f"infra/{path}"].content.decode("utf-8")


def _block(text: str, start: str) -> str:
    """Give the top-level block of HCL text that starts with the line `start`."""
    first = text.index(f"{start}\n")
    return text[first : text.index("\n}\n", first) + 3]


def _actions(text: str) -> list[str]:
    """Give each action of each `actions` list of HCL text."""
    return [
        action
        for match in _ACTIONS.finditer(text)
        for action in re.findall(r'"([^"]*)"', match.group(2))
    ]


# trace: PRD-IAC-001, PRD-IAC-002, PRD-IAC-029
def test_generator_writes_the_tooling_and_the_bootstrap_root_modules(ir: Ir) -> None:
    files = _generate(ir)
    paths = sorted(
        path for path in files if path.startswith(("infra/tooling/", "infra/bootstrap/"))
    )
    assert paths == sorted(
        [f"infra/tooling/{name}.gen.tf" for name in TOOLING_FILES]
        + [
            f"infra/bootstrap/{account}/{name}"
            for account in ACCOUNTS
            for name in (*(f"{file}.gen.tf" for file in BOOTSTRAP_FILES), README)
        ]
    )
    for file in files.values():
        assert file.kind is Kind.GENERATED
    check_files(list(files.values()))


# trace: PRD-IAC-029
def test_bootstrap_starts_with_local_state(ir: Ir) -> None:
    files = _generate(ir)
    for account in ACCOUNTS:
        for name in BOOTSTRAP_FILES:
            assert 'backend "s3"' not in _text(files, f"bootstrap/{account}/{name}.gen.tf")


# trace: PRD-IAC-029
def test_readme_gives_the_command_that_moves_the_state_into_the_bucket(ir: Ir) -> None:
    text = _text(_generate(ir), f"bootstrap/staging/{README}")
    assert "2. Run `tofu init -migrate-state`.\n" in text
    assert '       bucket       = "order-service-staging-tfstate-333333333333"\n' in text
    assert '       key          = "bootstrap/terraform.tfstate"\n' in text
    assert "       use_lockfile = true\n" in text
    assert "The toolchain does not create AWS accounts.\n" in text


# trace: PRD-IAC-006, PRD-IAC-026, PRD-IAC-030, PRD-IAC-031
def test_bootstrap_writes_the_state_bucket_and_the_oidc_provider(ir: Ir) -> None:
    text = _text(_generate(ir), "bootstrap/prod/main.gen.tf")
    bucket = _block(text, 'resource "aws_s3_bucket" "state" {')
    assert '  bucket = "order-service-prod-tfstate-444444444444"\n' in bucket
    assert names.state_bucket("order-service", "prod", "444444444444") in bucket
    assert '    status = "Enabled"\n' in _block(
        text, 'resource "aws_s3_bucket_versioning" "state" {'
    )
    assert '      sse_algorithm = "AES256"\n' in _block(
        text, 'resource "aws_s3_bucket_server_side_encryption_configuration" "state" {'
    )
    public = _block(text, 'resource "aws_s3_bucket_public_access_block" "state" {')
    for setting in ("block_public_acls", "block_public_policy", "ignore_public_acls"):
        assert re.search(rf"^  {setting} += true$", public, re.MULTILINE), setting
    assert "  restrict_public_buckets = true\n" in public
    oidc = _block(text, 'resource "aws_iam_openid_connect_provider" "github" {')
    assert '  url            = "https://token.actions.githubusercontent.com"\n' in oidc
    assert '  client_id_list = ["sts.amazonaws.com"]\n' in oidc
    assert "aws_kms_key" not in text


# trace: PRD-IAC-024, PRD-IAC-035
def test_each_account_root_module_sets_its_account_and_tags(ir: Ir) -> None:
    files = _generate(ir)
    for account, account_id in ACCOUNTS.items():
        folders = [f"bootstrap/{account}"] + (["tooling"] if account == "tooling" else [])
        for folder in folders:
            main = _text(files, f"{folder}/main.gen.tf")
            assert f'  aws_account_id = "{account_id}"\n' in main
            assert f'  environment    = "{account}"\n' in main
            providers = _text(files, f"{folder}/providers.gen.tf")
            assert "  allowed_account_ids = [local.aws_account_id]\n" in providers
            assert f'      "dsml:environment"  = "{account}"\n' in providers
            assert '      "dsml:model-commit" = var.model_commit\n' in providers


# trace: PRD-IAC-027
@pytest.mark.parametrize("environment", ["dev", "prod", "staging"])
def test_plan_and_deploy_roles_check_the_repository_and_the_environment(
    ir: Ir, environment: str
) -> None:
    text = _text(_generate(ir), f"bootstrap/{environment}/iam.gen.tf")
    plan = _block(text, 'data "aws_iam_policy_document" "plan_trust" {')
    assert (
        '      test     = "StringEquals"\n'
        '      variable = "token.actions.githubusercontent.com:sub"\n'
        "      values = [\n"
        '        "repo:${var.github_repository}:pull_request",\n'
        "      ]\n"
    ) in plan
    deploy = _block(text, 'data "aws_iam_policy_document" "deploy_trust" {')
    assert (
        '      test     = "StringEquals"\n'
        '      variable = "token.actions.githubusercontent.com:sub"\n'
        "      values = [\n"
        f'        "repo:${{var.github_repository}}:environment:{environment}",\n'
        "      ]\n"
    ) in deploy
    for trust in (plan, deploy):
        assert '      variable = "token.actions.githubusercontent.com:aud"\n' in trust
        assert "        aws_iam_openid_connect_provider.github.arn,\n" in trust
    assert f'  name               = "{names.plan_role("order-service", environment)}"\n' in text
    assert f'  name               = "{names.deploy_role("order-service", environment)}"\n' in text
    assert '  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"\n' in text
    assert 'resource "aws_iam_role" "push"' not in text


# trace: PRD-IAC-028
def test_push_role_permits_only_the_main_branch_and_the_release_tags(ir: Ir) -> None:
    text = _text(_generate(ir), "bootstrap/tooling/iam.gen.tf")
    trust = _block(text, 'data "aws_iam_policy_document" "push_trust" {')
    assert (
        '      test     = "StringLike"\n'
        '      variable = "token.actions.githubusercontent.com:sub"\n'
        "      values = [\n"
        '        "repo:${var.github_repository}:ref:refs/heads/main",\n'
        '        "repo:${var.github_repository}:ref:refs/tags/v*",\n'
        "      ]\n"
    ) in trust
    assert '  name               = "order-service-tooling-ci-push"\n' in text
    assert names.push_role("order-service") == "order-service-tooling-ci-push"
    assert (
        '      "arn:aws:ecr:eu-west-1:111111111111:repository/order-service-tooling-order-api",\n'
    ) in _block(text, 'data "aws_iam_policy_document" "push" {')
    assert 'resource "aws_iam_role" "plan"' not in text
    assert 'resource "aws_iam_role" "deploy"' not in text


# trace: PRD-IAC-027
def test_deploy_role_cannot_change_the_ci_roles(ir: Ir) -> None:
    text = _text(_generate(ir), "bootstrap/dev/iam.gen.tf")
    policy = _block(text, 'data "aws_iam_policy_document" "deploy" {')
    deny = policy[policy.index('    sid    = "KeepCiRoles"\n') :]
    deny = deny[: deny.index("\n  }\n")]
    assert '    effect = "Deny"\n' in deny
    assert '      "arn:aws:iam::222222222222:role/order-service-dev-ci-deploy",\n' in deny
    assert '      "arn:aws:iam::222222222222:role/order-service-dev-ci-plan",\n' in deny
    assert '      "iam:PutRolePolicy",\n' in deny


# trace: PRD-IAC-033
def test_no_iam_policy_uses_the_action_star_or_a_service_wildcard(ir: Ir) -> None:
    for configuration in (
        Configuration(infrastructure=INFRA),
        Configuration(infrastructure=INFRA, opentofu=OpenTofuOptions(state_encryption=True)),
    ):
        actions = [
            action
            for file in _generate(ir, configuration).values()
            for action in _actions(file.content.decode("utf-8"))
        ]
        assert len(actions) > 100
        for action in actions:
            assert action != "*"
            assert not action.endswith(":*"), action
            assert re.fullmatch(r"[a-z0-9-]+:[A-Za-z0-9]+\*?", action), action


# trace: PRD-IAC-033
@pytest.mark.parametrize("action", ["*", "s3:*", "s3", "*:GetObject", "s3:Get*Object"])
def test_statement_rejects_the_action_star_and_a_service_wildcard(action: str) -> None:
    assert not policies.is_permitted_action(action)
    with pytest.raises(ValueError, match="PRD-IAC-033"):
        policies.Statement(sid="Test", actions=(action,), resources=('"*"',))


# trace: PRD-IAC-022, PRD-IAC-030
def test_tooling_writes_an_ecr_repository_for_each_container_application(ir: Ir) -> None:
    text = _text(_generate(ir), "tooling/main.gen.tf")
    repository = _block(text, 'resource "aws_ecr_repository" "order_api" {')
    assert '  name                 = "order-service-tooling-order-api"\n' in repository
    assert '  image_tag_mutability = "IMMUTABLE"\n' in repository
    assert "    scan_on_push = true\n" in repository
    assert '    encryption_type = "KMS"\n' in repository
    assert '    "dsml:element"     = "OrderService::orderApi"\n' in repository
    lifecycle = _block(text, 'resource "aws_ecr_lifecycle_policy" "order_api" {')
    assert '          tagStatus   = "untagged"\n' in lifecycle
    assert text.count('resource "aws_ecr_repository" ') == 1


# trace: PRD-IAC-015, PRD-IAC-022
def test_repository_policy_permits_pulls_by_the_task_execution_roles(ir: Ir) -> None:
    text = _text(_generate(ir), "tooling/main.gen.tf")
    policy = _block(text, 'data "aws_iam_policy_document" "order_api_pull" {')
    assert _actions(policy) == list(policies.PULL_ACTIONS)
    for environment in ("dev", "prod", "staging"):
        account = ACCOUNTS[environment]
        role = names.task_execution_role("order-service", environment, "apiService")
        assert role == f"order-service-{environment}-api-service-execution"
        assert f'        "arn:aws:iam::{account}:role/{role}",\n' in policy
        assert f'        "arn:aws:iam::{account}:root",\n' in policy
    assert '      variable = "aws:PrincipalArn"\n' in policy


# trace: PRD-IAC-006, PRD-IAC-022
def test_tooling_state_is_in_the_bucket_of_the_tooling_account(ir: Ir) -> None:
    text = _text(_generate(ir), "tooling/backend.gen.tf")
    assert '    bucket       = "order-service-tooling-tfstate-111111111111"\n' in text
    assert '    key          = "tooling/terraform.tfstate"\n' in text


# trace: PRD-IAC-004
def test_state_encryption_gives_the_key_and_the_key_access_of_the_roles(ir: Ir) -> None:
    configuration = Configuration(
        infrastructure=INFRA, opentofu=OpenTofuOptions(state_encryption=True)
    )
    files = _generate(ir, configuration)
    main = _text(files, "bootstrap/dev/main.gen.tf")
    assert 'resource "aws_kms_key" "state" {' in main
    assert '  name          = "alias/order-service-dev-tfstate"\n' in main
    iam = _text(files, "bootstrap/dev/iam.gen.tf")
    assert iam.count('    sid    = "StateEncryptionKey"\n') == 2
    assert '  name          = "alias/order-service-tooling-tfstate"\n' in _text(
        files, "bootstrap/tooling/main.gen.tf"
    )


# trace: PRD-TRACE-006, PRD-TRACE-007
def test_ecr_blocks_are_symbols_of_the_application(ir: Ir) -> None:
    file = _generate(ir)["infra/tooling/main.gen.tf"]
    owners = {symbol.name: symbol.elements for symbol in file.symbols}
    assert owners == {
        "locals": ("OrderService::tooling",),
        "aws_ecr_repository.order_api": ("OrderService::orderApi",),
        "aws_ecr_lifecycle_policy.order_api": ("OrderService::orderApi",),
        "aws_ecr_repository_policy.order_api": ("OrderService::orderApi",),
        "data.aws_iam_policy_document.order_api_pull": ("OrderService::orderApi",),
    }
    bootstrap = _generate(ir)["infra/bootstrap/dev/iam.gen.tf"]
    assert {symbol.elements for symbol in bootstrap.symbols} == {("OrderService::dev",)}


def test_model_with_no_tooling_account_gives_no_account(ir: Ir) -> None:
    elements = tuple(element for element in ir.elements if element.kind != "ToolingAccount")
    model = dataclasses.replace(ir, elements=elements)
    assert tooling_account(model, lambda element: "order-service") is None


def test_model_with_two_tooling_accounts_stops(ir: Ir) -> None:
    tooling = next(element for element in ir.elements if element.kind == "ToolingAccount")
    second = dataclasses.replace(tooling, identity="OrderService::tooling2", name="tooling2")
    with pytest.raises(ToolchainError, match="one #ToolingAccount element, not 2"):
        _generate(dataclasses.replace(ir, elements=(*ir.elements, second)))
