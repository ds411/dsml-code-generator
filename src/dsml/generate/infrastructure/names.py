# trace: PRD-IAC-008, PRD-IAC-037
"""The names of the infrastructure: HCL addresses, AWS names, tag values and CI roles.

All infrastructure and pipeline generators get their names from this module,
so that each generator uses the same name for the same AWS resource.

- An HCL address is the snake case of the element name, for example
  `api_service` (PRD-IAC-008).
- An AWS name has the form `<product>-<environment>-<element>`, each part in
  kebab case, for example `order-service-dev-api-service` (PRD-IAC-008).
- If a name is longer than the AWS limit of its resource type, the function
  `shorten` cuts it and adds a hash of the full name. The same full name
  always gives the same shorter name.
- If a tag value is longer than 256 characters, the function `tag_value`
  cuts it and adds a hash of the full value (PRD-IAC-037).
"""

import hashlib
from typing import Final

from dsml.generate import names

HASH_LENGTH: Final = 8
"""The number of hexadecimal characters of the hash in a shorter name."""

TAG_VALUE_LIMIT: Final = 256
"""The maximum number of characters of an AWS tag value."""

NAME_LIMITS: Final = {
    "alb": 32,
    "cloudfront_origin_access_control": 64,
    "cloudwatch_log_group": 512,
    "cognito_app_client": 128,
    "cognito_domain": 63,
    "cognito_user_pool": 128,
    "db_instance": 63,
    "ecr_repository": 256,
    "ecs_cluster": 255,
    "ecs_service": 255,
    "ecs_task_definition": 255,
    "iam_policy": 128,
    "iam_role": 64,
    "kms_alias": 256,
    "s3_bucket": 63,
    "secret": 512,
    "security_group": 255,
    "target_group": 32,
    "vpc": 224,
}
"""The maximum number of characters of the name of each AWS resource type.

The name of a VPC is its tag `Name`. The network module adds a suffix of 32
characters or fewer to the names of the subnets and the gateways of the VPC.
Thus the limit of a VPC name is less than the limit of a tag value.
"""

TOOLING: Final = "tooling"
"""The name of the tooling account in AWS names."""

PLAN_ROLE: Final = "ci-plan"
"""The element part of the name of the plan role (PRD-IAC-027)."""

DEPLOY_ROLE: Final = "ci-deploy"
"""The element part of the name of the deploy role (PRD-IAC-027)."""

PUSH_ROLE: Final = "ci-push"
"""The element part of the name of the push role (PRD-IAC-028)."""

STATE: Final = "tfstate"
"""The element part of the names of the state bucket and the state key."""


# trace: PRD-IAC-008
def hcl_address(name: str) -> str:
    """Give the HCL name of a model element: the snake case of its name."""
    return names.snake_case(name)


def full_hash(text: str) -> str:
    """Give the first characters of the SHA-256 hash of a text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:HASH_LENGTH]


# trace: PRD-IAC-008, PRD-IAC-037
def shorten(text: str, limit: int) -> str:
    """Give the text if it has `limit` characters or fewer. Else give a shorter text.

    The shorter text is the start of the text, then "-" and a hash of the
    full text. It has exactly `limit` characters, or fewer if the start ends
    with "-".
    """
    if limit <= HASH_LENGTH + 1:
        raise ValueError(f"The limit {limit} is too small for a name with a hash.")
    if len(text) <= limit:
        return text
    start = text[: limit - HASH_LENGTH - 1].rstrip("-")
    return f"{start}-{full_hash(text)}"


def name_limit(resource_type: str) -> int:
    """Give the AWS limit of the name of a resource type of `NAME_LIMITS`."""
    try:
        return NAME_LIMITS[resource_type]
    except KeyError:
        raise ValueError(f'The resource type "{resource_type}" has no name limit.') from None


# trace: PRD-IAC-008
def aws_name(product: str, environment: str, element: str, resource_type: str) -> str:
    """Give the AWS name `<product>-<environment>-<element>` of a resource.

    Each part is in kebab case. If the name is longer than the limit of the
    resource type, the function gives a shorter name with a hash.
    """
    full = "-".join(names.kebab_case(part) for part in (product, environment, element))
    return shorten(full, name_limit(resource_type))


# trace: PRD-IAC-035, PRD-IAC-037
def tag_value(value: str) -> str:
    """Give a tag value with 256 characters or fewer."""
    return shorten(value, TAG_VALUE_LIMIT)


# trace: PRD-IAC-006, PRD-IAC-026
def state_bucket(product: str, environment: str, account_id: str) -> str:
    """Give the name of the state bucket of an account.

    S3 bucket names are global, thus the name ends with the account ID. The
    start of the name gets a hash if the full name is too long.
    """
    end = f"-{account_id}"
    start = "-".join(names.kebab_case(part) for part in (product, environment, STATE))
    return shorten(start, name_limit("s3_bucket") - len(end)) + end


# trace: PRD-IAC-008, PRD-IAC-021
def site_bucket(product: str, environment: str, element: str, account_id: str) -> str:
    """Give the name of the S3 bucket of a static site.

    S3 bucket names are global, thus the name ends with the account ID. The
    start of the name gets a hash if the full name is too long.
    """
    end = f"-{account_id}"
    start = "-".join(names.kebab_case(part) for part in (product, environment, element))
    return shorten(start, name_limit("s3_bucket") - len(end)) + end


# trace: PRD-IAC-006
def state_key(environment: str) -> str:
    """Give the key of the state file of an environment root module in its bucket."""
    return f"envs/{names.kebab_case(environment)}/terraform.tfstate"


# trace: PRD-IAC-004
def state_kms_alias(product: str, environment: str) -> str:
    """Give the KMS alias of the OpenTofu state encryption key of an account."""
    prefix = "alias/"
    full = "-".join(names.kebab_case(part) for part in (product, environment, STATE))
    return prefix + shorten(full, name_limit("kms_alias") - len(prefix))


# trace: PRD-IAC-008, PRD-IAC-020
def kms_alias(product: str, environment: str, element: str) -> str:
    """Give the KMS alias `alias/<product>-<environment>-<element>` of the key of an element."""
    prefix = "alias/"
    full = "-".join(names.kebab_case(part) for part in (product, environment, element))
    return prefix + shorten(full, name_limit("kms_alias") - len(prefix))


# trace: PRD-IAC-027
def plan_role(product: str, environment: str) -> str:
    """Give the name of the plan role of an environment account."""
    return aws_name(product, environment, PLAN_ROLE, "iam_role")


# trace: PRD-IAC-027
def deploy_role(product: str, environment: str) -> str:
    """Give the name of the deploy role of an environment account."""
    return aws_name(product, environment, DEPLOY_ROLE, "iam_role")


# trace: PRD-IAC-028
def push_role(product: str) -> str:
    """Give the name of the push role of the tooling account."""
    return aws_name(product, TOOLING, PUSH_ROLE, "iam_role")


# trace: PRD-IAC-008, PRD-IAC-022
def ecr_repository(product: str, application: str) -> str:
    """Give the name of the ECR repository of an application in the tooling account."""
    return aws_name(product, TOOLING, application, "ecr_repository")


# trace: PRD-IAC-015, PRD-IAC-022
def task_execution_role(product: str, environment: str, element: str) -> str:
    """Give the name of the task execution role of a container service.

    The ECR repository policy of the tooling account permits pulls by this role.
    """
    return aws_name(product, environment, f"{names.kebab_case(element)}-execution", "iam_role")


# trace: PRD-IAC-015
def task_role(product: str, environment: str, element: str) -> str:
    """Give the name of the task role of a container service."""
    return aws_name(product, environment, f"{names.kebab_case(element)}-task", "iam_role")


# trace: PRD-IAC-006, PRD-IAC-022
def tooling_state_key() -> str:
    """Give the key of the state file of the tooling root module in its bucket."""
    return f"{TOOLING}/terraform.tfstate"


# trace: PRD-IAC-029
def bootstrap_state_key() -> str:
    """Give the key of the state file of a bootstrap root module in its bucket."""
    return "bootstrap/terraform.tfstate"
