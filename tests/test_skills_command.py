"""Tests of the command `dsml skills install` (story #229)."""

from pathlib import Path

import pytest

from dsml import skills
from dsml.cli import main

SKILL_TEXT = "---\nname: {name}\ndescription: A test skill.\n---\n\n# {name}\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """A folder with two test skills, a folder with no SKILL.md file and a cache folder."""
    folder = tmp_path / "source"
    for name in ("skill-b", "skill-a"):
        _write(folder / name / "SKILL.md", SKILL_TEXT.format(name=name))
        _write(folder / name / "references" / "rules.md", f"# Rules of {name}\n")
        _write(folder / name / "__pycache__" / "x.pyc", "cache")
    _write(folder / "no-skill" / "README.md", "Not a skill.\n")
    _write(folder / "__pycache__" / "SKILL.md", "cache")
    return folder


@pytest.fixture
def test_skills(source: Path, monkeypatch: pytest.MonkeyPatch) -> list[skills.Skill]:
    """Make the command install the test skills, not the skills of the package."""
    found = skills.package_skills(source)
    monkeypatch.setattr(skills, "package_skills", lambda: found)
    return found


def _tree(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


# trace: PRD-AI-001
def test_package_skills_are_the_folders_with_a_skill_file(source: Path) -> None:
    found = skills.package_skills(source)
    assert [skill.name for skill in found] == ["skill-a", "skill-b"]
    assert [path.as_posix() for path, _ in found[0].files] == ["SKILL.md", "references/rules.md"]


# trace: PRD-AI-001
def test_each_skill_of_the_package_has_a_skill_file() -> None:
    for skill in skills.package_skills():
        assert any(path.as_posix() == skills.SKILL_FILE for path, _ in skill.files), skill.name


# trace: PRD-AI-004, PRD-AI-006
def test_install_writes_the_same_bytes_at_each_run(
    test_skills: list[skills.Skill], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "out"
    assert main(["skills", "install", "--output", str(output)]) == 0
    first = _tree(output)
    report = capsys.readouterr().out
    assert main(["skills", "install", "--output", str(output)]) == 0
    assert _tree(output) == first
    assert capsys.readouterr().out == report
    assert report == "".join(
        f"install {(output / name).as_posix()}\n" for name in ("skill-a", "skill-b")
    )
    assert sorted(first) == [
        "skill-a/SKILL.md",
        "skill-a/references/rules.md",
        "skill-b/SKILL.md",
        "skill-b/references/rules.md",
    ]
    assert first["skill-a/SKILL.md"] == SKILL_TEXT.format(name="skill-a").encode()


# trace: PRD-AI-004
def test_install_writes_into_claude_skills_by_default(
    test_skills: list[skills.Skill], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["skills", "install"]) == 0
    assert (tmp_path / ".claude" / "skills" / "skill-a" / "SKILL.md").is_file()


# trace: PRD-AI-005
def test_install_replaces_only_the_skill_folders_that_it_owns(
    test_skills: list[skills.Skill], tmp_path: Path
) -> None:
    output = tmp_path / "out"
    _write(output / "skill-a" / "old.md", "An old file of the skill.\n")
    _write(output / "skill-a" / "SKILL.md", "Changed.\n")
    _write(output / "my-skill" / "SKILL.md", "A skill of the user.\n")
    _write(output / "notes.md", "A file of the user.\n")
    others = {name: data for name, data in _tree(output).items() if name.startswith(("my", "n"))}
    assert main(["skills", "install", "--output", str(output)]) == 0
    tree = _tree(output)
    assert "skill-a/old.md" not in tree
    assert tree["skill-a/SKILL.md"] == SKILL_TEXT.format(name="skill-a").encode()
    assert {name: data for name, data in tree.items() if name.startswith(("my", "n"))} == others


# trace: PRD-AI-004
def test_install_stops_with_exit_code_2_if_it_cannot_write(
    test_skills: list[skills.Skill], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "file"
    output.write_text("A file, not a folder.\n", encoding="utf-8")
    assert main(["skills", "install", "--output", str(output)]) == 2
    assert "dsml: error: Cannot write the skill files in" in capsys.readouterr().err


def test_skills_needs_an_action(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["skills"]) == 2
    assert "the following arguments are required: <action>" in capsys.readouterr().err


# trace: PRD-AI-001, PRD-AI-004, PRD-AI-006
def test_install_writes_both_skills_of_the_package_with_the_same_bytes_at_each_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    for output in (first, second):
        output.mkdir()
        assert main(["skills", "install", "--output", str(output)]) == 0
    assert capsys.readouterr().out == "".join(
        f"install {(output / name).as_posix()}\n"
        for output in (first, second)
        for name in ("dsml-cli", "dsml-modeling")
    )
    tree = _tree(first)
    assert sorted({name.split("/")[0] for name in tree}) == ["dsml-cli", "dsml-modeling"]
    assert {"dsml-cli/SKILL.md", "dsml-modeling/SKILL.md"} <= set(tree)
    assert _tree(second) == tree
    assert main(["skills", "install", "--output", str(first)]) == 0
    assert _tree(first) == tree
    for skill in skills.package_skills():
        for path, data in skill.files:
            assert tree[f"{skill.name}/{path.as_posix()}"] == data
