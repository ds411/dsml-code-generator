"""Tests of the GitHub Action of the toolchain (story #137).

The workflow `.github/workflows/action-test.yml` runs the action. These
tests examine the text of `action.yml`, of the workflow and of
`docs/action.md`.
"""

import re
from pathlib import Path

from dsml.generate.pipelines.generator import ACTIONS
from dsml.generate.pipelines.workflow import pinned_action
from dsml.versions import load_baseline, pinned_version

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "action.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "action-test.yml"
DOCUMENT = ROOT / "docs" / "action.md"

_USES = re.compile(r"^ +(?:- )?uses: (.+)$", flags=re.MULTILINE)
_FORM = re.compile(r"[\w.-]+/[\w./-]+@[0-9a-f]{40} # v[0-9]+\.[0-9]+\.[0-9]+")


def _section(text: str, name: str) -> str:
    """Give the lines of one top-level key of `action.yml`."""
    match = re.search(rf"^{name}:\n((?:(?: .*)?\n)*)", text, flags=re.MULTILINE)
    assert match is not None, name
    return match.group(1)


def _inputs() -> list[str]:
    section = _section(ACTION.read_text(encoding="utf-8"), "inputs")
    return re.findall(r"^  ([a-z-]+):$", section, flags=re.MULTILINE)


# trace: PRD-CICD-014
def test_each_third_party_action_has_the_sha_of_the_baseline() -> None:
    baseline = load_baseline()
    pinned = {pinned_action(item, baseline).uses for item in ACTIONS.values()}
    for path in (ACTION, WORKFLOW):
        uses = [value for value in _USES.findall(path.read_text(encoding="utf-8")) if value != "./"]
        assert uses, path
        for value in uses:
            assert _FORM.fullmatch(value), value
            assert value in pinned, value


# trace: PRD-CORE-050, PRD-CORE-051
def test_action_sets_up_the_pinned_uv_and_uploads_sarif() -> None:
    text = ACTION.read_text(encoding="utf-8")
    assert "using: composite" in text
    assert f'version: "{pinned_version("uv")}"' in text
    uses = {value.split("@")[0] for value in _USES.findall(text)}
    assert uses == {"astral-sh/setup-uv", "github/codeql-action/upload-sarif"}
    assert "--format sarif" in text


# trace: PRD-CORE-050
def test_action_installs_the_wheel_of_the_github_release() -> None:
    text = ACTION.read_text(encoding="utf-8")
    url = "https://github.com/${DSML_REPOSITORY}/releases/download/v${DSML_VERSION}/"
    assert url + "dsml-${DSML_VERSION}-py3-none-any.whl" in text
    # Q63: there is no package index.
    assert "index" not in " ".join(_inputs())
    assert "--index-url" not in text


# trace: PRD-CORE-050
def test_version_is_the_only_mandatory_input() -> None:
    section = _section(ACTION.read_text(encoding="utf-8"), "inputs")
    blocks = re.split(r"^  (?=[a-z-]+:$)", section, flags=re.MULTILINE)[1:]
    required = [block.split(":")[0] for block in blocks if "required: true" in block]
    assert required == ["version"]


# trace: PRD-CORE-009
def test_dsml_reads_no_input_from_a_terminal() -> None:
    text = ACTION.read_text(encoding="utf-8")
    # Each call of dsml or of a dsml module. The SARIF step gives its Python
    # script on standard input, with "-".
    start = r'^ *(?:run: \')?"\$(?:venv/bin/dsml|DSML_ACTION_BIN|DSML_ACTION_PYTHON)" (?!- )'
    calls = re.findall(start + ".*$", text, flags=re.MULTILINE)
    assert len(calls) == 3
    for call in calls:
        assert "< /dev/null" in call, call


def test_document_gives_each_input_and_output() -> None:
    document = DOCUMENT.read_text(encoding="utf-8")
    rows = set(re.findall(r"^\| `([a-z-]+)` \|", document, flags=re.MULTILINE))
    outputs = re.findall(
        r"^  ([a-z-]+):$",
        _section(ACTION.read_text(encoding="utf-8"), "outputs"),
        flags=re.MULTILINE,
    )
    assert rows == {*_inputs(), *outputs}


def test_workflow_uses_the_local_action() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert _USES.findall(text).count("./") == 3
    assert 'sarif: "true"' in text
    assert "tests/models/action" in text
