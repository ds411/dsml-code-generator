"""Tests of the configuration file `dsml.toml` (story #35)."""

import re
import shutil
from pathlib import Path, PurePosixPath

import pytest

from dsml.cli import main
from dsml.config import (
    Application,
    Configuration,
    ConfigurationError,
    IdPatterns,
    OpenTofuOptions,
    Rules,
    Trace,
    load_configuration,
    parse_configuration,
)

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "docs" / "configuration.md"
MODEL = ROOT / "tests" / "models" / "ir" / "needs-links.sysml"
FILE = Path("dsml.toml")

FULL = """\
schema = 1

[model]
paths = ["model", "extra/b.sysml", "model"]

[applications.orders]
output = "services/orders"
dependencies = ["httpx==0.28.1"]

[applications.admin]
output = "services/admin"

[infrastructure]
output = "infra"

[pipelines]
output = ".github/workflows"

[ids]
requirement = "REQ-[0-9]{4}"

[rules]
optional = ["TXT"]

[rules.severity]
"COV-003" = "error"
"TXT-001" = "off"

[trace]
baseline = "trace-baseline"
tests = ["tests"]

[aws]
regions = ["eu-west-1", "eu-central-1"]

[iac.opentofu]
state_encryption = true
"""


def _errors(text: str) -> list[str]:
    with pytest.raises(ConfigurationError) as error:
        parse_configuration(text, FILE)
    return error.value.errors


# trace: PRD-CORE-013
def test_full_file_gives_typed_sorted_data() -> None:
    assert parse_configuration(FULL, FILE) == Configuration(
        path=FILE,
        model=(PurePosixPath("extra/b.sysml"), PurePosixPath("model")),
        applications=(
            Application("admin", PurePosixPath("services/admin")),
            Application("orders", PurePosixPath("services/orders"), ("httpx==0.28.1",)),
        ),
        infrastructure=PurePosixPath("infra"),
        pipelines=PurePosixPath(".github/workflows"),
        ids=IdPatterns(requirement="REQ-[0-9]{4}"),
        rules=Rules(optional=("TXT",), severity=(("COV-003", "error"), ("TXT-001", "off"))),
        trace=Trace(baseline="trace-baseline", tests=(PurePosixPath("tests"),)),
        regions=("eu-central-1", "eu-west-1"),
        opentofu=OpenTofuOptions(state_encryption=True),
    )


# trace: PRD-CORE-013, PRD-DSML-050
def test_minimal_file_gives_the_defaults() -> None:
    configuration = parse_configuration("schema = 1\n", FILE)
    assert configuration == Configuration(path=FILE)
    assert configuration.ids == IdPatterns("N-[0-9]{3,}", "R-[0-9]{3,}", "V-[0-9]{3,}")
    assert configuration.opentofu is None
    assert configuration.application("orders") is None


# trace: PRD-DSML-051
def test_id_patterns_replace_the_defaults() -> None:
    text = 'schema = 1\n[ids]\nneed = "NEED-[0-9]+"\nverification = "T-[0-9]{2}"\n'
    ids = parse_configuration(text, FILE).ids
    assert ids == IdPatterns("NEED-[0-9]+", "R-[0-9]{3,}", "T-[0-9]{2}")
    assert re.fullmatch(ids.need, "NEED-7")


# trace: PRD-CORE-014
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "schema = 1\n\n[model]\npths = []\n",
            'dsml.toml:4: The key "model.pths" is unknown.',
        ),
        (
            "schema = 1\nmodels = []\n",
            'dsml.toml:2: The key "models" is unknown.',
        ),
        (
            'schema = 1\n[applications.orders]\noutput = "a"\nport = 80\n',
            'dsml.toml:4: The key "applications.orders.port" is unknown.',
        ),
        (
            "schema = 1\n[iac.terraform]\nx = 1\n",
            'dsml.toml:2: The key "iac.terraform" is unknown.',
        ),
        (
            "schema = 1\naws = { regions = [], account = 1 }\n",
            'dsml.toml:2: The key "aws.account" is unknown.',
        ),
        (
            'schema = 1\n[database]\npassword = "secret"\n',
            'dsml.toml:2: The key "database" is unknown.',
        ),
    ],
)
def test_unknown_key_is_an_error(text: str, expected: str) -> None:
    assert _errors(text) == [expected]


# trace: PRD-CORE-014
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("schema = 2\n", "dsml.toml:1: The schema version 2 is unknown."),
        ('schema = "1"\n', 'dsml.toml:1: The schema version "1" is unknown.'),
        ("schema = 1.0\n", "dsml.toml:1: The schema version 1.0 is unknown."),
        ("[model]\npaths = []\n", 'dsml.toml: The key "schema" is missing.'),
    ],
)
def test_unknown_schema_version_is_an_error(text: str, expected: str) -> None:
    errors = _errors(text)
    assert len(errors) == 1
    assert errors[0].startswith(expected)


# trace: PRD-CORE-014
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            'schema = 1\n[model]\npaths = "model"\n',
            'dsml.toml:3: The key "model.paths" must be a list of paths, not "model".',
        ),
        (
            "schema = 1\nmodel = 3\n",
            'dsml.toml:2: The key "model" must be a table, not 3.',
        ),
        (
            'schema = 1\n[infrastructure]\noutput = ""\n',
            'dsml.toml:3: The key "infrastructure.output" must be a text that is not empty, '
            'not "".',
        ),
        (
            'schema = 1\n[iac.opentofu]\nstate_encryption = "yes"\n',
            'dsml.toml:3: The key "iac.opentofu.state_encryption" must be true or false, '
            'not "yes".',
        ),
        (
            'schema = 1\n[aws]\nregions = [\n  "eu-west-1",\n  1,\n]\n',
            'dsml.toml:3: The key "aws.regions" must be a text that is not empty, not 1.',
        ),
    ],
)
def test_wrong_type_is_an_error(text: str, expected: str) -> None:
    assert _errors(text) == [expected]


# trace: PRD-CORE-013, PRD-CORE-033
@pytest.mark.parametrize("path", ["/abs/model", "../model", "model/../x", "C:/model", "model\\\\x"])
def test_path_must_be_relative_in_the_folder(path: str) -> None:
    errors = _errors(f'schema = 1\n[model]\npaths = ["{path}"]\n')
    assert len(errors) == 1
    assert errors[0].startswith("dsml.toml:3: The path ")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            'schema = 1\n[ids]\nneed = "N-[0-9"\n',
            "dsml.toml:3: The regular expression is not correct: ",
        ),
        (
            'schema = 1\n[rules]\noptional = ["TXT", "FOO"]\n',
            'dsml.toml:3: The rule set "FOO" is unknown.',
        ),
        (
            'schema = 1\n[rules.severity]\n"COV-3" = "error"\n',
            'dsml.toml:3: The rule ID "COV-3" is not correct.',
        ),
        (
            'schema = 1\n[rules.severity]\nCOV-003 = "high"\n',
            'dsml.toml:3: The severity "high" is unknown.',
        ),
        (
            'schema = 1\n[applications."my app"]\noutput = "a"\n',
            'dsml.toml:2: The application name "my app" is not correct.',
        ),
    ],
)
def test_wrong_value_is_an_error(text: str, expected: str) -> None:
    errors = _errors(text)
    assert len(errors) == 1
    assert errors[0].startswith(expected)


def test_all_errors_are_reported_in_line_order() -> None:
    text = 'schema = 1\n[trace]\ntests = "t"\nbase = "x"\n[model]\nfoo = 1\n'
    assert _errors(text) == [
        'dsml.toml:3: The key "trace.tests" must be a list of paths, not "t".',
        'dsml.toml:4: The key "trace.base" is unknown.',
        'dsml.toml:6: The key "model.foo" is unknown.',
    ]


def test_line_numbers_ignore_text_in_strings_and_comments() -> None:
    text = (
        "# [model]\n"
        "schema = 1\n"
        "[trace]\n"
        'baseline = """\n'
        "x = 1\n"
        '[model]"""\n'
        "tests = ['a#b', \"c]\"]  # comment\n"
        '["model"]\n'
        "unknown = 1\n"
    )
    assert _errors(text) == ['dsml.toml:9: The key "model.unknown" is unknown.']


def test_toml_syntax_error_gives_the_line() -> None:
    assert _errors("schema = 1\n[model\n") == [
        "dsml.toml:2: The file is not correct TOML: Expected ']' at the end of a table declaration."
    ]


def test_missing_or_bad_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="does not exist"):
        load_configuration(tmp_path / "none.toml")
    bad = tmp_path / "bad.toml"
    bad.write_bytes(b"schema = 1\n# \xff\n")
    with pytest.raises(ConfigurationError, match="does not have UTF-8 encoding"):
        load_configuration(bad)


# trace: PRD-CORE-012
def test_paths_are_relative_to_the_folder_of_the_file(tmp_path: Path) -> None:
    path = tmp_path / "conf" / "other.toml"
    path.parent.mkdir()
    path.write_text('schema = 1\n[model]\npaths = ["m"]\n', encoding="utf-8")
    configuration = load_configuration(path)
    assert configuration.root == path.parent
    assert configuration.model == (PurePosixPath("m"),)


# trace: PRD-CORE-013
def test_example_in_the_key_reference_is_correct() -> None:
    text = REFERENCE.read_text(encoding="utf-8")
    examples = re.findall(r"```toml\n(.*?)```", text, re.DOTALL)
    assert examples
    for example in examples:
        parse_configuration(example, FILE)


# trace: PRD-CORE-013
def test_key_reference_gives_each_key() -> None:
    text = REFERENCE.read_text(encoding="utf-8")
    keys = [
        "schema",
        "model.paths",
        "applications.<name>.output",
        "applications.<name>.dependencies",
        "infrastructure.output",
        "pipelines.output",
        "ids.need",
        "ids.requirement",
        "ids.verification",
        "rules.optional",
        "rules.severity.<rule>",
        "trace.baseline",
        "trace.tests",
        "aws.regions",
        "iac.opentofu.state_encryption",
    ]
    for key in keys:
        assert f"`{key}`" in text, key


# The command line.


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make a folder with one model file in `model/` and go to it."""
    (tmp_path / "model").mkdir()
    shutil.copy(MODEL, tmp_path / "model" / "needs.sysml")
    monkeypatch.chdir(tmp_path)
    return tmp_path


# trace: PRD-CORE-002, PRD-CORE-014
@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("schema = 1\nmodels = []\n", 'dsml: error: dsml.toml:2: The key "models" is unknown.\n'),
        ("schema = 7\n", "dsml: error: dsml.toml:1: The schema version 7 is unknown. "),
    ],
)
def test_bad_configuration_gives_exit_code_2(
    text: str, message: str, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / "dsml.toml").write_text(text, encoding="utf-8")
    assert main(["ir", "model/needs.sysml"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(message)


def test_each_error_is_one_line_of_the_message(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / "dsml.toml").write_text("schema = 1\na = 1\nb = 2\n", encoding="utf-8")
    assert main(["ir"]) == 2
    assert capsys.readouterr().err == (
        'dsml: error: dsml.toml:2: The key "a" is unknown.\n'
        'dsml: error: dsml.toml:3: The key "b" is unknown.\n'
    )


# trace: PRD-CORE-012
def test_config_option_gives_a_missing_file_exit_code_2(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["ir", "--config", "other.toml", "model/needs.sysml"]) == 2
    assert capsys.readouterr().err == (
        "dsml: error: The configuration file other.toml does not exist.\n"
    )


# trace: PRD-CORE-012, PRD-DSML-007
def test_config_option_reads_a_file_at_a_different_path(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / "dsml.toml").write_text("schema = 1\nbad = 1\n", encoding="utf-8")
    (project / "other.toml").write_text('schema = 1\n[model]\npaths = ["model"]\n', "utf-8")
    assert main(["ir", "--config", "other.toml", "--output", "from-config.json"]) == 0
    assert main(["ir", "--config", "other.toml", "model/needs.sysml", "--output", "cli.json"]) == 0
    from_config = (project / "from-config.json").read_bytes()
    assert from_config == (project / "cli.json").read_bytes()
    assert b'"model/needs.sysml"' in from_config


def test_ir_with_no_model_file_is_an_error(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["ir"]) == 2
    assert capsys.readouterr().err.startswith("dsml: error: Give one or more model files")
    (project / "dsml.toml").write_text('schema = 1\n[model]\npaths = ["none"]\n', "utf-8")
    assert main(["ir"]) == 2
    assert capsys.readouterr().err == (
        'dsml: error: The model path "none" of the configuration file does not exist.\n'
    )
