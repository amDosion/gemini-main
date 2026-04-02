#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v npm >/dev/null 2>&1; then
  echo "[error] npm is required for check_multiagent_media_contract.sh" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[error] python3 is required for check_multiagent_media_contract.sh" >&2
  exit 1
fi

KEY_TEST_FILES=(
  "frontend/components/multiagent/agentRegistryService.test.ts"
  "frontend/components/multiagent/providerModelUtils.media.test.ts"
  "frontend/components/multiagent/PropertiesPanel.mediaTasks.test.tsx"
  "frontend/components/multiagent/agentManager/AgentManagerEditorForm.test.tsx"
  "frontend/components/multiagent/agentManager/AgentManagerEditorForm.failClosed.test.tsx"
  "frontend/components/multiagent/agentManager/AgentManagerListView.test.tsx"
  "frontend/components/multiagent/CustomNode.mediaPreview.test.tsx"
  "frontend/components/multiagent/useResultPanelPreviewState.test.tsx"
  "frontend/components/multiagent/MultiAgentWorkflowEditorReactFlow.resultPanel.test.tsx"
  "frontend/components/multiagent/WorkflowTemplateSelector.mediaResult.test.tsx"
  "frontend/components/multiagent/workflowUtils.autoLayout.test.ts"
  "frontend/components/multiagent/workflowResultUtils.previewMerge.test.ts"
  "frontend/components/multiagent/workflowEditorUtils.media.test.ts"
  "frontend/components/multiagent/nodeParamSummaryUtils.media.test.ts"
  "frontend/components/multiagent/workflowTemplateLoader.media.test.ts"
  "frontend/components/views/multiagent/useWorkflowHistoryController.media.test.ts"
  "frontend/components/views/multiagent/useWorkflowHistoryPreviewState.test.ts"
  "frontend/services/workflowHistoryService.media.test.ts"
  "backend/tests/test_agent_seed_service_media_defaults.py"
  "backend/tests/test_adk_samples_importer_seed_sync.py"
  "backend/tests/test_workflow_available_models_media_classification.py"
  "backend/tests/test_workflow_engine_media_execution.py"
  "backend/tests/test_workflow_history_media_service.py"
  "backend/tests/test_workflow_engine_media_output_sanitization.py"
)

for test_file in "${KEY_TEST_FILES[@]}"; do
  if [[ ! -f "$test_file" ]]; then
    echo "[error] missing media-contract test file: $test_file" >&2
    exit 1
  fi
done

echo "[check] Multi-agent media frontend task/model contract gate"
npm run test -- \
  frontend/components/multiagent/agentRegistryService.test.ts \
  frontend/components/multiagent/agentManager/AgentManagerListView.test.tsx \
  frontend/components/multiagent/providerModelUtils.media.test.ts \
  frontend/components/multiagent/PropertiesPanel.mediaTasks.test.tsx \
  frontend/components/multiagent/agentManager/AgentManagerEditorForm.test.tsx \
  frontend/components/multiagent/agentManager/AgentManagerEditorForm.failClosed.test.tsx

echo "[check] Multi-agent workflow history media UI gate"
npm run test -- \
  frontend/components/views/multiagent/useWorkflowHistoryController.media.test.ts \
  frontend/components/views/multiagent/useWorkflowHistoryPreviewState.test.ts \
  frontend/services/workflowHistoryService.media.test.ts

echo "[check] Multi-agent result-panel media parity gate"
npm run test -- \
  frontend/components/multiagent/useResultPanelPreviewState.test.tsx \
  frontend/components/multiagent/MultiAgentWorkflowEditorReactFlow.resultPanel.test.tsx \
  frontend/components/multiagent/workflowResultUtils.previewMerge.test.ts

echo "[check] Multi-agent inline-preview and template media parity gate"
npm run test -- \
  frontend/components/multiagent/PropertiesPanel.mediaTasks.test.tsx \
  frontend/components/multiagent/CustomNode.mediaPreview.test.tsx \
  frontend/components/multiagent/WorkflowTemplateSelector.mediaResult.test.tsx \
  frontend/components/multiagent/workflowUtils.autoLayout.test.ts

echo "[check] Multi-agent media frontend normalization gate"
npm run test -- \
  frontend/components/multiagent/workflowEditorUtils.media.test.ts \
  frontend/components/multiagent/nodeParamSummaryUtils.media.test.ts \
  frontend/components/multiagent/workflowTemplateLoader.media.test.ts

echo "[check] Multi-agent media backend contract gate"
(
  cd backend
  PYTHONPATH=. python3 -m pytest \
    tests/test_agent_seed_service_media_defaults.py \
    tests/test_adk_samples_importer_seed_sync.py \
    tests/test_workflow_available_models_media_classification.py \
    tests/test_workflow_engine_media_execution.py \
    tests/test_workflow_history_media_service.py \
    tests/test_workflow_engine_media_output_sanitization.py \
    -q
)

echo "[ok] Multi-agent media contract gate passed"
