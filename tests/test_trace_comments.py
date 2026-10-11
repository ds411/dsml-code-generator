"""Tests of the trace comments in hand-written files (story #71)."""

import os
from pathlib import Path

import pytest

from dsml.config import Configuration, parse_configuration
from dsml.generate.manifest import MANIFEST_PATH, CreateOnceEntry, GeneratedEntry, Manifest
from dsml.trace.comments import (
    Language,
    TraceComment,
    TraceComments,
    TraceProblem,
    parse_trace_comments,
    read_trace_comments,
    trace_folders,
)

CONFIGURATION = """\
schema = 1

[applications.orders]
output = "services/orders"

[infrastructure]
output = "infra"

[pipelines]
output = ".github/workflows"

[trace]
tests = ["tests", "services/orders/tests"]
"""


def comment(
    line: int, *ids: str, symbol: str | None = None, symbol_line: int | None = None
) -> TraceComment:
    return TraceComment("f", line, ids, symbol, symbol_line)


def parse(text: str, language: Language) -> list[TraceComment]:
    comments, problems = parse_trace_comments("f", text, language)
    assert problems == []
    return comments


def configure(root: Path) -> Configuration:
    path = root / "dsml.toml"
    path.write_text(CONFIGURATION)
    return parse_configuration(CONFIGURATION, path)


def write(root: Path, path: str, text: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


# Python.


def test_python_comment_applies_to_the_next_def_or_class() -> None:
    text = """\
# trace: R-001
def get_order() -> None:
    pass


# trace: R-002, OrderService::orderDataSafe
@dataclass
class OrderStore:
    # trace: 'R-003'
    async def get(self) -> None:
        def inner() -> None: ...


def after() -> None: ...
"""
    assert parse(text, Language.PYTHON) == [
        comment(1, "R-001", symbol="get_order", symbol_line=2),
        comment(6, "R-002", "OrderService::orderDataSafe", symbol="OrderStore", symbol_line=8),
        comment(9, "'R-003'", symbol="OrderStore.get", symbol_line=10),
    ]


def test_python_comment_with_no_symbol_after_it_applies_to_the_file() -> None:
    text = 'def first() -> None: ...\n\n\n# trace: R-001\nVALUE = "def x():"\n'
    assert parse(text, Language.PYTHON) == [comment(4, "R-001")]


def test_python_reader_ignores_strings_and_comments_after_code() -> None:
    text = '''\
TEXT = """
# trace: R-001
def not_a_symbol(): ...
"""
VALUE = 1  # trace: R-002
#trace:R-003
def real() -> None: ...
'''
    assert parse(text, Language.PYTHON) == [comment(6, "R-003", symbol="real", symbol_line=7)]


def test_python_reader_reads_a_file_with_a_syntax_error() -> None:
    text = "# trace: R-001\ndef broken(:\n    (\n"
    assert parse(text, Language.PYTHON) == [comment(1, "R-001", symbol="broken", symbol_line=2)]


def test_python_reader_ignores_other_comments() -> None:
    assert parse("# traceability\n# Trace: R-001\n# trace R-001\n", Language.PYTHON) == []


# HCL.


def test_hcl_comment_applies_to_the_next_top_level_block() -> None:
    text = """\
# trace: R-001
resource "aws_s3_bucket" "logs" {
  # trace: R-002
  bucket = "logs-${var.name}-{x}"
  tags = {
    Name = "logs"
  }
}

# trace: OrderService::network
module "network" {
  source = "./network"
}

# trace: R-003
data "aws_iam_policy_document" "read" {}
# trace: R-004
variable "region" {
  default = "eu-west-1"
}
# trace: R-005
output "url" { value = 1 }
# trace: R-006
locals {
  policy = <<-EOT
    # trace: R-999
    resource "x" "y" {
  EOT
}
# trace: R-007
"""
    assert parse(text, Language.HCL) == [
        comment(1, "R-001", symbol="aws_s3_bucket.logs", symbol_line=2),
        comment(3, "R-002", symbol="module.network", symbol_line=11),
        comment(10, "OrderService::network", symbol="module.network", symbol_line=11),
        comment(15, "R-003", symbol="data.aws_iam_policy_document.read", symbol_line=16),
        comment(17, "R-004", symbol="var.region", symbol_line=18),
        comment(21, "R-005", symbol="output.url", symbol_line=22),
        comment(23, "R-006", symbol="locals", symbol_line=24),
        comment(30, "R-007"),
    ]


def test_hcl_reader_ignores_block_comments() -> None:
    text = '/*\n# trace: R-999\n*/\n# trace: R-001\nprovider "aws" {}\n'
    assert parse(text, Language.HCL) == [comment(4, "R-001", symbol="provider.aws", symbol_line=5)]


# YAML.


def test_yaml_comment_applies_to_the_file() -> None:
    text = """\
# trace: R-001
name: Deploy
jobs:
  deploy:
    # trace: OrderService::deploy, V-001
    steps:
      - run: |
          # trace: R-999
          echo "deploy"
      - run: >-
          # trace: R-998
      # trace: R-002
      - uses: actions/checkout@v6
"""
    assert parse(text, Language.YAML) == [
        comment(1, "R-001"),
        comment(5, "OrderService::deploy", "V-001"),
        comment(12, "R-002"),
    ]


# TypeScript.


def test_typescript_comment_applies_to_the_next_symbol() -> None:
    text = """\
// trace: R-001
export async function getOrder(): Promise<void> {}

// trace: R-002
export default class OrderStore {}

// trace: 'R-003'
export const ORDER_LIMIT = 10;

// trace: R-004
const local = `
// trace: R-999
function notASymbol() {}
`;
/* // trace: R-998
function notASymbol2() {} */
function helper(): void {}

// trace: R-005
export default function () {}
// trace: R-006
"""
    assert parse(text, Language.TYPESCRIPT) == [
        comment(1, "R-001", symbol="getOrder", symbol_line=2),
        comment(4, "R-002", symbol="OrderStore", symbol_line=5),
        comment(7, "'R-003'", symbol="ORDER_LIMIT", symbol_line=8),
        comment(10, "R-004", symbol="helper", symbol_line=17),
        comment(19, "R-005", symbol="default", symbol_line=20),
        comment(21, "R-006"),
    ]


def test_typescript_reader_ignores_hash_comments() -> None:
    assert parse("# trace: R-001\n", Language.TYPESCRIPT) == []


# Problems.


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("# trace:\n", "The trace comment has no ID."),
        ("# trace: R-001,\n", 'not a short name or a qualified name: "".'),
        ("# trace: R 001, R-002\n", 'not a short name or a qualified name: "R 001".'),
        ("# trace: Pkg::\n", 'not a short name or a qualified name: "Pkg::".'),
    ],
)
def test_malformed_comment_is_a_problem(text: str, message: str) -> None:
    comments, problems = parse_trace_comments("f", text, Language.PYTHON)
    assert comments == []
    assert len(problems) == 1
    assert problems[0].line == 1
    assert problems[0].message.endswith(message)


def test_crlf_line_ends_give_the_same_result() -> None:
    text = "# trace: R-001\ndef run() -> None: ...\n"
    assert parse(text.replace("\n", "\r\n"), Language.PYTHON) == parse(text, Language.PYTHON)


# The folders and the manifest.


def test_trace_folders_are_the_output_and_test_folders(tmp_path: Path) -> None:
    folders = [folder.as_posix() for folder in trace_folders(configure(tmp_path))]
    assert folders == [
        ".github/workflows",
        "infra",
        "services/orders",
        "services/orders/tests",
        "tests",
    ]


def test_reader_reads_hand_written_files_and_skips_generated_files(tmp_path: Path) -> None:
    configuration = configure(tmp_path)
    write(tmp_path, "services/orders/app/routes_gen.py", "# trace: R-900\ndef route(): ...\n")
    write(tmp_path, "services/orders/app/handlers.py", "# trace: R-001\ndef handle(): ...\n")
    write(tmp_path, "services/orders/tests/test_handlers.py", "# trace: V-001\ndef test(): ...\n")
    write(tmp_path, "services/orders/node_modules/x.ts", "// trace: R-901\n")
    write(tmp_path, "services/orders/notes.md", "# trace: R-902\n")
    write(tmp_path, "infra/main.tf", '# trace: R-002\nresource "a" "b" {}\n')
    write(tmp_path, ".github/workflows/deploy.gen.yml", "# trace: R-903\n")
    write(tmp_path, ".github/workflows/extra.yml", "# trace: R-003\n")
    write(tmp_path, "tests/e2e.ts", "// trace: V-002\nexport function e2e() {}\n")
    write(tmp_path, "other/main.py", "# trace: R-904\n")
    manifest = Manifest(
        generated=(
            GeneratedEntry("services/orders/app/routes_gen.py", "orders", "0" * 64),
            GeneratedEntry(".github/workflows/deploy.gen.yml", "pipelines", "0" * 64),
        ),
        create_once=(CreateOnceEntry("services/orders/app/handlers.py", "orders"),),
    )
    write(tmp_path, MANIFEST_PATH, manifest.to_bytes().decode())

    assert read_trace_comments(configuration) == TraceComments(
        comments=(
            TraceComment(".github/workflows/extra.yml", 1, ("R-003",), None, None),
            TraceComment("infra/main.tf", 1, ("R-002",), "a.b", 2),
            TraceComment("services/orders/app/handlers.py", 1, ("R-001",), "handle", 2),
            TraceComment("services/orders/tests/test_handlers.py", 1, ("V-001",), "test", 2),
            TraceComment("tests/e2e.ts", 1, ("V-002",), "e2e", 2),
        )
    )


def test_reader_reports_a_file_that_is_not_utf_8(tmp_path: Path) -> None:
    configuration = configure(tmp_path)
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "main.tf").write_bytes(b"# trace: R-001 \xff\n")
    assert read_trace_comments(configuration) == TraceComments(
        problems=(TraceProblem("infra/main.tf", None, "The file does not have UTF-8 encoding."),)
    )


def test_reader_with_no_folders_on_disk_gives_no_comments(tmp_path: Path) -> None:
    assert read_trace_comments(configure(tmp_path)) == TraceComments()


@pytest.mark.skipif(os.name == "nt", reason="Symbolic links need extra rights on Windows.")
def test_reader_does_not_follow_symbolic_links(tmp_path: Path) -> None:
    configuration = configure(tmp_path)
    write(tmp_path, "other/main.py", "# trace: R-001\n")
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "link.py").symlink_to(tmp_path / "other" / "main.py")
    (tmp_path / "infra" / "folder").symlink_to(tmp_path / "other")
    assert read_trace_comments(configuration) == TraceComments()


def test_order_of_the_files_on_disk_does_not_change_the_result(tmp_path: Path) -> None:
    files = {f"tests/test_{name}.py": f"# trace: R-00{index}\n" for index, name in enumerate("cab")}
    first, second = tmp_path / "first", tmp_path / "second"
    for root, order in ((first, sorted(files)), (second, sorted(files, reverse=True))):
        root.mkdir()
        for path in order:
            write(root, path, files[path])
    assert read_trace_comments(configure(first)) == read_trace_comments(configure(second))
    assert [item.path for item in read_trace_comments(configure(first)).comments] == [
        "tests/test_a.py",
        "tests/test_b.py",
        "tests/test_c.py",
    ]
