"""Tests of the trace manifest `.dsml/trace.gen.json` (story #70).

The golden file `tests/golden/trace/order-service.trace.gen.json` is the
trace manifest that `dsml generate` writes for the example model with the
test generator of `tests/dsml_test_command.py`.
"""

import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dsml.errors import ToolchainError
from dsml.generate.trace import (
    TRACE_PATH,
    Symbol,
    SymbolKind,
    TraceEntry,
    read_trace,
    trace_bytes,
    trace_entries,
)
from dsml.generate.writer import (
    INFRASTRUCTURE,
    Kind,
    OutputFile,
    apply_plan,
    check_files,
    make_plan,
)

ROOT = Path(__file__).resolve().parent.parent
COMMAND = ROOT / "tests" / "dsml_test_command.py"
EXAMPLE_MODEL = ROOT / "docs" / "model" / "examples" / "order-service.sysml"
GOLDEN = ROOT / "tests" / "golden" / "trace" / "order-service.trace.gen.json"
APP = "application/orderApi"


def function(name: str, first: int, last: int, *elements: str) -> Symbol:
    return Symbol(SymbolKind.FUNCTION, name, first, last, elements)


def generated(path: str, lines: int = 3, part: str = APP, *symbols: Symbol) -> OutputFile:
    content = "".join(f"x{number} = 1\n" for number in range(lines)).encode()
    return OutputFile(path, content, Kind.GENERATED, part, symbols)


def run(root: Path, files: list[OutputFile], parts: set[str] | None = None) -> list[str]:
    """Run the writer like `dsml generate`. Give the changes."""
    check_files(files)
    plan = make_plan(root, files, parts)
    apply_plan(root, plan)
    return [str(change) for change in plan.changes]


# trace: PRD-TRACE-006, PRD-TRACE-007, PRD-CORE-028
def test_generate_writes_the_golden_trace_manifest(tmp_path: Path) -> None:
    (tmp_path / "model").mkdir()
    shutil.copy(EXAMPLE_MODEL, tmp_path / "model" / "order-service.sysml")
    (tmp_path / "dsml.toml").write_text('schema = 1\n\n[model]\npaths = ["model"]\n')
    result = subprocess.run(
        [sys.executable, str(COMMAND), "generate"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert (tmp_path / TRACE_PATH).read_bytes() == GOLDEN.read_bytes(), (
        "The trace manifest is different from the golden file. If the change is correct, "
        f"write the new trace manifest to {GOLDEN.relative_to(ROOT).as_posix()}."
    )


# trace: PRD-TRACE-007
def test_golden_trace_manifest_gives_the_resource_addresses_of_infrastructure_elements() -> None:
    data = json.loads(GOLDEN.read_bytes())
    addresses = {
        item["element"]: [
            symbol["name"]
            for file in item["files"]
            for symbol in file["symbols"]
            if symbol["kind"] == "resource"
        ]
        for item in data["elements"]
    }
    assert addresses["OrderService::apiServiceAws"] == ["aws_ecs_service.api_service_aws"]
    assert addresses["OrderService::apiService"] == ["aws_ecs_service.api_service_aws"]
    assert addresses["OrderService::usersAws"] == ["aws_cognito_user_pool.users_aws"]


# trace: PRD-TRACE-008
def test_trace_manifest_is_sorted_by_element_then_path_then_line() -> None:
    entries = [
        TraceEntry("R-001", "b_gen.py", SymbolKind.FUNCTION, "late", 9, 12),
        TraceEntry("R-001", "b_gen.py", SymbolKind.CLASS, "early", 2, 20),
        TraceEntry("R-001", "a_gen.py", SymbolKind.FUNCTION, "f", 30, 31),
        TraceEntry("N-001", "z.gen.tf", SymbolKind.RESOURCE, "aws_vpc.main", 4, 8),
        TraceEntry("Shop::order", "a_gen.py", SymbolKind.ROUTE, "GET /orders", 1, 1),
        TraceEntry("Shop::Order", "a_gen.py", SymbolKind.CLASS, "Order", 5, 6),
    ]
    expected = trace_bytes(entries)
    shuffled = list(entries)
    random.Random(7).shuffle(shuffled)
    assert trace_bytes(shuffled) == expected
    assert trace_bytes(reversed(entries)) == expected

    data = json.loads(expected)
    order = [
        (item["element"], file["path"], symbol["firstLine"])
        for item in data["elements"]
        for file in item["files"]
        for symbol in file["symbols"]
    ]
    assert order == [
        ("N-001", "z.gen.tf", 4),
        ("R-001", "a_gen.py", 30),
        ("R-001", "b_gen.py", 2),
        ("R-001", "b_gen.py", 9),
        ("Shop::Order", "a_gen.py", 5),
        ("Shop::order", "a_gen.py", 1),
    ]
    assert expected == (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()


# trace: PRD-TRACE-006
def test_symbol_with_two_elements_is_in_the_manifest_of_each_element() -> None:
    entries = trace_entries("a_gen.py", [function("f", 1, 2, "R-002", "R-001", "R-001")])
    assert [entry.element for entry in entries] == ["R-001", "R-002"]
    data = json.loads(trace_bytes([*entries, *entries]))
    assert [item["element"] for item in data["elements"]] == ["R-001", "R-002"]
    assert data["elements"][0]["files"] == [
        {
            "path": "a_gen.py",
            "symbols": [{"firstLine": 1, "kind": "function", "lastLine": 2, "name": "f"}],
        }
    ]


def test_run_with_no_symbols_writes_an_empty_trace_manifest(tmp_path: Path) -> None:
    assert run(tmp_path, [generated("a_gen.py")]) == [
        "add .dsml/generated.json",
        "add .dsml/trace.gen.json",
        "add a_gen.py",
    ]
    assert (tmp_path / TRACE_PATH).read_bytes() == b'{\n  "elements": [],\n  "traceVersion": 1\n}\n'


# trace: PRD-TRACE-006
def test_create_once_files_do_not_go_into_the_trace_manifest(tmp_path: Path) -> None:
    files = [
        generated("a_gen.py", 3, APP, function("f", 1, 2, "R-001")),
        OutputFile("handler.py", b"x = 1\n", Kind.CREATE_ONCE, APP),
    ]
    run(tmp_path, files)
    assert read_trace(tmp_path) == [TraceEntry("R-001", "a_gen.py", SymbolKind.FUNCTION, "f", 1, 2)]


# trace: PRD-TRACE-006, PRD-CORE-004
def test_new_symbols_change_only_the_trace_manifest(tmp_path: Path) -> None:
    run(tmp_path, [generated("a_gen.py", 3, APP, function("f", 1, 2, "R-001"))])
    changes = run(tmp_path, [generated("a_gen.py", 3, APP, function("f", 1, 3, "R-001"))])
    assert changes == ["change .dsml/trace.gen.json"]
    assert run(tmp_path, [generated("a_gen.py", 3, APP, function("f", 1, 3, "R-001"))]) == []


# trace: PRD-TRACE-006, PRD-CORE-005
def test_run_of_one_part_keeps_the_trace_entries_of_the_other_parts(tmp_path: Path) -> None:
    app = generated("app/api_gen.py", 3, APP, function("f", 1, 2, "R-001"))
    infra = generated(
        "infra/main.gen.tf",
        5,
        INFRASTRUCTURE,
        Symbol(SymbolKind.RESOURCE, "aws_vpc.main", 1, 5, ("Shop::networkAws",)),
    )
    run(tmp_path, [app, infra])
    changes = run(
        tmp_path,
        [generated("infra/main.gen.tf", 5, INFRASTRUCTURE)],
        {INFRASTRUCTURE},
    )
    assert changes == ["change .dsml/trace.gen.json"]
    assert read_trace(tmp_path) == [
        TraceEntry("R-001", "app/api_gen.py", SymbolKind.FUNCTION, "f", 1, 2)
    ]


@pytest.mark.parametrize(
    ("file", "message"),
    [
        (
            OutputFile("a.py", b"x\n", Kind.CREATE_ONCE, APP, (function("f", 1, 1, "R-001"),)),
            'The create-once file "a.py" must not have symbols',
        ),
        (generated("a_gen.py", 3, APP, function("f", 0, 1, "R-001")), "the lines 0 to 1"),
        (generated("a_gen.py", 3, APP, function("f", 2, 4, "R-001")), "range 1 to 3"),
        (generated("a_gen.py", 3, APP, function("f", 3, 2, "R-001")), "the lines 3 to 2"),
        (generated("a_gen.py", 3, APP, function("f", 1, 2)), 'The symbol "f" .* has no element'),
        (generated("a_gen.py", 3, APP, function("f", 1, 2, " R-001")), "the element identity"),
        (generated("a_gen.py", 3, APP, function("", 1, 2, "R-001")), "a symbol with the name ''"),
    ],
)
def test_symbol_that_is_not_correct_is_an_error(file: OutputFile, message: str) -> None:
    with pytest.raises(ToolchainError, match=message):
        check_files([file])


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[", "is not correct JSON"),
        ("[]", "The top level must be a JSON object"),
        ('{"elements": [], "traceVersion": 2}', "version 2 is unknown"),
        ('{"elements": {}, "traceVersion": 1}', 'The key "elements" must be a list'),
        ('{"elements": [{"element": "R-001"}], "traceVersion": 1}', 'Each item of "elements"'),
        (
            '{"elements": [{"element": "R-001", "files": [{"path": "a_gen.py", "symbols": '
            '[{"firstLine": 1, "kind": "macro", "lastLine": 1, "name": "m"}]}]}], '
            '"traceVersion": 1}',
            'The symbol kind "macro" is unknown',
        ),
        (
            '{"elements": [{"element": "R-001", "files": [{"path": "a_gen.py", "symbols": '
            '[{"firstLine": 0, "kind": "class", "lastLine": 1, "name": "m"}]}]}], '
            '"traceVersion": 1}',
            'The key "firstLine" must be a line number',
        ),
    ],
)
def test_trace_manifest_that_is_not_correct_is_an_error(
    tmp_path: Path, text: str, message: str
) -> None:
    (tmp_path / ".dsml").mkdir()
    (tmp_path / TRACE_PATH).write_text(text, encoding="utf-8")
    with pytest.raises(ToolchainError, match=message):
        read_trace(tmp_path)


def test_trace_manifest_is_read_back_with_the_same_entries(tmp_path: Path) -> None:
    entries = [
        TraceEntry("R-001", "a_gen.py", SymbolKind.ROUTE, "POST /orders", 4, 9),
        TraceEntry("R-001", "a_gen.py", SymbolKind.CLASS, "Order", 1, 3),
    ]
    (tmp_path / ".dsml").mkdir()
    (tmp_path / TRACE_PATH).write_bytes(trace_bytes(entries))
    assert sorted(read_trace(tmp_path), key=lambda entry: entry.first_line) == [
        entries[1],
        entries[0],
    ]


def test_missing_trace_manifest_is_empty(tmp_path: Path) -> None:
    assert read_trace(tmp_path) == []
