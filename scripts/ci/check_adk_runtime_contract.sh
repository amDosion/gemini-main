#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v rg >/dev/null 2>&1; then
  echo "[error] rg is required for check_adk_runtime_contract.sh" >&2
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

forbid_pattern() {
  local pattern="$1"
  local file="$2"
  local label="$3"
  if rg -n --max-count 1 "$pattern" "$file" >/dev/null; then
    echo "[error] forbidden pattern matched for $label: $pattern ($file)" >&2
    exit 1
  fi
  echo "[ok] $label"
}

echo "[check] ADK strict runtime contract (no implicit fallback/degrade)"

require_pattern 'error_code": "ADK_RUNTIME_UNAVAILABLE"' 'backend/app/services/gemini/agent/adk_runner.py' 'runner fail-closed runtime unavailable error'
forbid_pattern 'fallback\s*[:=]\s*True' 'backend/app/services/gemini/agent/adk_runner.py' 'runner does not emit fallback=true payloads'

require_pattern 'ORCHESTRATOR_NO_DEGRADE' 'backend/app/services/gemini/agent/orchestrator.py' 'orchestrator strict no-degrade guard'

require_pattern 'ADK_RUNTIME_UNAVAILABLE' 'backend/app/routers/ai/multi_agent.py' 'orchestration runtime unavailable code'
require_pattern 'ADK_STRATEGY_VIOLATION' 'backend/app/routers/ai/multi_agent.py' 'orchestration strategy violation code'
require_pattern 'ADK_FALLBACK_FORBIDDEN' 'backend/app/routers/ai/multi_agent.py' 'orchestration fallback forbidden code'
require_pattern 'if runtime_strategy == "allow_legacy" and fallback_allowed:' 'backend/app/routers/ai/multi_agent.py' 'legacy path is explicit policy-gated'

require_pattern 'ADK_RUNTIME_UNAVAILABLE' 'frontend/components/multiagent/adkSessionService.ts' 'frontend handles runtime unavailable'
require_pattern 'ADK_FALLBACK_FORBIDDEN' 'frontend/components/multiagent/adkSessionService.ts' 'frontend handles fallback forbidden'
require_pattern 'ADK_STRATEGY_VIOLATION' 'frontend/components/multiagent/adkSessionService.ts' 'frontend handles strategy violation'

require_pattern '"fallback" not in event' 'backend/tests/test_adk_runner_strict_runtime.py' 'runner strict runtime test forbids fallback payload'
require_pattern 'ORCHESTRATOR_NO_DEGRADE' 'backend/tests/test_adk_orchestrator_no_degrade.py' 'orchestrator no-degrade test assertions'
require_pattern 'response_signature' 'backend/tests/test_adk_result_accuracy_signals.py' 'accuracy signal signature assertions'
require_pattern 'ADK_FALLBACK_FORBIDDEN' 'backend/tests/security/test_adk_runtime_no_fallback.py' 'security no-fallback test assertions'
require_pattern 'ADK_FALLBACK_FORBIDDEN' 'frontend/components/multiagent/adkSessionService.test.ts' 'frontend runtime error mapping test assertions'

echo "[ok] ADK strict runtime contract checks passed"
