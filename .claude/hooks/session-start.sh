#!/bin/bash
# SessionStart hook for Claude Code cloud sessions.
#
# The hook installs the dev tools of the DSML toolchain, so that ruff,
# pyright and pytest operate at the start of each session:
#   1. pnpm, at the version in the "packageManager" field of package.json.
#   2. Python, at the version in .python-version, with uv.
#   3. The Python dependencies, from uv.lock.
#   4. The Node.js runtime and the Node.js dev tools, from pnpm-lock.yaml.
#
# You can run the hook again with no problem. Outside a cloud session,
# it does nothing.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

# Claude reads the standard output of a SessionStart hook. Send the
# output of the install tools to standard error.
exec 3>&1 1>&2

# 1. pnpm. Read the version outside the project, because pnpm can
# switch to the version of package.json in the project folder.
pnpm_version="$(python3 -c 'import json; print(json.load(open("package.json"))["packageManager"].split("@", 1)[1])')"
if [ "$(cd / && pnpm --version 2>/dev/null || true)" != "$pnpm_version" ]; then
  npm install --global --no-fund --no-audit "pnpm@${pnpm_version}"
  hash -r
fi

# 2. Python.
uv python install

# 3. Python dependencies.
uv sync --frozen

# 4. Node.js runtime and Node.js dev tools.
pnpm install --frozen-lockfile

echo "Dev tools are ready: pnpm $(cd / && pnpm --version), Python $(uv run python -c 'import platform; print(platform.python_version())'), Node.js $(pnpm exec node --version)." >&3
