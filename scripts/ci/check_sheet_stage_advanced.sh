#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

for required_cmd in rg python3 node; do
  if ! command -v "$required_cmd" >/dev/null 2>&1; then
    echo "[error] $required_cmd is required for check_sheet_stage_advanced.sh" >&2
    exit 1
  fi
done

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

echo "[check] Advanced sheet stage CI + observability gates"

require_file "queue/adk_sheet_advanced_cycle_tasks.csv" "advanced-cycle queue exists"
require_file ".github/workflows/ci.yml" "ci workflow exists"
require_file "scripts/ci/check_sheet_stage_advanced.sh" "advanced gate script exists"
require_file "scripts/observability/verify_sheet_stage_metrics.mjs" "metrics verifier script exists"
require_file "scripts/perf/sheet_stage_replay_load.mjs" "sheet stage replay load profile script exists"
require_file "docs/testing/sheet_stage_replay_matrix.md" "qa replay matrix docs exist"
require_file "docs/observability/sheet_stage_metrics.md" "sheet stage observability docs exist"
require_file "backend/app/services/agent/workflow_runtime_store.py" "runtime store file exists"

require_file "backend/tests/test_sheet_stage_persistence.py" "BE-702 persistence tests exist"
require_file "backend/tests/test_sheet_session_resume.py" "BE-702 session resume tests exist"
require_file "backend/tests/test_sheet_artifact_lineage_query.py" "BE-702 lineage tests exist"
require_file "backend/tests/security/test_sheet_row_level_policy.py" "SE-702 row-level policy tests exist"
require_file "backend/tests/security/test_sheet_export_constraints.py" "SE-702 export constraints tests exist"
require_file "backend/tests/security/test_sheet_policy_audit_chain.py" "SE-702 policy audit-chain tests exist"
require_file "backend/tests/test_sheet_stage_replay_matrix.py" "QA-702 replay matrix tests exist"
require_file "backend/tests/test_sheet_stage_replay_run_config_matrix.py" "QA-702 run-config matrix tests exist"
require_file "frontend/components/multiagent/stageReplayReducer.test.ts" "FE-702 reducer tests exist"
require_file "frontend/components/multiagent/StageReplayPanel.test.tsx" "FE-702 panel tests exist"

require_pattern '^BE-702,Implement stage persistence resumable sessions and lineage query,backend,' 'queue/adk_sheet_advanced_cycle_tasks.csv' 'BE-702 queue row present'
require_pattern '^SE-702,Enforce row-level policy hooks and export constraints,security,' 'queue/adk_sheet_advanced_cycle_tasks.csv' 'SE-702 queue row present'
require_pattern '^QA-702,Deterministic matrix and load profile for stage replay,qa,' 'queue/adk_sheet_advanced_cycle_tasks.csv' 'QA-702 queue row present'
require_pattern '^FE-702,Deliver historical session stage replay UX,frontend,' 'queue/adk_sheet_advanced_cycle_tasks.csv' 'FE-702 queue row present'
require_pattern '^OP-702,Add CI gates and stage observability metrics,devops,' 'queue/adk_sheet_advanced_cycle_tasks.csv' 'OP-702 queue row present'
require_literal '.github/workflows/ci.yml;scripts/ci/check_sheet_stage_advanced.sh;scripts/observability/verify_sheet_stage_metrics.mjs;docs/observability/sheet_stage_metrics.md;backend/app/services/agent/workflow_runtime_store.py' 'queue/adk_sheet_advanced_cycle_tasks.csv' 'OP-702 required files pin CI + metrics gate assets'

require_literal 'def test_sheet_stage_persists_session_and_artifacts_with_deterministic_runtime_keys' 'backend/tests/test_sheet_stage_persistence.py' 'BE-702 deterministic runtime key persistence coverage'
require_literal 'assert session_key == f"sheet-stage:session:{session_id}"' 'backend/tests/test_sheet_stage_persistence.py' 'BE-702 session key contract assertion'
require_literal 'def test_sheet_session_resume_honors_session_and_invocation_binding' 'backend/tests/test_sheet_session_resume.py' 'BE-702 session+invocation resume contract coverage'
require_literal 'SHEET_STAGE_SESSION_BINDING_MISMATCH' 'backend/tests/test_sheet_session_resume.py' 'BE-702 fail-closed session binding mismatch coverage'
require_literal 'def test_sheet_artifact_lineage_query_returns_parent_child_and_version_chain' 'backend/tests/test_sheet_artifact_lineage_query.py' 'BE-702 lineage parent/child/version chain coverage'
require_literal 'SHEET_STAGE_LINEAGE_NOT_FOUND' 'backend/tests/test_sheet_artifact_lineage_query.py' 'BE-702 missing lineage fail-closed coverage'

require_literal 'def test_row_level_before_after_hooks_filter_rows_and_emit_deterministic_chain' 'backend/tests/security/test_sheet_row_level_policy.py' 'SE-702 row_level_policy before/after deterministic chain coverage'
require_literal 'policy_audit_chain is required' 'backend/tests/security/test_sheet_row_level_policy.py' 'SE-702 missing audit chain fail-closed coverage'
require_literal 'def test_export_constraint_rejects_sensitive_fields_fail_closed' 'backend/tests/security/test_sheet_export_constraints.py' 'SE-702 export constraint sensitive-field fail-closed coverage'
require_literal 'def test_export_constraint_requires_audit_chain_evidence' 'backend/tests/security/test_sheet_export_constraints.py' 'SE-702 export constraint audit evidence coverage'
require_literal 'def _assert_chain_deterministic' 'backend/tests/security/test_sheet_policy_audit_chain.py' 'SE-702 policy audit chain deterministic validation helper coverage'

require_literal 'def test_sheet_stage_replay_consistency_matrix' 'backend/tests/test_sheet_stage_replay_matrix.py' 'QA-702 sheet_stage_replay consistency matrix coverage'
require_literal 'def test_sheet_stage_replay_recovery_rejects_stale_input_artifact_refs' 'backend/tests/test_sheet_stage_replay_matrix.py' 'QA-702 stale replay recovery fail-closed coverage'
require_literal 'SHEET_STAGE_ARTIFACT_STALE' 'backend/tests/test_sheet_stage_replay_matrix.py' 'QA-702 stale artifact error-code coverage'
require_literal 'def test_sheet_stage_replay_run_config_accept_matrix' 'backend/tests/test_sheet_stage_replay_run_config_matrix.py' 'QA-702 run_config accept matrix coverage'
require_literal 'def test_sheet_stage_replay_run_config_reject_matrix' 'backend/tests/test_sheet_stage_replay_run_config_matrix.py' 'QA-702 run_config reject matrix coverage'
require_literal 'def test_sheet_stage_replay_state_delta_contract_is_explicit_in_run_path' 'backend/tests/test_sheet_stage_replay_run_config_matrix.py' 'QA-702 state_delta explicit boundary coverage'

require_literal "it('hydrates invalid context as snapshot_invalid'" 'frontend/components/multiagent/stageReplayReducer.test.ts' 'FE-702 reducer snapshot invalid fail-closed coverage'
require_literal "it('moves to failed when start replay is requested on blocked anchor'" 'frontend/components/multiagent/stageReplayReducer.test.ts' 'FE-702 reducer blocked-anchor fail-closed coverage'
require_literal "[UI-M1] shows fail-closed messaging when snapshot context is invalid" 'frontend/components/multiagent/StageReplayPanel.test.tsx' 'FE-702 panel invalid snapshot fail-closed coverage'
require_literal "[UI-M3] keeps replay disabled for blocked anchor and does not issue replay request" 'frontend/components/multiagent/StageReplayPanel.test.tsx' 'FE-702 panel blocked anchor replay guard coverage'

require_literal 'stage_latency_ms' 'scripts/perf/sheet_stage_replay_load.mjs' 'load profile emits stage_latency_ms metric'
require_literal 'stage_replay_recovery_ms' 'scripts/perf/sheet_stage_replay_load.mjs' 'load profile emits stage_replay_recovery_ms metric'
require_literal 'stage_error_cardinality' 'scripts/perf/sheet_stage_replay_load.mjs' 'load profile emits stage_error_cardinality metric'

require_literal 'sheet_stage_replay' 'docs/observability/sheet_stage_metrics.md' 'observability docs mention sheet_stage_replay scope'
require_literal 'row_level_policy' 'docs/observability/sheet_stage_metrics.md' 'observability docs mention row_level_policy coverage'
require_literal 'stage_latency_ms' 'docs/observability/sheet_stage_metrics.md' 'observability docs mention stage_latency_ms metric'
require_literal 'stage_replay_recovery_ms' 'docs/observability/sheet_stage_metrics.md' 'observability docs mention stage_replay_recovery_ms metric'
require_literal 'stage_error_cardinality' 'docs/observability/sheet_stage_metrics.md' 'observability docs mention stage_error_cardinality metric'

require_literal 'check_sheet_stage_advanced.sh' '.github/workflows/ci.yml' 'CI runs advanced sheet-stage gate script'
require_literal 'verify_sheet_stage_metrics.mjs --ci' '.github/workflows/ci.yml' 'CI runs metrics verifier in CI mode'
require_literal 'test_sheet_stage_persistence.py' '.github/workflows/ci.yml' 'CI runs BE-702 persistence tests'
require_literal 'test_sheet_session_resume.py' '.github/workflows/ci.yml' 'CI runs BE-702 session resume tests'
require_literal 'test_sheet_artifact_lineage_query.py' '.github/workflows/ci.yml' 'CI runs BE-702 lineage tests'
require_literal 'test_sheet_row_level_policy.py' '.github/workflows/ci.yml' 'CI runs SE-702 row_level_policy tests'
require_literal 'test_sheet_export_constraints.py' '.github/workflows/ci.yml' 'CI runs SE-702 export constraints tests'
require_literal 'test_sheet_policy_audit_chain.py' '.github/workflows/ci.yml' 'CI runs SE-702 audit-chain tests'
require_literal 'test_sheet_stage_replay_matrix.py' '.github/workflows/ci.yml' 'CI runs QA-702 replay matrix tests'
require_literal 'test_sheet_stage_replay_run_config_matrix.py' '.github/workflows/ci.yml' 'CI runs QA-702 run-config matrix tests'
require_literal 'stageReplayReducer.test.ts' '.github/workflows/ci.yml' 'CI runs FE-702 reducer tests'
require_literal 'StageReplayPanel.test.tsx' '.github/workflows/ci.yml' 'CI runs FE-702 panel tests'
require_literal 'sheet_stage_replay_load.mjs --mode ci --max-duration-ms 120000' '.github/workflows/ci.yml' 'CI runs deterministic replay load profile'
require_literal 'stage_latency_ms' '.github/workflows/ci.yml' 'CI includes stage_latency_ms hard-gate marker'
require_literal 'stage_error_cardinality' '.github/workflows/ci.yml' 'CI includes stage_error_cardinality hard-gate marker'

node scripts/observability/verify_sheet_stage_metrics.mjs --ci

echo "[ok] Advanced sheet stage CI + observability gates passed"
