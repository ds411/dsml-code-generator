# Work process

This document gives the work process for this repository. It applies to people and to Claude Code sessions. `CLAUDE.md` gives a short form of these rules.

## Roles

| Role | Tasks |
| --- | --- |
| Product owner | Approves issues. Answers decision issues. Reviews pull requests. Merges each pull request with a squash merge. |
| Developer (a person or a Claude Code session) | Does the work of one story on one branch. Opens a pull request. Adds the recommended squash commit message. Does not merge. |

## Work cycle

1. Take the next open story issue in the order of its milestone. Look at the steps in the milestone issue.
2. Make a new branch from the newest `main`.
3. Do the work. Commit with the commit template.
4. Push the branch and open a pull request to `main`.
5. Add a comment with the recommended squash commit message.
6. Correct the pull request until the review and CI pass.
7. The product owner does a squash merge. The story issue closes. If other stories of the same step go in parallel, follow "Merge order" below.
8. After the last story of the last step of a milestone merges, examine the exit criteria of the milestone. Follow "Milestone exit" below.

## Issues

The GitHub issue tracker holds all open items and shows when they are complete. Do not keep a list of open items in a file in the repository.

| Issue type | Template in `.github/ISSUE_TEMPLATE/` | Label | Use |
| --- | --- | --- | --- |
| Milestone | `milestone.md` | `milestone` | One milestone of the plan, for example M1. Its stories are sub-issues. |
| Story | `story.md` | `story` | One unit of work that one branch and one pull request complete. |
| Defect | `defect.md` | `defect` | A result that does not agree with a requirement or with the documentation. |
| Decision | `decision.md` | `decision` | A question that the product owner must answer. |

Use these rules for issues:

1. Use the template of the issue type. Fill in each section. Write "None" in a section that does not apply.
2. Give the PRD requirement IDs and the decision IDs that the issue is about.
3. Make each story small enough for one pull request. If a story is too large, divide it into two or more stories before you start the work.
4. Add each story as a sub-issue of its milestone.
5. Give the order of all the stories in the milestone issue. Put the stories into numbered steps in the section "Stories". Do the steps in their order.
6. In the milestone issue, write which stories can go in parallel. Put them in the same step, and give the stories that each step needs. Obey "Parallel stories" below.
7. When you add a story to a milestone, put it in a step. Then make sure that the order is still correct.
8. Put the label `deferred` on an item that waits for a resource, for example an AWS account. Give the reason in the issue.
9. A pull request closes its story with the line `Closes #<issue>`. Close a milestone only when all its stories are closed and all its exit criteria are true (see "Milestone exit").
10. When the product owner answers a decision issue, record the answer. If the answer changes a PRD, follow "Changes to a PRD requirement" below. Then close the issue.

## Milestone exit

The exit criteria of a milestone tell when the milestone is complete. Examine them after the last step of the milestone, when all its stories are closed.

1. Examine each exit criterion on the newest `main`. Use the code, the documents and the CI results.
2. Add a comment to the milestone issue. For each criterion, give the result and the data that shows it, for example a file, a test or a CI run.
3. If all exit criteria are true, mark each criterion as complete in the milestone issue. Then close the milestone issue.
4. If one or more exit criteria are not true, add one or more stories that make them true. Put these stories in one or more new steps at the end of the milestone issue.
5. Do the new steps. Then examine the exit criteria again from step 1.

## Parallel stories

The stories in one step go in parallel. Use these rules to make a step:

1. Put 4 or fewer stories in a step. If more stories can go in parallel, divide them into two or more steps.
2. For each story, write the main files that it changes in the milestone issue.
3. Put stories in the same step only if they change different files.
4. If two or more stories must change the same file, for example a test fixture, a registry or the CLI, make a setup story. The setup story changes the shared file before the step starts. Put it in the step before.
5. Make the setup story as small as possible. After it merges, the stories of the step only add new files, or change files that no other story of the step changes.

## Merge order

When the stories of one step go in parallel, their pull requests merge one at a time. Each merge then causes only one update from `main` in each pull request.

1. Correct each pull request until its CI passes. Then stop the work on it and report that it is ready. Do not merge `main` into the branch at this time.
2. Merge the ready pull requests one at a time, in the order of the stories in the milestone issue.
3. Immediately before the turn of a pull request, merge the newest `main` into its branch. Correct the merge conflicts.
4. Push the branch. Merge the pull request only after CI passes on that push.
5. Do steps 3 and 4 for the next pull request in the order.

If CI fails on the update from `main`, correct the branch before the next pull request starts its turn.

## Branches

1. Start each story on a new branch from the newest `main`.
2. Give the branch the name `story/<issue>-<short-name>`, for example `story/12-dsml-library`. If the Claude Code session gives a branch name, use that name.
3. Put the work of one story only on a branch.
4. Do not push to `main`. Do not merge a pull request.
5. After the product owner merges the pull request, do not add commits to its branch. Start new work on a new branch from `main`.
6. After you open the pull request, do not rewrite the history of the branch. To get changes from `main`, merge `main` into the branch.

## Commits

Use the commit template in `.gitmessage`. To set it, run this command one time in your clone:

```sh
git config commit.template .gitmessage
```

Use these rules for commit messages:

1. Write the subject line in the imperative form, for example "Add the IR writer". Use 72 characters or fewer and no period at the end.
2. Put one blank line after the subject line.
3. In the body, tell what changed and why. Wrap the lines at 72 characters.
4. Give the story issue in the last paragraph, for example `Refs #12`.
5. Use ASD-STE100 (see `CLAUDE.md`).
6. A Claude Code session adds its attribution lines at the end of the message, as its session instructions tell it.

The squash merge replaces the commits of a branch with one commit on `main`. The branch commits are for the review only.

## Pull requests

1. Open the pull request to `main`. Use the title of the story issue, or a short title in the imperative form.
2. Fill in each section of `.github/pull_request_template.md`. Put `Closes #<issue>` in the section "Issue".
3. After you open the pull request, add one comment with the recommended squash commit message. Use the form in `.github/squash_commit_comment_template.md`.
4. After each push that changes the scope of the pull request, edit that comment so that it agrees with the pull request. Do not add a second squash commit message comment.
5. Before you ask for a review, CI must pass.
6. Reply to each review comment. Push the corrections to the same branch.
7. Do not merge. The product owner selects "Squash and merge", copies the title and the description from the comment into the form, and merges.

## Squash commit message

The squash commit is the only commit that `main` keeps for a story. Its message must describe the full pull request, not the branch commits.

- **Commit title.** Write a summary in the imperative form, then the pull request number, for example `Add the DSML library package (#14)`. Use 72 characters or fewer.
- **Extended description.** Write one short paragraph that tells what changed and why. Then write a list of the main changes, the line `Closes #<issue>`, and the attribution lines of the Claude Code session, if a session did the work. Wrap the lines at 72 characters.

The GitHub "Squash and merge" form has two fields: the commit title and the extended description. The comment puts each field in a separate code block, so the product owner can copy each field with one click. A Claude Code session puts its comment footer below the two code blocks, not in them.

## Changes to a PRD requirement

The PRDs, the indexes and the DSML model of the PRDs must agree. To change a PRD requirement, do all these steps in one pull request:

1. Record the decision in a decision record in `docs/decisions/`. Add a row to `docs/index/decisions.csv`.
2. Change the requirement in `docs/prd/`. Add the decision ID to its Source column.
3. Change the row of the requirement in `docs/index/requirements.csv`.
4. Change the `doc` comment of the requirement in `docs/model/prd/*.sysml`.
5. For a new requirement, use the next ID that was not used before. Do not use a deleted ID again.

## Definition of done

A story is complete when all these conditions are true:

- Each acceptance criterion of the story is true.
- CI passes on the pull request.
- New code has tests. Each generator change has golden-file tests (PRD-CORE-030).
- Each module, class or function that implements a PRD requirement has a trace comment (see `CLAUDE.md`).
- Documentation, comments and messages use ASD-STE100.
- The pull request has a recommended squash commit message that agrees with its changes.
- The product owner merged the pull request.
