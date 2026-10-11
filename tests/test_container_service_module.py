"""Tests of the local module `container-service` and of its module calls (story #80).

The golden files in `tests/golden/infrastructure/order-service/` hold the
full output. These tests examine the values that the requirements give.
"""

import dataclasses
import json
import re
from pathlib import Path, PurePosixPath

import pytest

from dsml.adapter.convert import make_ir
from dsml.config import Configuration
from dsml.errors import ToolchainError
from dsml.generate.infrastructure import names
from dsml.generate.infrastructure.container_service import container_services, network_address
from dsml.generate.infrastructure.generator import InfrastructureGenerator
from dsml.ir.model import Attribute, Element, IntegerValue, Ir
from dsml.versions import load_baseline

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
GOLDEN = ROOT / "tests" / "golden" / "infrastructure" / "order-service"
MODULE = "infra/modules/container-service"


@pytest.fixture(scope="module")
def ir() -> Ir:
    return make_ir([EXAMPLE], ROOT)


@pytest.fixture(scope="module")
def files(ir: Ir) -> dict[str, str]:
    output = InfrastructureGenerator().generate(
        ir, Configuration(infrastructure=PurePosixPath("infra")), None
    )
    return {file.path: file.content.decode("utf-8") for file in output}


def _block(text: str, start: str) -> str:
    """Give the top-level block that starts with the line `start`."""
    lines = text.split("\n")
    first = lines.index(start)
    last = lines.index("}", first)
    return "\n".join(lines[first : last + 1])


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
    for environment in ("dev", "prod", "staging"):
        call = _block(files[f"infra/envs/{environment}/main.gen.tf"], 'module "api_service" {')
        assert '  source = "../../modules/container-service"\n' in call


# trace: PRD-IAC-012
def test_task_definition_and_service_use_the_values_of_the_realization(
    files: dict[str, str],
) -> None:
    dev = _block(files["infra/envs/dev/main.gen.tf"], 'module "api_service" {')
    assert "  cpu               = 512\n" in dev
    assert "  memory            = 1024\n" in dev
    assert "  desired_count     = 1\n" in dev
    prod = _block(files["infra/envs/prod/main.gen.tf"], 'module "api_service" {')
    assert "  desired_count     = 3\n" in prod
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
    dev = _block(files["infra/envs/dev/main.gen.tf"], 'module "api_service" {')
    assert "  min_count         = 1\n  max_count         = 2\n" in dev
    prod = _block(files["infra/envs/prod/main.gen.tf"], 'module "api_service" {')
    assert "  min_count         = 3\n  max_count         = 6\n" in prod
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
        container_services(changed, "OrderService::dev")
    changed = _with_attributes(ir, "OrderService::apiServiceAws", minCount=1, maxCount=4)
    (dev,) = container_services(changed, "OrderService::dev")
    assert (dev.min_count, dev.desired_count, dev.max_count) == (1, 1, 4)
    (prod,) = container_services(changed, "OrderService::prod")
    assert (prod.min_count, prod.desired_count, prod.max_count) == (1, 3, 4)


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
    dev = _block(files["infra/envs/dev/main.gen.tf"], 'module "api_service" {')
    assert '  domain_name = "order-api.orders.dev.example.com"\n' in dev
    assert '  zone_name   = "orders.dev.example.com"\n' in dev


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
    # The task role has no policy: the elements of the example need no IAM access.
    task = _block(main, 'resource "aws_iam_role" "task" {')
    assert "aws_iam_policy_document.ecs_tasks_trust.json" in task
    assert "aws_iam_role.task.id" not in main
    assert "aws_iam_role.task.name" not in main


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
    dev = _block(files["infra/envs/dev/main.gen.tf"], 'module "api_service" {')
    assert '  migration_command = ["python", "-m", "app.migrate_gen"]\n' in dev


# trace: PRD-IAC-042
def test_service_ignores_its_task_definition_and_rolls_back_a_failed_deployment(
    files: dict[str, str],
) -> None:
    service = _block(files[f"{MODULE}/main.gen.tf"], 'resource "aws_ecs_service" "main" {')
    assert "    ignore_changes = [task_definition, desired_count]\n" in service
    assert "  deployment_circuit_breaker {\n    enable   = true\n    rollback = true\n" in service


# trace: PRD-IAC-009
def test_image_digest_is_a_root_module_variable_of_the_application(files: dict[str, str]) -> None:
    for environment in ("dev", "prod", "staging"):
        variables = files[f"infra/envs/{environment}/variables.gen.tf"]
        block = _block(variables, 'variable "order_api_image_digest" {')
        assert "^sha256:[0-9a-f]{64}$" in block
        call = _block(files[f"infra/envs/{environment}/main.gen.tf"], 'module "api_service" {')
        assert "  image_digest   = var.order_api_image_digest\n" in call
        assert '  ecr_account_id = "111111111111"\n' in call
        assert '  ecr_repository = "order-service-tooling-order-api"\n' in call
    assert "@${var.image_digest}" in files[f"{MODULE}/main.gen.tf"]


# trace: PRD-IAC-010
def test_root_module_outputs_the_values_of_the_pipelines(files: dict[str, str]) -> None:
    outputs = files["infra/envs/staging/outputs.gen.tf"]
    for name in (
        "api_url",
        "cluster_name",
        "migration_task_definition",
        "private_subnet_ids",
        "security_group_id",
        "service_name",
    ):
        block = _block(outputs, f'output "api_service_{name}" {{')
        assert f"  value       = module.api_service.{name}\n" in block
        assert f'output "{name}" {{' in files[f"{MODULE}/outputs.gen.tf"]


# trace: PRD-IAC-035, PRD-IAC-037
def test_each_resource_has_the_element_and_application_tags(files: dict[str, str]) -> None:
    main = files[f"{MODULE}/main.gen.tf"]
    assert '    "dsml:application" = var.application_tag\n' in main
    assert '    "dsml:element"     = var.element_tag\n' in main
    call = _block(files["infra/envs/prod/main.gen.tf"], 'module "api_service" {')
    assert '  element_tag     = "OrderService::apiService"\n' in call
    assert '  application_tag = "OrderService::orderApi"\n' in call
    # Route 53 records and IAM role policies do not accept tags.
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


# trace: PRD-IAC-008
def test_long_aws_names_get_a_hash(files: dict[str, str]) -> None:
    staging = _block(files["infra/envs/staging/main.gen.tf"], 'module "api_service" {')
    alb = names.aws_name("order-service", "staging", "api-service", "alb")
    assert len(alb) == 32
    assert alb != "order-service-staging-api-service"
    assert f'    alb                    = "{alb}"\n' in staging
    assert f'    target_group           = "{alb}"\n' in staging


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
    kept = tuple(element for element in ir.elements if element.kind != "ContainerService")
    output = InfrastructureGenerator().generate(
        dataclasses.replace(ir, elements=kept),
        Configuration(infrastructure=PurePosixPath("infra")),
        None,
    )
    assert not any(file.path.startswith("infra/modules/") for file in output)
    assert all(b"module " not in file.content for file in output)


def test_container_service_needs_one_network_and_one_application(ir: Ir) -> None:
    assert network_address(ir) == "network"
    no_network = dataclasses.replace(
        ir, elements=tuple(element for element in ir.elements if element.kind != "Network")
    )
    with pytest.raises(ToolchainError, match="exactly one network"):
        container_services(no_network, "OrderService::dev")
    no_allocation = dataclasses.replace(
        ir, links=tuple(link for link in ir.links if link.type != "allocate")
    )
    with pytest.raises(ToolchainError, match="exactly one allocated application"):
        container_services(no_allocation, "OrderService::dev")
