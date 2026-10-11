"""Tests of the baseline module and the IDN rules (story #66).

Each test makes a temporary Git repository. The tests use only the local
`git` command and no network (PRD-TOP-004).
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Protocol

import pytest
from conftest import RULE_MODELS

from dsml.adapter.convert import build_ir
from dsml.adapter.engine import Engine
from dsml.baseline import checkout, newest_release_tag, read_baseline, resolve
from dsml.cli import main
from dsml.config import Configuration, load_configuration
from dsml.errors import ToolchainError
from dsml.ir.model import Finding, Ir, Location
from dsml.library import library_document
from dsml.validate.engine import Validator
from dsml.validate.rules import registry

IDN_RULES = ("IDN-001", "IDN-002", "IDN-003")
CONFIG = 'schema = 1\n\n[model]\npaths = ["model"]\n'
MODEL = "model/model.sysml"


class Repository:
    """A temporary Git repository with a configuration file and one model file."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir()
        self.git("init", "--quiet", "--initial-branch=main")
        (root / "dsml.toml").write_text(CONFIG, encoding="utf-8")
        (root / "model").mkdir()

    def git(self, *args: str) -> str:
        """Run a Git command with no user or system configuration."""
        env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
        result = subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            check=True,
            env=env,
            text=True,
        )
        return result.stdout.strip()

    def model(self, source: Path) -> None:
        """Copy a model into the model file of the work tree."""
        shutil.copyfile(source, self.root / MODEL)

    def commit(self, message: str, tag: str | None = None) -> str:
        """Commit all files of the work tree. Then put a tag on the commit if `tag` gives one."""
        self.git("add", "--all")
        self.git("commit", "--quiet", "--allow-empty", "--no-gpg-sign", "-m", message)
        if tag is not None:
            self.git("tag", tag)
        return self.git("rev-parse", "HEAD")

    @property
    def configuration(self) -> Configuration:
        return load_configuration(self.root / "dsml.toml")


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    return Repository(tmp_path / "repository")


def _ir(engine: Engine, root: Path, files: tuple[Path, ...]) -> Ir:
    documents = [
        (file.relative_to(root).as_posix(), file.read_text(encoding="utf-8")) for file in files
    ]
    return build_ir(engine.parse_texts([library_document(), *documents]), [n for n, _ in documents])


class RunIdn(Protocol):
    """Run one IDN rule on a model of `tests/models/rules/<rule>/`.

    The baseline is the model `baseline.sysml` of the rule in a commit with
    the tag `v1.0.0`. With `baseline=False`, the validator gets no baseline.
    """

    def __call__(self, rule: str, model: str, baseline: bool = True) -> tuple[Finding, ...]: ...


@pytest.fixture
def run_idn(rule_engine: Engine, repository: Repository) -> RunIdn:
    """Give the helper that runs one IDN rule with a baseline from Git."""

    def run(rule: str, model: str, baseline: bool = True) -> tuple[Finding, ...]:
        repository.model(RULE_MODELS / rule / "baseline.sysml")
        repository.commit("Add the baseline model.", tag="v1.0.0")
        repository.model(RULE_MODELS / rule / model if "/" not in model else Path(model))
        ir = _ir(rule_engine, repository.root, (repository.root / MODEL,))
        before = None
        if baseline:
            with checkout("v1.0.0", repository.configuration, repository.root) as copy:
                before = _ir(rule_engine, copy.root, copy.files)
        return Validator(Configuration(), {rule: registry()[rule]}).run(ir, before)

    return run


def _location(line: int, column: int) -> Location:
    return Location(MODEL, line, column)


# trace: PRD-VAL-015
def test_registry_contains_the_idn_rules_with_their_severities() -> None:
    rules = registry()
    severities = {rule_id: rules[rule_id].rule.severity for rule_id in IDN_RULES}
    assert severities == {"IDN-001": "error", "IDN-002": "info", "IDN-003": "warning"}


# trace: PRD-VAL-008
@pytest.mark.parametrize("rule", IDN_RULES)
def test_idn_rule_accepts_its_accept_model(rule: str, run_idn: RunIdn) -> None:
    assert run_idn(rule, "accept.sysml") == ()


# trace: PRD-VAL-008, PRD-VAL-011
@pytest.mark.parametrize("rule", IDN_RULES)
def test_idn_rules_do_not_run_with_no_baseline(rule: str, run_idn: RunIdn) -> None:
    assert run_idn(rule, "reject.sysml", baseline=False) == ()


REJECTED = {
    "IDN-001": (
        Finding(
            "IDN-001",
            "error",
            'The short name "R-001" is the short name of a Need. '
            "In the baseline, it was the short name of a Requirement.",
            _location(11, 5),
            "R-001",
        ),
    ),
    "IDN-002": (
        Finding(
            "IDN-002",
            "info",
            'The qualified name of "R-001" is "IdnQualifiedNames::getStatus". '
            'In the baseline, it was "IdnQualifiedNames::getOrderStatus".',
            _location(10, 5),
            "R-001",
        ),
    ),
    "IDN-003": (
        Finding(
            "IDN-003",
            "warning",
            'The qualified name of the Entity "IdnNoShortNames::Purchase" was '
            '"IdnNoShortNames::Order" in the baseline. Its identity changes.',
            _location(8, 5),
            "IdnNoShortNames::Purchase",
        ),
        Finding(
            "IDN-003",
            "warning",
            'The qualified name of the Field "IdnNoShortNames::Purchase::id" was '
            '"IdnNoShortNames::Order::id" in the baseline. Its identity changes.',
            _location(9, 9),
            "IdnNoShortNames::Purchase::id",
        ),
    ),
}


# trace: PRD-VAL-008, PRD-VAL-011
@pytest.mark.parametrize("rule", IDN_RULES)
def test_idn_rule_rejects_its_reject_model(rule: str, run_idn: RunIdn) -> None:
    assert run_idn(rule, "reject.sysml") == REJECTED[rule]


# trace: PRD-DSML-053
def test_idn_003_makes_no_pair_when_two_elements_agree(run_idn: RunIdn, tmp_path: Path) -> None:
    model = tmp_path / "two.sysml"
    text = (RULE_MODELS / "IDN-003" / "reject.sysml").read_text(encoding="utf-8")
    model.write_text(
        text.replace(
            "    #Entity part def Purchase {",
            "    #Entity part def Sale {\n        #Key attribute id : String [1];\n    }\n\n"
            "    #Entity part def Purchase {",
        ),
        encoding="utf-8",
    )
    assert run_idn("IDN-003", str(model)) == ()


# trace: PRD-TRACE-016
def test_newest_release_tag_is_none_when_there_is_no_tag(repository: Repository) -> None:
    repository.commit("First commit.", tag="trace-baseline")
    repository.commit("Second commit.")
    assert newest_release_tag(repository.root) is None


# trace: PRD-TRACE-016
def test_newest_release_tag_is_the_nearest_v_tag_before_head(repository: Repository) -> None:
    repository.commit("First commit.", tag="v1.0.0")
    repository.commit("Second commit.", tag="v1.1.0")
    repository.commit("Third commit.", tag="trace-baseline")
    repository.commit("Fourth commit.", tag="v2.0.0")
    assert newest_release_tag(repository.root) == "v1.1.0"
    repository.commit("Fifth commit.")
    assert newest_release_tag(repository.root) == "v2.0.0"


# trace: PRD-VAL-011
def test_resolve_gives_the_commit_of_a_reference(repository: Repository) -> None:
    commit = repository.commit("First commit.", tag="v1.0.0")
    assert resolve(repository.root, "v1.0.0") == commit
    assert resolve(repository.root, "main") == commit


# trace: PRD-VAL-011
@pytest.mark.parametrize("ref", ["v9.9.9", "-v", ""])
def test_resolve_rejects_a_reference_that_does_not_exist(repository: Repository, ref: str) -> None:
    repository.commit("First commit.")
    with pytest.raises(ToolchainError, match="Git reference"):
        resolve(repository.root, ref)


# trace: PRD-VAL-011
def test_baseline_needs_a_git_repository(tmp_path: Path) -> None:
    with pytest.raises(ToolchainError, match="is not in a Git repository"):
        read_baseline("HEAD", Configuration(), tmp_path)


# trace: PRD-VAL-011
def test_checkout_copies_only_the_model_files(repository: Repository) -> None:
    repository.model(RULE_MODELS / "IDN-002" / "baseline.sysml")
    (repository.root / "model" / "notes.txt").write_text("Notes.\n", encoding="utf-8")
    (repository.root / "other.sysml").write_text("package Other;\n", encoding="utf-8")
    commit = repository.commit("Add the model.")
    (repository.root / MODEL).unlink()
    with checkout("HEAD", repository.configuration, repository.root) as copy:
        assert copy.commit == commit
        assert [file.relative_to(copy.root).as_posix() for file in copy.files] == [MODEL]
        assert sorted(path.name for path in copy.root.rglob("*") if path.is_file()) == [
            "model.sysml"
        ]
        folder = copy.root
    assert not folder.exists()


# trace: PRD-VAL-011
def test_baseline_with_no_model_file_gives_an_empty_ir(repository: Repository) -> None:
    repository.commit("No model.", tag="v0.1.0")
    assert read_baseline("v0.1.0", repository.configuration, repository.root) == Ir()


# trace: PRD-VAL-011, PRD-CORE-002
def test_validate_stops_with_exit_code_2_for_a_reference_that_does_not_exist(
    repository: Repository, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository.model(RULE_MODELS / "IDN-001" / "baseline.sysml")
    repository.commit("Add the model.")
    monkeypatch.chdir(repository.root)
    assert main(["validate", "--baseline", "v9.9.9"]) == 2
    assert capsys.readouterr().err == (
        'dsml: error: The Git reference "v9.9.9" does not exist in the local repository.\n'
    )


# trace: PRD-VAL-011
def test_validate_runs_the_idn_rules_only_with_a_baseline(
    repository: Repository, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository.model(RULE_MODELS / "IDN-001" / "baseline.sysml")
    repository.commit("Add the model.", tag="v1.0.0")
    repository.model(RULE_MODELS / "IDN-001" / "reject.sysml")
    monkeypatch.chdir(repository.root)

    # The test model is not complete, thus other rules, for example STR-001, give errors.
    main(["validate", "--format", "json"])
    findings = json.loads(capsys.readouterr().out)["findings"]
    assert not [item for item in findings if item["rule"].startswith("IDN-")]

    assert main(["validate", "--baseline", "v1.0.0"]) == 1
    assert "model/model.sysml:11:5: error: IDN-001: " in capsys.readouterr().out

    (repository.root / "dsml.toml").write_text(
        f'{CONFIG}\n[trace]\nbaseline = "v1.0.0"\n', encoding="utf-8"
    )
    assert main(["validate"]) == 1
    assert "error: IDN-001: " in capsys.readouterr().out
