#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v rg >/dev/null 2>&1; then
  echo "[error] rg is required for check_adk_usability_accuracy_contract.sh" >&2
  exit 1
fi

require_pattern() {
  local pattern="$1"
  local file="$2"
  local label="$3"
  if rg -n --max-count 1 "$pattern" "$file" >/dev/null; then
    echo "[ok] $label"
    return 0
  fi
  echo "[error] missing pattern for $label: $pattern ($file)" >&2
  exit 1
}

echo "[check] ADK usability + accuracy contract (confirm contract / strategy enum / run-live aggregation)"

require_pattern 'confirm-tool requires explicit confirmed=true' 'backend/app/routers/ai/multi_agent.py' 'confirm contract enforces explicit approve'
require_pattern 'approval_ticket and nonce are required \(approval_ticket object\)' 'backend/app/routers/ai/multi_agent.py' 'confirm contract requires approval_ticket + nonce'
require_pattern 'confirm nonce replay detected' 'backend/app/routers/ai/multi_agent.py' 'confirm contract nonce replay guard'
require_pattern '_materialize_approval_ticket_from_request' 'backend/app/routers/ai/multi_agent.py' 'confirm contract legacy ticket materialization'
require_pattern 'confirm-contract-approval-ticket-object' 'backend/tests/test_adk_confirm_tool_contract.py' 'confirm contract regression case for approval_ticket object'
require_pattern 'confirm-contract-legacy-ticket-materialization' 'backend/tests/test_adk_confirm_tool_contract.py' 'confirm contract regression case for legacy ticket materialization'
require_pattern 'test_confirm_contract_integrity_case_executes' 'backend/tests/security/test_adk_confirm_and_session_readonly_security.py' 'security regression case for confirm integrity'

require_pattern '^ADK_RUNTIME_STRATEGY_VALUES = \(' 'backend/app/core/config.py' 'runtime strategy enum single source in config'
require_pattern '"official_only"' 'backend/app/core/config.py' 'runtime strategy enum includes official_only'
require_pattern '"official_or_legacy"' 'backend/app/core/config.py' 'runtime strategy enum includes official_or_legacy'
require_pattern '"allow_legacy"' 'backend/app/core/config.py' 'runtime strategy enum includes allow_legacy'
require_pattern 'ADK_RUNTIME_STRATEGY_VALUES = tuple\(_CONFIG_ADK_RUNTIME_STRATEGY_VALUES\)' 'backend/app/services/gemini/agent/adk_runtime_contract.py' 'runtime contract reuses config enum source'
require_pattern 'test_runtime_strategy_enum_is_single_source_of_truth' 'backend/tests/test_adk_runtime_strategy_contract.py' 'runtime strategy single-source regression'
require_pattern 'ADK_STRATEGY_VIOLATION' 'backend/tests/security/test_adk_runtime_strategy_enum_tamper.py' 'runtime strategy enum tamper security regression'

require_pattern 'final_contents: List\[str\] = \[\]' 'backend/app/routers/ai/multi_agent.py' 'run-live keeps final event aggregation buffer'
require_pattern 'output_chunks: List\[str\] = \[\]' 'backend/app/routers/ai/multi_agent.py' 'run-live keeps chunk fallback aggregation buffer'
require_pattern 'long_running_seen: set\[str\] = set\(\)' 'backend/app/routers/ai/multi_agent.py' 'run-live deduplicates long_running_tool_ids'
require_pattern 'if final_contents:' 'backend/app/routers/ai/multi_agent.py' 'run-live final-first output selection'
require_pattern 'output_text = "\\n"\.join\(item for item in final_contents if item\)\.strip\(\)' 'backend/app/routers/ai/multi_agent.py' 'run-live joins final outputs before chunk fallback'
require_pattern 'run-live-final-first-and-deduplicate' 'backend/tests/test_adk_run_live_aggregation.py' 'run-live aggregation regression case for final-first dedupe'
require_pattern 'run-live-chunk-fallback-when-final-missing' 'backend/tests/test_adk_run_live_aggregation.py' 'run-live aggregation regression case for chunk fallback'
require_pattern 'assert response\["event_count"\] == len\(events\)' 'backend/tests/test_adk_run_live_aggregation.py' 'run-live response keeps event_count contract'

echo "[ok] ADK usability + accuracy contract checks passed"
