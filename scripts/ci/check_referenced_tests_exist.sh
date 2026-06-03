#!/usr/bin/env bash
# CI preflight (T1/T4): fail if any test file referenced by the CI workflow or a
# gate script does not exist. This prevents the "phantom test reference" rot that
# previously made CI red by construction (28 backend test files referenced by
# ci.yml were never committed).
set -euo pipefail

cd "$(dirname "$0")/../.."

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

scan() {
  local file="$1"
  [ -f "$file" ] || return 0
  # Backend pytest paths look like tests/....py and resolve under backend/.
  # `|| true` keeps a no-match grep (exit 1) from aborting under `set -e`.
  local backend_refs frontend_refs t
  backend_refs="$(grep -oE 'tests/[A-Za-z0-9_./-]+\.py' "$file" 2>/dev/null | sort -u || true)"
  for t in $backend_refs; do
    if [ ! -f "backend/$t" ] && [ ! -f "$t" ]; then
      echo "MISSING (backend) referenced in $file: $t"
    fi
  done
  # Frontend test paths look like frontend/....test.ts(x).
  frontend_refs="$(grep -oE 'frontend/[A-Za-z0-9_./-]+\.test\.tsx?' "$file" 2>/dev/null | sort -u || true)"
  for t in $frontend_refs; do
    if [ ! -f "$t" ]; then
      echo "MISSING (frontend) referenced in $file: $t"
    fi
  done
}

{
  scan ".github/workflows/ci.yml"
  for s in scripts/ci/*.sh; do
    [ "$(basename "$s")" = "check_referenced_tests_exist.sh" ] && continue
    scan "$s"
  done
} > "$tmp"

if [ -s "$tmp" ]; then
  echo "CI preflight FAILED — referenced test files do not exist:" >&2
  cat "$tmp" >&2
  exit 1
fi

echo "CI preflight OK — every referenced test file exists."
