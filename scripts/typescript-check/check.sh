#!/usr/bin/env bash
# Check the tools of the TypeScript targets with one or more TypeScript
# versions (story #190, decision Q64).
#
# trace: PRD-APP-201, PRD-APP-301, PRD-CORE-011, PRD-CORE-035, PRD-CICD-004
#
# Usage: scripts/typescript-check/check.sh [TYPESCRIPT_VERSION ...]
# Example: scripts/typescript-check/check.sh 7.0.2 6.0.3
#
# For each version, the script copies the test project into a temporary
# folder and installs it with an override of the TypeScript version. Then
# it runs each check and writes a Markdown table of the results. The logs
# go into the folder that RESULTS_DIR gives, or into a temporary folder.
# The install uses the network. This is not validation, generation or a
# trace report, so PRD-TOP-005 permits it.
set -uo pipefail

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
results_dir="${RESULTS_DIR:-$(mktemp -d)}"
mkdir -p "$results_dir"

if [ "$#" -eq 0 ]; then
  set -- 7.0.2 6.0.3
fi

# The checks. Each line is: <name>|<folder in the project>|<command>.
checks=(
  "tsc --noEmit (React)|react-app|pnpm exec tsc --noEmit -p tsconfig.json"
  "tsc --noEmit (Next.js)|next-app|pnpm exec tsc --noEmit -p tsconfig.json"
  "ESLint with type-aware rules|.|pnpm exec eslint ."
  "Steiger (React)|react-app|pnpm exec steiger ./src"
  "Steiger (Next.js)|next-app|pnpm exec steiger ./src"
  "Prettier|.|pnpm exec prettier --check ."
  "Vitest (React)|react-app|pnpm exec vitest run"
  "Vitest (Next.js)|next-app|pnpm exec vitest run"
  "vite build|react-app|pnpm exec vite build"
  "next build|next-app|pnpm exec next build"
)

table="$results_dir/results.md"
{
  printf '| Check |'
  for version in "$@"; do printf ' TypeScript %s |' "$version"; done
  printf '\n| --- |'
  for _ in "$@"; do printf ' --- |'; done
  printf '\n'
} > "$table"

declare -A result
for version in "$@"; do
  work_dir="$(mktemp -d)"
  log_dir="$results_dir/typescript-$version"
  mkdir -p "$log_dir"
  echo "TypeScript $version: install the test project in $work_dir"
  tar -C "$source_dir" --exclude=node_modules --exclude=.next --exclude=dist -cf - . \
    | tar -C "$work_dir" -xf -
  printf '\noverrides:\n  typescript: "%s"\n' "$version" >> "$work_dir/pnpm-workspace.yaml"
  if ! (cd "$work_dir" && pnpm install --no-frozen-lockfile) > "$log_dir/install.log" 2>&1; then
    echo "TypeScript $version: the install failed. See $log_dir/install.log."
    for check in "${checks[@]}"; do result["$version|${check%%|*}"]="Not run"; done
    continue
  fi
  (cd "$work_dir" && pnpm list -r --depth 0) > "$log_dir/versions.log" 2>&1

  index=0
  for check in "${checks[@]}"; do
    index=$((index + 1))
    IFS='|' read -r name folder command <<< "$check"
    log="$log_dir/$(printf '%02d' "$index").log"
    if (cd "$work_dir/$folder" && eval "$command") > "$log" 2>&1; then
      result["$version|$name"]="Pass"
    else
      result["$version|$name"]="Fail"
    fi
    echo "TypeScript $version: $name: ${result["$version|$name"]}"
  done
  rm -rf "$work_dir"
done

failed=0
for check in "${checks[@]}"; do
  name="${check%%|*}"
  printf '| %s |' "$name" >> "$table"
  for version in "$@"; do
    printf ' %s |' "${result["$version|$name"]}" >> "$table"
    [ "${result["$version|$name"]}" = "Pass" ] || failed=1
  done
  printf '\n' >> "$table"
done

echo
cat "$table"
echo
echo "The logs are in $results_dir."
exit "$failed"
