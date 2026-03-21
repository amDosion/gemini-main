#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v npm >/dev/null 2>&1; then
  echo "[error] npm is required for check_multiagent_frontend_hardening.sh" >&2
  exit 1
fi

TEST_FILES=(
  "frontend/services/boundedRecordCache.test.ts"
  "frontend/components/views/multiagent/useWorkflowHistoryController.test.ts"
  "frontend/components/multiagent/useAgentRegistry.test.tsx"
  "frontend/components/multiagent/AdkSessionPanel.test.tsx"
  "frontend/components/multiagent/MultiAgentWorkflowEditorReactFlow.resultPanel.test.tsx"
  "frontend/components/multiagent/workflowEditorUtils.focus.test.ts"
)

for test_file in "${TEST_FILES[@]}"; do
  if [[ ! -f "$test_file" ]]; then
    echo "[error] missing frontend hardening test file: $test_file" >&2
    exit 1
  fi
done

echo "[check] Multi-agent frontend hardening gate (cache/history/registry/adk/result/focus)"
npm run test -- "${TEST_FILES[@]}"
echo "[ok] Multi-agent frontend hardening gate passed"
