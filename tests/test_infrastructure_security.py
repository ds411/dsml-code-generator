"""Tests of the security baseline of the generated infrastructure (story #86).

The tests read the golden HCL of the reference models and of the test model
in `tests/golden/infrastructure/`. Story #162 added the order portal with the
static site. The golden-file tests make sure that the
generator writes the same files. The toolchain CI also runs Checkov on these
files (PRD-IAC-040).
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from dsml.versions import load_baseline

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "infrastructure"
MODELS = ("order-portal", "order-service", "shop")
OPEN_CIDRS = ('"0.0.0.0/0"', '"::/0"')

_START = re.compile(r'^(resource|data) "([a-z0-9_]+)" "([a-z0-9_]+)" \{$')
_LIST = re.compile(r"^\s*(?:actions|not_actions) = \[\n(.*?)\n\s*\]", re.MULTILINE | re.DOTALL)
_ONE_LINE_LIST = re.compile(r"^\s*(?:actions|not_actions)\s*= \[(.+)\]$", re.MULTILINE)
_SETTING = r"^\s*{name}\s*=\s*{value}$"


@dataclass(frozen=True, slots=True)
class Block:
    """One top-level resource or data source block of an HCL file."""

    path: str
    kind: str
    type: str
    name: str
    body: str

    def has(self, name: str, value: str) -> bool:
        """Tell if the block sets the argument `name` to the HCL text `value`."""
        pattern = _SETTING.format(name=re.escape(name), value=re.escape(value))
        return re.search(pattern, self.body, re.MULTILINE) is not None

    def value(self, name: str) -> str | None:
        """Give the HCL text of a one-line argument, or None."""
        match = re.search(rf"^\s*{re.escape(name)}\s*=\s*(.+)$", self.body, re.MULTILINE)
        return match.group(1) if match else None


def _blocks(text: str, path: str) -> list[Block]:
    blocks: list[Block] = []
    lines = text.split("\n")
    for index, line in enumerate(lines):
        match = _START.match(line)
        if match:
            end = lines.index("}", index)
            body = "\n".join(lines[index + 1 : end])
            blocks.append(Block(path, match[1], match[2], match[3], body))
    return blocks


def _read(model: str) -> list[Block]:
    folder = GOLDEN / model
    blocks: list[Block] = []
    for path in sorted(folder.rglob("*.tf")):
        relative = path.relative_to(folder).as_posix()
        blocks.extend(_blocks(path.read_text(encoding="utf-8"), relative))
    return blocks


@pytest.fixture(scope="module", params=MODELS)
def blocks(request: pytest.FixtureRequest) -> list[Block]:
    model: str = request.param
    return _read(model)


def _of(blocks: list[Block], kind: str) -> list[Block]:
    return [block for block in blocks if block.kind == "resource" and block.type == kind]


def _for_bucket(blocks: list[Block], kind: str, bucket: Block) -> list[Block]:
    """Give the blocks of the type `kind` in the same file that refer to `bucket`."""
    reference = f"aws_s3_bucket.{bucket.name}.id"
    return [
        block
        for block in _of(blocks, kind)
        if block.path == bucket.path and block.value("bucket") == reference
    ]


def test_the_golden_output_has_the_resources_that_store_data() -> None:
    kinds = {block.type for model in MODELS for block in _read(model)}
    for kind in (
        "aws_cloudfront_distribution",
        "aws_db_instance",
        "aws_ecr_repository",
        "aws_s3_bucket",
        "aws_secretsmanager_secret",
        "aws_security_group",
        "aws_vpc_security_group_ingress_rule",
    ):
        assert kind in kinds, kind


# trace: PRD-IAC-030
def test_each_s3_bucket_has_encryption_at_rest(blocks: list[Block]) -> None:
    for bucket in _of(blocks, "aws_s3_bucket"):
        configurations = _for_bucket(
            blocks, "aws_s3_bucket_server_side_encryption_configuration", bucket
        )
        assert len(configurations) == 1, (bucket.path, bucket.name)
        algorithm = configurations[0].value("sse_algorithm")
        assert algorithm in ('"AES256"', '"aws:kms"', '"aws:kms:dsse"'), bucket.path


# trace: PRD-IAC-030
def test_each_database_has_encryption_at_rest(blocks: list[Block]) -> None:
    for database in _of(blocks, "aws_db_instance"):
        assert database.has("storage_encrypted", "true"), database.path
        assert database.value("kms_key_id") is not None, database.path


# trace: PRD-IAC-030
def test_each_secret_has_a_kms_key(blocks: list[Block]) -> None:
    for secret in _of(blocks, "aws_secretsmanager_secret"):
        assert secret.value("kms_key_id") is not None, secret.path


# trace: PRD-IAC-030
def test_each_ecr_repository_has_encryption_at_rest(blocks: list[Block]) -> None:
    for repository in _of(blocks, "aws_ecr_repository"):
        assert "  encryption_configuration {\n" in repository.body, repository.path
        assert repository.value("encryption_type") in ('"KMS"', '"AES256"'), repository.path


# trace: PRD-IAC-031
def test_no_database_is_public(blocks: list[Block]) -> None:
    for database in _of(blocks, "aws_db_instance"):
        assert database.has("publicly_accessible", "false"), database.path


# trace: PRD-IAC-031
def test_each_s3_bucket_blocks_public_access(blocks: list[Block]) -> None:
    for bucket in _of(blocks, "aws_s3_bucket"):
        blocks_of_bucket = _for_bucket(blocks, "aws_s3_bucket_public_access_block", bucket)
        assert len(blocks_of_bucket) == 1, (bucket.path, bucket.name)
        for setting in (
            "block_public_acls",
            "block_public_policy",
            "ignore_public_acls",
            "restrict_public_buckets",
        ):
            assert blocks_of_bucket[0].has(setting, "true"), (bucket.path, setting)


# trace: PRD-IAC-031, PRD-IAC-032
def test_security_groups_have_no_inline_rules(blocks: list[Block]) -> None:
    # Separate rule resources hold all rules, so the next test sees each
    # ingress rule.
    for kind in ("aws_security_group", "aws_default_security_group"):
        for group in _of(blocks, kind):
            assert "ingress" not in group.body, (group.path, group.name)
            assert "egress" not in group.body, (group.path, group.name)
    assert _of(blocks, "aws_security_group_rule") == []


# trace: PRD-IAC-031, PRD-IAC-032
def test_only_the_alb_accepts_ingress_from_the_internet(blocks: list[Block]) -> None:
    open_rules = [
        rule
        for rule in _of(blocks, "aws_vpc_security_group_ingress_rule")
        if rule.value("cidr_ipv4") in OPEN_CIDRS or rule.value("cidr_ipv6") in OPEN_CIDRS
    ]
    assert open_rules, "The ALB must accept HTTPS from the internet."
    for rule in open_rules:
        assert rule.path == "infra/modules/container-service/main.gen.tf", rule.path
        assert rule.value("security_group_id") == "aws_security_group.alb.id", rule.name
        assert rule.value("for_each") == 'toset(["80", "443"])', rule.name
        assert rule.value("from_port") == "tonumber(each.key)", rule.name
        assert rule.value("to_port") == "tonumber(each.key)", rule.name


# trace: PRD-IAC-033
def test_iam_policies_come_from_policy_documents(blocks: list[Block]) -> None:
    for block in blocks:
        if block.kind != "resource":
            continue
        for name in ("policy", "assume_role_policy"):
            value = block.value(name)
            if value is None or block.type == "aws_ecr_lifecycle_policy":
                continue
            assert value.startswith("data.aws_iam_policy_document."), (block.path, block.name)
    for kind in ("aws_iam_policy", "aws_iam_role_policy", "aws_iam_role"):
        for block in _of(blocks, kind):
            assert "inline_policy" not in block.body, (block.path, block.name)


# trace: PRD-IAC-033
def test_no_iam_action_is_a_wildcard(blocks: list[Block]) -> None:
    documents = [block for block in blocks if block.type == "aws_iam_policy_document"]
    assert documents
    actions = [
        action
        for document in documents
        for actions in (*_LIST.findall(document.body), *_ONE_LINE_LIST.findall(document.body))
        for action in re.findall(r'"([^"]*)"', actions)
    ]
    assert actions
    for action in actions:
        service, _, name = action.partition(":")
        assert action != "*", action
        assert service and name, action
        assert not name.startswith("*"), action


# trace: PRD-IAC-031, PRD-IAC-034
def test_each_distribution_accepts_only_https_with_the_baseline_tls_policy(
    blocks: list[Block],
) -> None:
    policy = load_baseline()["cloudfront-tls-policy"].value
    for distribution in _of(blocks, "aws_cloudfront_distribution"):
        assert distribution.has("viewer_protocol_policy", '"redirect-to-https"'), distribution.path
        assert distribution.has("minimum_protocol_version", f'"{policy}"'), distribution.path
        assert distribution.has("ssl_support_method", '"sni-only"'), distribution.path


# trace: PRD-IAC-031
def test_each_distribution_reads_its_bucket_with_origin_access_control(
    blocks: list[Block],
) -> None:
    for distribution in _of(blocks, "aws_cloudfront_distribution"):
        control = distribution.value("origin_access_control_id")
        assert control is not None, distribution.path
        assert control.startswith("aws_cloudfront_origin_access_control."), distribution.path
