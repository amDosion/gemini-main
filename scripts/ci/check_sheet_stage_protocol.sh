#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v rg >/dev/null 2>&1; then
  echo "[error] rg is required for check_sheet_stage_protocol.sh" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[error] python3 is required for check_sheet_stage_protocol.sh" >&2
  exit 1
fi

require_file() {
  local file="$1"
  local label="$2"
  if [[ -f "$file" ]]; then
    echo "[ok] $label"
    return 0
  fi
  echo "[error] missing file for $label: $file" >&2
  exit 1
}

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

require_literal() {
  local text="$1"
  local file="$2"
  local label="$3"
  if rg -n -F --max-count 1 "$text" "$file" >/dev/null; then
    echo "[ok] $label"
    return 0
  fi
  echo "[error] missing literal for $label: $text ($file)" >&2
  exit 1
}

echo "[check] Sheet stage protocol CI observability gates"

require_file "queue/adk_next_cycle_tasks.csv" "next-cycle queue exists"
require_file "backend/tests/test_sheet_stage_protocol.py" "backend stage protocol test file exists"
require_file "backend/tests/security/test_sheet_stage_protocol_security.py" "backend security stage protocol test file exists"
require_file "frontend/components/multiagent/sheetStageService.test.ts" "frontend stage protocol test file exists"
require_file ".github/workflows/ci.yml" "ci workflow exists"

python3 scripts/ci/validate_adk_next_cycle_queue.py queue/adk_next_cycle_tasks.csv

require_pattern '^BE-701,Implement sheet stage protocol v1 backend,backend,' 'queue/adk_next_cycle_tasks.csv' 'BE-701 row present'
require_pattern '^QA-701,Regression matrix for sheet stage protocol v1,qa,' 'queue/adk_next_cycle_tasks.csv' 'QA-701 row present'
require_pattern '^OP-701,CI observability gates for staged sheet workflow,devops,' 'queue/adk_next_cycle_tasks.csv' 'OP-701 row present'
require_literal '.github/workflows/ci.yml;scripts/ci/check_sheet_stage_protocol.sh' 'queue/adk_next_cycle_tasks.csv' 'OP-701 required files pin CI + protocol checker'
require_literal 'backend/tests/test_sheet_stage_protocol.py;backend/tests/security/test_sheet_stage_protocol_security.py;frontend/components/multiagent/sheetStageService.test.ts' 'queue/adk_next_cycle_tasks.csv' 'QA-701 regression matrix pins BE/SE/FE stage tests'

require_pattern '^def test_sheet_stage_protocol_happy_path_flow' 'backend/tests/test_sheet_stage_protocol.py' 'backend validates staged happy-path transition flow'
require_literal 'assert ingest["protocol_version"] == "sheet-stage/v1"' 'backend/tests/test_sheet_stage_protocol.py' 'backend validates protocol_version in envelope'
require_literal 'assert [str(item.get("stage") or "") for item in history] == [' 'backend/tests/test_sheet_stage_protocol.py' 'backend validates deterministic stage history progression'
require_literal 'SHEET_STAGE_INVALID_REQUEST' 'backend/tests/test_sheet_stage_protocol.py' 'backend fail-closed artifact mismatch code is asserted'

require_pattern '^def test_sheet_stage_security_rejects_cross_session_artifact_ref_fail_closed' 'backend/tests/security/test_sheet_stage_protocol_security.py' 'security test covers cross-session rejection'
require_literal 'SHEET_STAGE_ARTIFACT_FORBIDDEN' 'backend/tests/security/test_sheet_stage_protocol_security.py' 'security test covers cross-tenant forbidden rejection'
require_literal 'SHEET_STAGE_ARTIFACT_STALE' 'backend/tests/security/test_sheet_stage_protocol_security.py' 'security test covers stale artifact fail-closed rejection'
require_literal 'SHEET_STAGE_TRANSITION_INVALID' 'backend/tests/security/test_sheet_stage_protocol_security.py' 'security test covers stage downgrade/replay rejection'
require_literal 'assert detail["stage"] == stage' 'backend/tests/security/test_sheet_stage_protocol_security.py' 'security test asserts stage field for observability'
require_literal 'assert detail["session_id"] == session_id' 'backend/tests/security/test_sheet_stage_protocol_security.py' 'security test asserts session_id field for observability'

require_literal "it('fails closed with parse errors when candidate envelope is malformed'" 'frontend/components/multiagent/sheetStageService.test.ts' 'frontend parser fail-closed malformed-envelope behavior is covered'
require_literal "item.message.includes('session_id is required')" 'frontend/components/multiagent/sheetStageService.test.ts' 'frontend parser surfaces session binding parse error'
require_literal "item.message.includes('artifact_session_id is required')" 'frontend/components/multiagent/sheetStageService.test.ts' 'frontend parser surfaces artifact session binding parse error'
require_literal "it('keeps failed envelope visible and exposes backend error payload'" 'frontend/components/multiagent/sheetStageService.test.ts' 'frontend preserves failed envelope observability payload'

if rg -n --max-count 1 '"timestamp_ms": int\(time\.time\(\) \* 1000\)' 'backend/app/routers/ai/multi_agent.py' >/dev/null \
  || rg -n --max-count 1 '"timestamp_ms": now_ms' 'backend/app/services/agent/adk_artifact_service.py' >/dev/null; then
  echo "[ok] backend stage history emits timestamp_ms observability field"
else
  echo '[error] missing timestamp_ms observability marker in known sheet-stage paths' >&2
  exit 1
fi
require_literal '[Multi-Agent API] Sheet stage protocol failed' 'backend/app/routers/ai/multi_agent.py' 'backend stage protocol failure log line is present'

require_literal 'check_sheet_stage_protocol.sh' '.github/workflows/ci.yml' 'ci runs sheet-stage protocol static gate script'
require_literal 'test_sheet_stage_protocol.py' '.github/workflows/ci.yml' 'ci runs backend sheet-stage protocol tests'
require_literal 'test_sheet_stage_protocol_security.py' '.github/workflows/ci.yml' 'ci runs security sheet-stage protocol tests'
require_literal 'sheetStageService.test.ts' '.github/workflows/ci.yml' 'ci runs frontend sheet-stage protocol tests'

echo "[ok] Sheet stage protocol CI observability gates passed"
