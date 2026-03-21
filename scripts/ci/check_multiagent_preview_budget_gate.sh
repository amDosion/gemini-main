#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v npm >/dev/null 2>&1; then
  echo "[error] npm is required for check_multiagent_preview_budget_gate.sh" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[error] python3 is required for check_multiagent_preview_budget_gate.sh" >&2
  exit 1
fi

KEY_TEST_FILES=(
  "frontend/components/multiagent/useResultPanelPreviewState.test.tsx"
  "frontend/components/multiagent/MultiAgentWorkflowEditorReactFlow.resultPanel.test.tsx"
  "frontend/components/multiagent/workflowResultUtils.previewMerge.test.ts"
  "frontend/components/views/multiagent/useWorkflowHistoryPreviewState.test.ts"
  "frontend/components/views/multiagent/useWorkflowHistoryController.test.ts"
  "frontend/services/workflowHistoryService.test.ts"
  "backend/tests/test_workflow_preview_budget_contract.py"
  "backend/tests/test_workflow_history_image_service.py"
)

for test_file in "${KEY_TEST_FILES[@]}"; do
  if [[ ! -f "$test_file" ]]; then
    echo "[error] missing preview-budget gate test file: $test_file" >&2
    exit 1
  fi
done

echo "[check] Multi-agent preview-budget frontend regression gate"
npm run test -- \
  frontend/components/multiagent/useResultPanelPreviewState.test.tsx \
  frontend/components/multiagent/MultiAgentWorkflowEditorReactFlow.resultPanel.test.tsx \
  frontend/components/multiagent/workflowResultUtils.previewMerge.test.ts \
  frontend/components/views/multiagent/useWorkflowHistoryPreviewState.test.ts \
  frontend/components/views/multiagent/useWorkflowHistoryController.test.ts \
  frontend/services/workflowHistoryService.test.ts

echo "[check] Multi-agent preview-budget backend contract gate"
(
  cd backend
  PYTHONPATH=. python3 -m pytest \
    tests/test_workflow_preview_budget_contract.py \
    tests/test_workflow_history_image_service.py \
    -q
)

echo "[ok] Multi-agent preview-budget gate passed"
