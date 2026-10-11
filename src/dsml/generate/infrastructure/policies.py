# trace: PRD-IAC-022, PRD-IAC-027, PRD-IAC-028, PRD-IAC-033
"""The IAM policies of the tooling and the bootstrap root modules.

A policy is a list of statements. The templates write each policy as a data
source `aws_iam_policy_document`. Each value in a statement is HCL text: a
string literal from `literal`, or an HCL expression, for example
`aws_s3_bucket.state.arn`.

No policy uses the action `*` or a service wildcard such as `s3:*`
(PRD-IAC-033). An action can have a wildcard after the start of its name, for
example `ec2:Describe*`. A statement uses the resource `*` only for actions
that have no resource-level permissions in AWS, or for read actions.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from dsml.generate.infrastructure import hcl

OIDC_URL: Final = "https://token.actions.githubusercontent.com"
"""The URL of the GitHub OIDC identity provider."""

OIDC_HOST: Final = "token.actions.githubusercontent.com"
"""The host part of `OIDC_URL`, the prefix of the claim keys in conditions."""

OIDC_AUDIENCE: Final = "sts.amazonaws.com"
"""The audience of the GitHub OIDC tokens for AWS."""

MAIN_BRANCH: Final = "refs/heads/main"
"""The Git reference of the main branch."""

RELEASE_TAGS: Final = "refs/tags/v*"
"""The Git references of the release tags (PRD-CICD-001)."""

READ_ONLY_POLICY: Final = "arn:aws:iam::aws:policy/ReadOnlyAccess"
"""The AWS managed policy of the plan role (PRD-IAC-027)."""

_ACTION: Final = re.compile(r"[a-z0-9-]+:[A-Za-z0-9]+\*?")


# trace: PRD-IAC-033
def is_permitted_action(action: str) -> bool:
    """Tell if an IAM action has a service and the start of an action name.

    The action `*` and a service wildcard such as `s3:*` are not permitted
    (PRD-IAC-033).
    """
    return _ACTION.fullmatch(action) is not None


def literal(value: str) -> str:
    """Give the HCL string literal of a value."""
    return hcl.string(value)


@dataclass(frozen=True, slots=True)
class Condition:
    """A condition of a statement."""

    test: str
    variable: str
    values: tuple[str, ...]
    """HCL values."""


@dataclass(frozen=True, slots=True)
class Principal:
    """A principal of a statement."""

    type: str
    identifiers: tuple[str, ...]
    """HCL values."""


@dataclass(frozen=True, slots=True)
class Statement:
    """A statement of an IAM policy."""

    sid: str
    actions: tuple[str, ...]
    resources: tuple[str, ...] = ()
    """HCL values. A trust policy has no resources."""
    effect: str = "Allow"
    principals: tuple[Principal, ...] = ()
    conditions: tuple[Condition, ...] = ()

    def __post_init__(self) -> None:
        for action in self.actions:
            if not is_permitted_action(action):
                raise ValueError(f'The IAM action "{action}" is not permitted (PRD-IAC-033).')


@dataclass(frozen=True, slots=True)
class Policy:
    """An IAM policy document: the label of its data source and its statements."""

    name: str
    statements: tuple[Statement, ...]

    @property
    def actions(self) -> tuple[str, ...]:
        """Give the actions of all statements."""
        return tuple(action for statement in self.statements for action in statement.actions)


def _arns(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(literal(value) for value in values)


# trace: PRD-IAC-027, PRD-IAC-028
def github_trust(name: str, test: str, subjects: Iterable[str]) -> Policy:
    """Give the trust policy of a CI role for GitHub OIDC.

    The policy checks the audience, and the repository and the subject in the
    `sub` claim. Each subject is the part of the `sub` claim after the
    repository, for example `environment:dev`.
    """
    sub = tuple(
        f'"repo:${{var.github_repository}}:{literal(subject)[1:-1]}"' for subject in subjects
    )
    return Policy(
        name,
        (
            Statement(
                sid="GitHubActions",
                actions=("sts:AssumeRoleWithWebIdentity",),
                principals=(
                    Principal("Federated", ("aws_iam_openid_connect_provider.github.arn",)),
                ),
                conditions=(
                    Condition("StringEquals", f"{OIDC_HOST}:aud", (literal(OIDC_AUDIENCE),)),
                    Condition(test, f"{OIDC_HOST}:sub", sub),
                ),
            ),
        ),
    )


# trace: PRD-IAC-027
def plan_trust() -> Policy:
    """Give the trust policy of the plan role: only pull requests can use it."""
    return github_trust("plan_trust", "StringEquals", ("pull_request",))


# trace: PRD-IAC-027
def deploy_trust(environment: str) -> Policy:
    """Give the trust policy of the deploy role: only the GitHub environment can use it."""
    return github_trust("deploy_trust", "StringEquals", (f"environment:{environment}",))


# trace: PRD-IAC-028
def push_trust() -> Policy:
    """Give the trust policy of the push role: the main branch and the release tags only."""
    return github_trust("push_trust", "StringLike", (f"ref:{MAIN_BRANCH}", f"ref:{RELEASE_TAGS}"))


def _state_key_statement(state_encryption: bool) -> tuple[Statement, ...]:
    if not state_encryption:
        return ()
    return (
        Statement(
            sid="StateEncryptionKey",
            actions=("kms:Decrypt", "kms:GenerateDataKey"),
            resources=("aws_kms_key.state.arn",),
        ),
    )


# trace: PRD-IAC-006, PRD-IAC-027
def plan_policy(environment: str, state_encryption: bool) -> Policy:
    """Give the inline policy of the plan role.

    The AWS managed policy `ReadOnlyAccess` gives the read access. This policy
    adds the state lock file of the environment root module, because a plan
    writes the lock file.
    """
    prefix = f"envs/{environment}"
    return Policy(
        "plan",
        (
            Statement(
                sid="StateBucket",
                actions=("s3:ListBucket",),
                resources=("aws_s3_bucket.state.arn",),
            ),
            Statement(
                sid="StateLock",
                actions=("s3:DeleteObject", "s3:PutObject"),
                resources=(f'"${{aws_s3_bucket.state.arn}}/{prefix}/terraform.tfstate.tflock"',),
            ),
            *_state_key_statement(state_encryption),
        ),
    )


_READ_ACTIONS: Final = (
    "acm:DescribeCertificate",
    "acm:GetCertificate",
    "acm:ListCertificates",
    "acm:ListTagsForCertificate",
    "application-autoscaling:Describe*",
    "application-autoscaling:ListTagsForResource",
    "cloudwatch:Describe*",
    "cloudwatch:GetMetricData",
    "cloudwatch:ListTagsForResource",
    "cognito-idp:Describe*",
    "cognito-idp:GetGroup",
    "cognito-idp:GetUserPoolMfaConfig",
    "cognito-idp:List*",
    "ec2:Describe*",
    "ecs:Describe*",
    "ecs:List*",
    "elasticloadbalancing:Describe*",
    "iam:Get*",
    "iam:List*",
    "kms:Describe*",
    "kms:GetKeyPolicy",
    "kms:GetKeyRotationStatus",
    "kms:List*",
    "logs:Describe*",
    "logs:ListTagsForResource",
    "logs:ListTagsLogGroup",
    "rds:Describe*",
    "rds:ListTagsForResource",
    "route53:GetChange",
    "route53:GetHostedZone",
    "route53:List*",
    "secretsmanager:DescribeSecret",
    "secretsmanager:GetResourcePolicy",
    "secretsmanager:ListSecrets",
    "sts:GetCallerIdentity",
)
"""The read actions of the deploy role. They do not read secret values."""

_NO_RESOURCE_LEVEL_ACTIONS: Final = (
    "acm:RequestCertificate",
    "application-autoscaling:DeleteScalingPolicy",
    "application-autoscaling:DeregisterScalableTarget",
    "application-autoscaling:PutScalingPolicy",
    "application-autoscaling:RegisterScalableTarget",
    "application-autoscaling:TagResource",
    "application-autoscaling:UntagResource",
    "cognito-idp:CreateUserPool",
    "ecs:CreateCluster",
    "ecs:DeregisterTaskDefinition",
    "ecs:RegisterTaskDefinition",
    "kms:CreateKey",
)
"""The write actions of the deploy role that have no resource-level permissions."""

_REGIONAL_ACTIONS: Final = (
    "acm:AddTagsToCertificate",
    "acm:DeleteCertificate",
    "acm:RemoveTagsFromCertificate",
    "cognito-idp:Create*",
    "cognito-idp:Delete*",
    "cognito-idp:SetUserPoolMfaConfig",
    "cognito-idp:TagResource",
    "cognito-idp:UntagResource",
    "cognito-idp:Update*",
    "ec2:Allocate*",
    "ec2:Associate*",
    "ec2:Attach*",
    "ec2:AuthorizeSecurityGroup*",
    "ec2:Create*",
    "ec2:Delete*",
    "ec2:Detach*",
    "ec2:Disassociate*",
    "ec2:Modify*",
    "ec2:Release*",
    "ec2:Replace*",
    "ec2:RevokeSecurityGroup*",
    "ec2:UpdateSecurityGroupRuleDescriptions*",
    "ecs:CreateService",
    "ecs:DeleteCluster",
    "ecs:DeleteService",
    "ecs:PutClusterCapacityProviders",
    "ecs:RunTask",
    "ecs:StopTask",
    "ecs:TagResource",
    "ecs:UntagResource",
    "ecs:UpdateCluster",
    "ecs:UpdateService",
    "elasticloadbalancing:Add*",
    "elasticloadbalancing:Create*",
    "elasticloadbalancing:Delete*",
    "elasticloadbalancing:Modify*",
    "elasticloadbalancing:Remove*",
    "elasticloadbalancing:Set*",
    "kms:CancelKeyDeletion",
    "kms:CreateAlias",
    "kms:CreateGrant",
    "kms:DeleteAlias",
    "kms:DisableKeyRotation",
    "kms:EnableKeyRotation",
    "kms:PutKeyPolicy",
    "kms:ScheduleKeyDeletion",
    "kms:TagResource",
    "kms:UntagResource",
    "kms:UpdateAlias",
    "kms:UpdateKeyDescription",
    "logs:CreateLogGroup",
    "logs:DeleteLogGroup",
    "logs:DeleteRetentionPolicy",
    "logs:PutRetentionPolicy",
    "logs:TagLogGroup",
    "logs:TagResource",
    "logs:UntagLogGroup",
    "logs:UntagResource",
    "rds:AddTagsToResource",
    "rds:Create*",
    "rds:Delete*",
    "rds:Modify*",
    "rds:RemoveTagsFromResource",
    "secretsmanager:CreateSecret",
    "secretsmanager:DeleteResourcePolicy",
    "secretsmanager:DeleteSecret",
    "secretsmanager:PutResourcePolicy",
    "secretsmanager:RestoreSecret",
    "secretsmanager:TagResource",
    "secretsmanager:UntagResource",
    "secretsmanager:UpdateSecret",
)
"""The write actions of the deploy role on the resources of the account in its Region."""

_REGIONAL_SERVICES: Final = (
    "acm",
    "cognito-idp",
    "ec2",
    "ecs",
    "elasticloadbalancing",
    "kms",
    "logs",
    "rds",
    "secretsmanager",
)
"""The services of `_REGIONAL_ACTIONS`."""

_ROLE_ACTIONS: Final = (
    "iam:AttachRolePolicy",
    "iam:CreatePolicy",
    "iam:CreatePolicyVersion",
    "iam:CreateRole",
    "iam:DeletePolicy",
    "iam:DeletePolicyVersion",
    "iam:DeleteRole",
    "iam:DeleteRolePolicy",
    "iam:DetachRolePolicy",
    "iam:PassRole",
    "iam:PutRolePolicy",
    "iam:TagPolicy",
    "iam:TagRole",
    "iam:UntagPolicy",
    "iam:UntagRole",
    "iam:UpdateAssumeRolePolicy",
    "iam:UpdateRole",
    "iam:UpdateRoleDescription",
)
"""The IAM actions of the deploy role on the roles and policies of the environment."""

_DNS_ACTIONS: Final = ("route53:ChangeResourceRecordSets", "route53:ChangeTagsForResource")
"""The Route 53 actions of the deploy role on the hosted zones."""


# trace: PRD-IAC-027, PRD-IAC-033
def deploy_policy(
    product: str,
    environment: str,
    account_id: str,
    region: str,
    ci_roles: Iterable[str],
    state_encryption: bool,
) -> Policy:
    """Give the inline policy of the deploy role of an environment account.

    The policy permits the changes of the environment root module. The IAM
    actions apply only to the roles and policies with the name prefix of the
    environment. A deny statement keeps the deploy role from a change of the
    CI roles.
    """
    prefix = f"{product}-{environment}-"
    roles = (
        f"arn:aws:iam::{account_id}:role/{prefix}*",
        f"arn:aws:iam::{account_id}:policy/{prefix}*",
    )
    state = f"envs/{environment}"
    return Policy(
        "deploy",
        (
            Statement(sid="Read", actions=_READ_ACTIONS, resources=(literal("*"),)),
            Statement(
                sid="CreateWithNoResourceLevel",
                actions=_NO_RESOURCE_LEVEL_ACTIONS,
                resources=(literal("*"),),
                conditions=(Condition("StringEquals", "aws:RequestedRegion", (literal(region),)),),
            ),
            Statement(
                sid="ManageInRegion",
                actions=_REGIONAL_ACTIONS,
                resources=_arns(
                    f"arn:aws:{service}:{region}:{account_id}:*" for service in _REGIONAL_SERVICES
                ),
            ),
            Statement(
                sid="ManageRoles",
                actions=_ROLE_ACTIONS,
                resources=_arns(roles),
            ),
            Statement(
                sid="KeepCiRoles",
                effect="Deny",
                actions=_ROLE_ACTIONS,
                resources=_arns(f"arn:aws:iam::{account_id}:role/{role}" for role in ci_roles),
            ),
            Statement(
                sid="ServiceLinkedRoles",
                actions=("iam:CreateServiceLinkedRole",),
                resources=_arns((f"arn:aws:iam::{account_id}:role/aws-service-role/*",)),
            ),
            Statement(
                sid="Dns",
                actions=_DNS_ACTIONS,
                resources=_arns(("arn:aws:route53:::hostedzone/*",)),
            ),
            Statement(
                sid="StateBucket",
                actions=("s3:ListBucket",),
                resources=("aws_s3_bucket.state.arn",),
            ),
            Statement(
                sid="State",
                actions=("s3:DeleteObject", "s3:GetObject", "s3:PutObject"),
                resources=(f'"${{aws_s3_bucket.state.arn}}/{state}/*"',),
            ),
            *_state_key_statement(state_encryption),
        ),
    )


_PUSH_ACTIONS: Final = (
    "ecr:BatchCheckLayerAvailability",
    "ecr:BatchGetImage",
    "ecr:CompleteLayerUpload",
    "ecr:DescribeImages",
    "ecr:GetDownloadUrlForLayer",
    "ecr:InitiateLayerUpload",
    "ecr:PutImage",
    "ecr:UploadLayerPart",
)
"""The ECR actions of the push role on the repositories."""

PULL_ACTIONS: Final = (
    "ecr:BatchCheckLayerAvailability",
    "ecr:BatchGetImage",
    "ecr:GetDownloadUrlForLayer",
)
"""The ECR actions of an image pull."""


# trace: PRD-IAC-028, PRD-IAC-033
def push_policy(account_id: str, region: str, repositories: Iterable[str]) -> Policy:
    """Give the inline policy of the push role of the tooling account."""
    arns = _arns(
        f"arn:aws:ecr:{region}:{account_id}:repository/{repository}"
        for repository in sorted(repositories)
    )
    statements = [
        Statement(
            sid="Login",
            actions=("ecr:GetAuthorizationToken",),
            resources=(literal("*"),),
        )
    ]
    if arns:
        statements.append(Statement(sid="Push", actions=_PUSH_ACTIONS, resources=arns))
    return Policy("push", tuple(statements))


# trace: PRD-IAC-022, PRD-IAC-033
def pull_policy(name: str, accounts: Iterable[str], roles: Iterable[str]) -> Policy:
    """Give the repository policy of an ECR repository.

    The policy permits image pulls by the task execution roles of the
    environment accounts. The principals are the accounts, and a condition
    gives the role ARNs, because a role ARN in a principal must exist before
    the policy.
    """
    return Policy(
        name,
        (
            Statement(
                sid="PullByTaskExecutionRoles",
                actions=PULL_ACTIONS,
                principals=(
                    Principal(
                        "AWS",
                        _arns(f"arn:aws:iam::{account}:root" for account in sorted(set(accounts))),
                    ),
                ),
                conditions=(Condition("ArnLike", "aws:PrincipalArn", _arns(sorted(roles))),),
            ),
        ),
    )
