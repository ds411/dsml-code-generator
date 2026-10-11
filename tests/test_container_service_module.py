"""Tests of the local module container-service and of its module calls (story #80).

The golden files in `tests/golden/infrastructure/order-service/` and
`tests/golden/infrastructure/shop/` hold the full output. These tests examine
the values that the requirements give. If a change of the output is correct,
run `uv run python scripts/write_golden_infrastructure.py`.
"""

import dataclasses
import json
import re
from pathlib import Path, PurePosixPath

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.generate.infrastructure import modules, names
from dsml.generate.infrastructure.generator import InfrastructureGenerator
from dsml.ir.model import Attribute, Element, IntegerValue, Ir
from dsml.versions import load_baseline

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
SHOP = ROOT / "tests" / "models" / "ir" / "solution-layers.sysml"
GOLDEN = ROOT / "tests" / "golden" / "infrastructure" / "order-service"
MODULE = "infra/modules/container-service"
ENVIRONMENTS = ("dev", "prod", "staging")


@pytest.fixture(scope="module")
def ir() -> Ir:
    return make_ir([EXAMPLE], ROOT)


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


def _arguments(files: dict[str, str], environment: str, address: str = "api_service") -> str:
    """Give the module call in a root module, with one space before each "="."""
    call = _block(files[f"infra/envs/{environment}/main.gen.tf"], f'module "{address}" {{')
    return re.sub(r" +=", " =", call)


def _with_attributes(ir: Ir, identity: str, **values: int) -> Ir:
    """Give a copy of the IR in which an element has more integer attributes."""
    location = next(element.location for element in ir.elements if element.identity == identity)

    def change(element: Element) -> Element:
        if element.identity != identity:
            return element
        kept = [attribute for attribute in element.attributes if attribute.name not in values]
        added = [
            Attribute(name=name, value=IntegerValue(value=value), location=location)
            for name, value in values.items()
        ]
        return dataclasses.replace(element, attributes=tuple(kept + added))

    return dataclasses.replace(ir, elements=tuple(change(element) for element in ir.elements))


# trace: PRD-IAC-001, PRD-IAC-007
def test_module_has_three_files_with_only_aws_resources(files: dict[str, str]) -> None:
    module = sorted(path for path in files if path.startswith(MODULE))
    assert module == [
        f"{MODULE}/main.gen.tf",
        f"{MODULE}/outputs.gen.tf",
        f"{MODULE}/variables.gen.tf",
    ]
    main = files[f"{MODULE}/main.gen.tf"]
    for match in re.finditer(r'^(resource|data) "([a-z0-9_]+)"', main, re.MULTILINE):
        assert match.group(2).startswith("aws_"), match.group(0)
    assert "\nmodule " not in main
    for environment in ENVIRONMENTS:
        call = _arguments(files, environment)
        assert '  source = "../../modules/container-service"\n' in call


# trace: PRD-IAC-012
def test_task_definition_and_service_use_the_values_of_the_realization(
    files: dict[str, str],
) -> None:
    dev = _arguments(files, "dev")
    assert "  cpu = 512\n" in dev
    assert "  memory = 1024\n" in dev
    assert "  desired_count = 1\n" in dev
    assert "  desired_count = 3\n" in _arguments(files, "prod")
    main = files[f"{MODULE}/main.gen.tf"]
    service = _block(main, 'resource "aws_ecs_service" "main" {')
    assert '  launch_type             = "FARGATE"\n' in service
    assert "    subnets          = var.private_subnet_ids\n" in service
    assert "    assign_public_ip = false\n" in service
    task = _block(main, 'resource "aws_ecs_task_definition" "service" {')
    assert "  cpu                      = var.cpu\n" in task
    assert "  memory                   = var.memory\n" in task


# trace: PRD-IAC-013
def test_auto_scaling_tracks_cpu_between_the_minimum_and_maximum_count(
    files: dict[str, str],
) -> None:
    dev = _arguments(files, "dev")
    assert "  min_count = 1\n" in dev
    assert "  max_count = 2\n" in dev
    prod = _arguments(files, "prod")
    assert "  min_count = 3\n" in prod
    assert "  max_count = 6\n" in prod
    main = files[f"{MODULE}/main.gen.tf"]
    target = _block(main, 'resource "aws_appautoscaling_target" "main" {')
    assert "  min_capacity       = var.min_count\n" in target
    assert "  max_capacity       = var.max_count\n" in target
    policy = _block(main, 'resource "aws_appautoscaling_policy" "cpu" {')
    assert '  policy_type        = "TargetTrackingScaling"\n' in policy
    assert '      predefined_metric_type = "ECSServiceAverageCPUUtilization"\n' in policy


# trace: PRD-IAC-013, PRD-DSML-042
def test_min_count_and_max_count_of_the_model_replace_the_default_values(ir: Ir) -> None:
    changed = _with_attributes(ir, "OrderService::apiServiceAws", minCount=2, maxCount=4)
    with pytest.raises(ToolchainError, match="minCount <= desiredCount <= maxCount"):
        _generate(changed)
    changed = _with_attributes(ir, "OrderService::apiServiceAws", minCount=1, maxCount=4)
    files = _generate(changed)
    for environment, desired in (("dev", 1), ("prod", 3)):
        call = _arguments(files, environment)
        assert f"  desired_count = {desired}\n" in call
        assert "  min_count = 1\n" in call
        assert "  max_count = 4\n" in call


# trace: PRD-IAC-014, PRD-IAC-034, PRD-APP-012
def test_alb_has_https_with_the_baseline_policy_a_redirect_and_the_health_check(
    files: dict[str, str],
) -> None:
    main = files[f"{MODULE}/main.gen.tf"]
    alb = _block(main, 'resource "aws_lb" "main" {')
    assert "  subnets                    = var.public_subnet_ids\n" in alb
    https = _block(main, 'resource "aws_lb_listener" "https" {')
    policy = load_baseline()["alb-tls-policy"].value
    assert f'  ssl_policy        = "{policy}"\n' in https
    assert "  certificate_arn   = aws_acm_certificate_validation.main.certificate_arn\n" in https
    http = _block(main, 'resource "aws_lb_listener" "http" {')
    assert '      protocol    = "HTTPS"\n      status_code = "HTTP_301"\n' in http
    group = _block(main, 'resource "aws_lb_target_group" "main" {')
    assert '    path                = "/healthz"\n' in group
    assert 'resource "aws_route53_record" "api" {' in main
    assert "  domain_name       = var.domain_name\n" in main
    dev = _arguments(files, "dev")
    assert '  domain_name = "order-api.orders.dev.example.com"\n' in dev
    assert '  zone_name = "orders.dev.example.com"\n' in dev


# trace: PRD-IAC-015, PRD-IAC-033
def test_roles_have_only_the_permitted_actions(files: dict[str, str]) -> None:
    main = files[f"{MODULE}/main.gen.tf"]
    policy = _block(main, 'data "aws_iam_policy_document" "execution" {')
    actions = sorted(set(re.findall(r'"((?:ecr|logs|secretsmanager|kms):[A-Za-z*]+)"', policy)))
    assert actions == [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:GetAuthorizationToken",
        "ecr:GetDownloadUrlForLayer",
        "kms:Decrypt",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "secretsmanager:GetSecretValue",
    ]
    assert "*" not in "".join(actions)
    # Only ecr:GetAuthorizationToken has no resource-level permissions.
    assert policy.count('resources = ["*"]') == 1
    assert '    actions   = ["ecr:GetAuthorizationToken"]\n    resources = ["*"]\n' in policy
    assert ":repository/${var.ecr_repository}" in policy
    assert "sort(distinct(var.secret_arns))" in policy
    assert "sort(distinct(var.kms_key_arns))" in policy
    # The task role has no policy: the elements of the example need no IAM access.
    task = _block(main, 'resource "aws_iam_role" "task" {')
    assert "aws_iam_policy_document.ecs_tasks_trust.json" in task
    assert "aws_iam_role.task.id" not in main
    assert "aws_iam_role.task.name" not in main


# trace: PRD-IAC-015
def test_execution_role_reads_only_the_secrets_of_the_used_elements(
    files: dict[str, str],
) -> None:
    call = _arguments(files, "dev")
    assert "  secret_arns = [module.order_db.master_user_secret_arn]\n" in call
    assert "  kms_key_arns = [module.order_db.kms_key_arn]\n" in call
    shop_call = _arguments(_generate(make_ir([SHOP], ROOT)), "dev", "api")
    assert "  secret_arns = [module.secrets.secret_arn]\n" in shop_call
    assert "  kms_key_arns = [module.secrets.key_arn]\n" in shop_call
    assert "    SECRETS = module.secrets.secret_arn\n" in shop_call


# trace: PRD-IAC-015
def test_container_gets_the_values_of_the_database_and_the_user_directory(
    files: dict[str, str],
) -> None:
    call = _arguments(files, "staging")
    assert (
        "  environment_variables = {\n"
        "    AWS_REGION = local.aws_region\n"
        '    COGNITO_APP_CLIENT_ID = module.users.app_client_ids["order_api"]\n'
        "    COGNITO_USER_POOL_ID = module.users.user_pool_id\n"
        "    DATABASE_HOST = module.order_db.address\n"
        "    DATABASE_NAME = module.order_db.database_name\n"
        "    DATABASE_PORT = tostring(module.order_db.port)\n"
        '    DATABASE_SSL_MODE = "require"\n'
        "  }\n"
    ) in call
    assert (
        "  secrets = {\n"
        '    DATABASE_PASSWORD = "${module.order_db.master_user_secret_arn}:password::"\n'
        '    DATABASE_USER = "${module.order_db.master_user_secret_arn}:username::"\n'
        "  }\n"
    ) in call
    main = files[f"{MODULE}/main.gen.tf"]
    assert "      environment = local.environment\n" in main
    assert "      secrets     = local.secrets\n" in main


# trace: PRD-IAC-031, PRD-IAC-032
def test_only_the_alb_accepts_traffic_from_the_internet_on_ports_80_and_443(
    files: dict[str, str],
) -> None:
    main = files[f"{MODULE}/main.gen.tf"]
    ingress = re.findall(
        r'^resource "aws_vpc_security_group_ingress_rule" "([a-z_]+)" \{', main, re.MULTILINE
    )
    assert ingress == ["alb", "service_from_alb"]
    alb = _block(main, 'resource "aws_vpc_security_group_ingress_rule" "alb" {')
    assert '  for_each = toset(["80", "443"])\n' in alb
    assert '  cidr_ipv4         = "0.0.0.0/0"\n' in alb
    service = _block(main, 'resource "aws_vpc_security_group_ingress_rule" "service_from_alb" {')
    assert "  referenced_security_group_id = aws_security_group.alb.id\n" in service
    assert "cidr" not in service
    assert "::/0" not in main
    assert main.count('"0.0.0.0/0"') == 2


# trace: PRD-IAC-016, PRD-APP-128
def test_log_group_keeps_logs_30_days_and_a_second_task_runs_the_migrations(
    files: dict[str, str],
) -> None:
    main = files[f"{MODULE}/main.gen.tf"]
    logs = _block(main, 'resource "aws_cloudwatch_log_group" "main" {')
    assert "  retention_in_days = 30\n" in logs
    migration = _block(main, 'resource "aws_ecs_task_definition" "migration" {')
    assert "      command     = var.migration_command\n" in migration
    call = _arguments(files, "dev")
    assert '  migration_command = ["python", "-m", "app.migrate_gen"]\n' in call


# trace: PRD-IAC-042
def test_service_ignores_its_task_definition_and_rolls_back_a_failed_deployment(
    files: dict[str, str],
) -> None:
    service = _block(files[f"{MODULE}/main.gen.tf"], 'resource "aws_ecs_service" "main" {')
    assert "    ignore_changes = [task_definition, desired_count]\n" in service
    assert "  deployment_circuit_breaker {\n    enable   = true\n    rollback = true\n" in service


# trace: PRD-IAC-009
def test_image_digest_is_a_root_module_variable_of_the_application(files: dict[str, str]) -> None:
    for environment in ENVIRONMENTS:
        variables = files[f"infra/envs/{environment}/variables.gen.tf"]
        block = _block(variables, 'variable "order_api_image_digest" {')
        assert "^sha256:[0-9a-f]{64}$" in block
        call = _arguments(files, environment)
        assert "  image_digest = var.order_api_image_digest\n" in call
        assert '  ecr_account_id = "111111111111"\n' in call
        assert '  ecr_repository = "order-service-tooling-order-api"\n' in call
    assert "@${var.image_digest}" in files[f"{MODULE}/main.gen.tf"]


# trace: PRD-IAC-010
def test_root_module_outputs_the_values_of_the_pipelines(files: dict[str, str]) -> None:
    outputs = files["infra/envs/staging/outputs.gen.tf"]
    for name, _ in modules.SERVICE_OUTPUTS:
        block = _block(outputs, f'output "api_service_{name}" {{')
        assert f"  value       = module.api_service.{name}\n" in block
        assert f'output "{name}" {{' in files[f"{MODULE}/outputs.gen.tf"]


# trace: PRD-IAC-018
def test_module_outputs_the_security_group_of_the_tasks(files: dict[str, str]) -> None:
    output = _block(files[f"{MODULE}/outputs.gen.tf"], 'output "security_group_id" {')
    assert "  value       = aws_security_group.service.id\n" in output


# trace: PRD-IAC-035, PRD-IAC-037
def test_each_resource_has_the_element_and_application_tags(files: dict[str, str]) -> None:
    main = files[f"{MODULE}/main.gen.tf"]
    assert '    "dsml:application" = var.application\n' in main
    assert '    "dsml:element"     = var.element\n' in main
    call = _arguments(files, "prod")
    assert '  element = "OrderService::apiService"\n' in call
    assert '  application = "OrderService::orderApi"\n' in call
    # Route 53 records, IAM role policies and some other resources do not accept tags.
    untagged = {
        "aws_acm_certificate_validation",
        "aws_appautoscaling_policy",
        "aws_iam_role_policy",
        "aws_route53_record",
    }
    for match in re.finditer(r'^resource "([a-z0-9_]+)" "([a-z0-9_]+)" \{', main, re.MULTILINE):
        block = _block(main, match.group(0))
        if match.group(1) not in untagged:
            assert "local.tags" in block, match.group(0)


# trace: PRD-IAC-008, PRD-IAC-015
def test_aws_names_have_the_form_of_the_names_module(files: dict[str, str]) -> None:
    dev = _arguments(files, "dev")
    assert '    execution_role = "order-service-dev-api-service-execution"\n' in dev
    assert '    task_role = "order-service-dev-api-service-task"\n' in dev
    staging = _arguments(files, "staging")
    alb = names.aws_name("order-service", "staging", "api-service", "alb")
    assert len(alb) == 32
    assert alb != "order-service-staging-api-service"
    assert f'    alb = "{alb}"\n' in staging
    assert f'    target_group = "{alb}"\n' in staging


# trace: PRD-TRACE-006, PRD-TRACE-007
def test_trace_manifest_gives_the_hcl_addresses_of_the_container_service() -> None:
    manifest = json.loads((GOLDEN / ".dsml" / "trace.gen.json").read_text(encoding="utf-8"))
    by_element = {item["element"]: item["files"] for item in manifest["elements"]}
    files = {
        item["path"]: [symbol["name"] for symbol in item["symbols"]]
        for item in by_element["OrderService::apiService"]
    }
    assert files["infra/envs/dev/main.gen.tf"] == ["module.api_service"]
    assert files["infra/envs/prod/variables.gen.tf"] == ["var.order_api_image_digest"]
    module = files[f"{MODULE}/main.gen.tf"]
    for address in (
        "aws_ecs_cluster.main",
        "aws_ecs_service.main",
        "aws_ecs_task_definition.migration",
        "aws_ecs_task_definition.service",
        "aws_lb.main",
        "aws_iam_role.execution",
        "aws_iam_role.task",
        "aws_appautoscaling_target.main",
        "aws_cloudwatch_log_group.main",
    ):
        assert address in module
    realization = {item["path"] for item in by_element["OrderService::apiServiceAws"]}
    assert f"{MODULE}/main.gen.tf" in realization


def test_model_with_no_container_service_gives_no_module(ir: Ir) -> None:
    gone = {
        "OrderService::apiService",
        "OrderService::apiServiceAws",
        "OrderService::prod::apiServiceProd",
    }
    changed = dataclasses.replace(
        ir,
        elements=tuple(element for element in ir.elements if element.identity not in gone),
        links=tuple(
            link for link in ir.links if link.source not in gone and link.target not in gone
        ),
    )
    files = _generate(changed)
    assert not any(path.startswith(MODULE) for path in files)
    assert "api_service" not in files["infra/envs/dev/main.gen.tf"]
    assert "image_digest" not in files["infra/envs/dev/variables.gen.tf"]


def test_container_service_needs_one_allocated_application(ir: Ir) -> None:
    no_allocation = dataclasses.replace(
        ir, links=tuple(link for link in ir.links if link.type != "allocate")
    )
    with pytest.raises(ToolchainError, match="must have one allocated application, not 0"):
        _generate(no_allocation)
    shop = make_ir([SHOP], ROOT)
    api = next(element for element in shop.elements if element.identity == "Shop::api")
    assert modules.service_application(shop, api).identity == "Shop::shopApi"
