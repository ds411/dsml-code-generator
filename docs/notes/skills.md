# Command `dsml skills install`

Story #229 added the subcommand `dsml skills install` (PRD-AI-004 to PRD-AI-006, Q68). The command writes the skills for AI agents into a project. The module is `src/dsml/skills/__init__.py`.

## Skills in the package

Each skill is a folder in `src/dsml/skills/`, in the Agent Skills format. The folder has a `SKILL.md` file and reference files. The command copies each folder that has a `SKILL.md` file. Thus a new skill needs no change to a list in the code.

| Skill | Folder | Story |
| --- | --- | --- |
| Modeling skill | `src/dsml/skills/dsml-modeling/` | #230 |
| CLI skill | `src/dsml/skills/dsml-cli/` | #231 |

The command does not copy a `__pycache__` folder. The wheel and the sdist contain all files of `src/dsml/skills/` (`tests/test_package.py`).

## Use

```text
dsml skills install [--output <folder>] [--verbose]
```

- The default destination folder is `.claude/skills/` in the current folder (PRD-AI-004).
- The option `--output` selects a different folder, for example the skill folder of a different AI agent.
- The command writes one line for each skill to standard output, sorted by name: `install <folder>`.
- The command does not read a configuration file and uses no network.

## Rules

- The command owns only the skill folders of the package. It removes each of these folders in the destination folder, then writes the files of the skill. Thus a file that a later version removes does not stay.
- The command does not change a different file or folder in the destination folder (PRD-AI-005).
- The command copies the bytes of each file. Two runs with the same toolchain version write byte-identical files (PRD-AI-006).
- If the command cannot write a file, it stops with exit code 2 and a message.

## Tests

`tests/test_skills_command.py` uses a folder with two test skills. It makes sure that two runs write the same bytes, that the command replaces only its own folders, and that the default folder is `.claude/skills/`.
