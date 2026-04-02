#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const ROOT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const LOAD_PROFILE_SCRIPT = path.join(ROOT_DIR, 'scripts/perf/sheet_stage_replay_load.mjs');
const DOC_FILE = path.join(ROOT_DIR, 'docs/observability/sheet_stage_metrics.md');
const CI_FILE = path.join(ROOT_DIR, '.github/workflows/ci.yml');
const RUNTIME_STORE_FILE = path.join(ROOT_DIR, 'backend/app/services/agent/workflow_runtime_store.py');

function fail(message) {
  console.error(`[sheet-stage-metrics] ERROR: ${message}`);
  process.exit(1);
}

function ok(message) {
  console.log(`[sheet-stage-metrics] OK: ${message}`);
}

function parsePositiveInt(raw, label) {
  const numeric = Number(String(raw).trim());
  if (!Number.isInteger(numeric) || numeric <= 0) {
    fail(`${label} must be a positive integer`);
  }
  return numeric;
}

function parseArgs(argv) {
  const options = {
    ci: false,
    maxDurationMs: 120000,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = String(argv[index] || '').trim();
    if (!token) {
      continue;
    }
    if (token === '--ci') {
      options.ci = true;
      continue;
    }
    if (token === '--max-duration-ms') {
      const rawValue = argv[index + 1];
      if (rawValue === undefined) {
        fail('missing value for --max-duration-ms');
      }
      options.maxDurationMs = parsePositiveInt(rawValue, '--max-duration-ms');
      index += 1;
      continue;
    }
    fail(`unsupported option: ${token}`);
  }

  return options;
}

function requireFile(filePath, label) {
  if (!fs.existsSync(filePath)) {
    fail(`missing ${label}: ${filePath}`);
  }
  ok(`${label} exists`);
}

function requireText(filePath, requiredText, label) {
  const source = fs.readFileSync(filePath, 'utf8');
  if (!source.includes(requiredText)) {
    fail(`missing ${label}: ${requiredText} (${filePath})`);
  }
  ok(label);
}

function extractJsonReport(stdout) {
  const start = stdout.indexOf('{');
  const end = stdout.lastIndexOf('}');
  if (start < 0 || end < 0 || end < start) {
    fail('failed to parse sheet stage load profile JSON report');
  }
  const rawJson = stdout.slice(start, end + 1);
  try {
    return JSON.parse(rawJson);
  } catch (error) {
    fail(`invalid JSON report from load profile: ${String(error?.message || error)}`);
  }
}

function metricObject(container, key) {
  if (!container || typeof container !== 'object') {
    fail(`missing metrics container while resolving ${key}`);
  }
  const value = container[key];
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    fail(`missing metric object: ${key}`);
  }
  return value;
}

function metricNumber(container, key, label) {
  const value = container?.[key];
  if (!Number.isFinite(value) || Number(value) < 0) {
    fail(`invalid numeric metric for ${label}: ${String(value)}`);
  }
  return Number(value);
}

function validateReport(report, options) {
  const expectedMode = options.ci ? 'ci' : 'local';
  if (String(report?.mode || '') !== expectedMode) {
    fail(`unexpected mode from load profile: expected ${expectedMode}, got ${String(report?.mode || '')}`);
  }

  const metrics = report?.metrics;
  if (!metrics || typeof metrics !== 'object') {
    fail('missing metrics object in load profile report');
  }

  const stageLatency = metricObject(metrics, 'stage_latency_ms');
  metricNumber(stageLatency, 'p50', 'stage_latency_ms.p50');
  const stageLatencyP95 = metricNumber(stageLatency, 'p95', 'stage_latency_ms.p95');
  const stageLatencyMax = metricNumber(stageLatency, 'max', 'stage_latency_ms.max');

  const replayRecovery = metricObject(metrics, 'stage_replay_recovery_ms');
  const replayRecoveryCount = metricNumber(replayRecovery, 'count', 'stage_replay_recovery_ms.count');
  const replayRecoveryP95 = metricNumber(replayRecovery, 'p95', 'stage_replay_recovery_ms.p95');
  const replayRecoveryMax = metricNumber(replayRecovery, 'max', 'stage_replay_recovery_ms.max');

  const stageErrorCardinality = metricNumber(metrics, 'stage_error_cardinality', 'stage_error_cardinality');
  if (!Number.isInteger(stageErrorCardinality)) {
    fail(`stage_error_cardinality must be an integer, got ${stageErrorCardinality}`);
  }

  const errorCodes = metrics?.error_codes;
  if (!Array.isArray(errorCodes)) {
    fail('metrics.error_codes must be an array');
  }
  if (errorCodes.length !== stageErrorCardinality) {
    fail(`stage_error_cardinality mismatch: expected ${stageErrorCardinality}, got error_codes.length=${errorCodes.length}`);
  }

  const totalSamples = metricNumber(metrics, 'total_samples', 'total_samples');
  if (totalSamples <= 0) {
    fail('total_samples must be > 0');
  }

  if (!Array.isArray(report?.violations)) {
    fail('report.violations must be an array');
  }

  if (options.ci) {
    if (report.violations.length > 0) {
      fail(`load profile reported threshold violations: ${report.violations.join(' | ')}`);
    }

    const thresholds = report?.thresholds;
    if (!thresholds || typeof thresholds !== 'object') {
      fail('missing thresholds object in CI report');
    }

    const maxLatencyP95 = metricNumber(thresholds, 'stageLatencyP95MaxMs', 'thresholds.stageLatencyP95MaxMs');
    const maxLatency = metricNumber(thresholds, 'stageLatencyMaxMs', 'thresholds.stageLatencyMaxMs');
    const minRecoveryCount = metricNumber(thresholds, 'minRecoverySamples', 'thresholds.minRecoverySamples');
    const maxRecoveryP95 = metricNumber(
      thresholds,
      'stageReplayRecoveryP95MaxMs',
      'thresholds.stageReplayRecoveryP95MaxMs'
    );
    const maxRecovery = metricNumber(thresholds, 'stageReplayRecoveryMaxMs', 'thresholds.stageReplayRecoveryMaxMs');
    const maxErrorCardinality = metricNumber(
      thresholds,
      'stageErrorCardinalityMax',
      'thresholds.stageErrorCardinalityMax'
    );

    if (stageLatencyP95 > maxLatencyP95) {
      fail(`stage_latency_ms.p95=${stageLatencyP95} exceeds ${maxLatencyP95}`);
    }
    if (stageLatencyMax > maxLatency) {
      fail(`stage_latency_ms.max=${stageLatencyMax} exceeds ${maxLatency}`);
    }
    if (replayRecoveryCount < minRecoveryCount) {
      fail(`stage_replay_recovery_ms.count=${replayRecoveryCount} is below ${minRecoveryCount}`);
    }
    if (replayRecoveryP95 > maxRecoveryP95) {
      fail(`stage_replay_recovery_ms.p95=${replayRecoveryP95} exceeds ${maxRecoveryP95}`);
    }
    if (replayRecoveryMax > maxRecovery) {
      fail(`stage_replay_recovery_ms.max=${replayRecoveryMax} exceeds ${maxRecovery}`);
    }
    if (stageErrorCardinality > maxErrorCardinality) {
      fail(`stage_error_cardinality=${stageErrorCardinality} exceeds ${maxErrorCardinality}`);
    }
  }

  ok('load profile metrics contract passed');
}

function runLoadProfile(options) {
  const mode = options.ci ? 'ci' : 'local';
  const result = spawnSync(
    process.execPath,
    [LOAD_PROFILE_SCRIPT, '--mode', mode, '--max-duration-ms', String(options.maxDurationMs)],
    {
      cwd: ROOT_DIR,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  );

  if (result.error) {
    fail(`failed to launch load profile: ${String(result.error?.message || result.error)}`);
  }

  const stdout = String(result.stdout || '');
  const stderr = String(result.stderr || '');
  const report = extractJsonReport(stdout);

  if (result.status !== 0) {
    const details = [
      `exit_code=${String(result.status)}`,
      `stdout=${stdout.trim()}`,
      `stderr=${stderr.trim()}`,
    ]
      .filter(Boolean)
      .join('\n');
    fail(`sheet stage replay load profile failed:\n${details}`);
  }

  return report;
}

function main() {
  const options = parseArgs(process.argv.slice(2));

  requireFile(LOAD_PROFILE_SCRIPT, 'sheet_stage_replay load profile script');
  requireFile(DOC_FILE, 'sheet stage observability docs');
  requireFile(CI_FILE, 'CI workflow file');
  requireFile(RUNTIME_STORE_FILE, 'workflow runtime store file');

  requireText(DOC_FILE, 'sheet_stage_replay', 'docs mention sheet_stage_replay coverage');
  requireText(DOC_FILE, 'row_level_policy', 'docs mention row_level_policy coverage');
  requireText(DOC_FILE, 'stage_latency_ms', 'docs mention stage_latency_ms metric');
  requireText(DOC_FILE, 'stage_replay_recovery_ms', 'docs mention stage_replay_recovery_ms metric');
  requireText(DOC_FILE, 'stage_error_cardinality', 'docs mention stage_error_cardinality metric');

  requireText(CI_FILE, 'check_sheet_stage_advanced.sh', 'CI runs advanced sheet-stage gate script');
  requireText(CI_FILE, 'verify_sheet_stage_metrics.mjs --ci', 'CI runs metrics verifier in CI mode');
  requireText(CI_FILE, 'test_sheet_stage_persistence.py', 'CI runs BE-702 persistence tests');
  requireText(CI_FILE, 'test_sheet_row_level_policy.py', 'CI runs SE-702 row_level_policy tests');
  requireText(CI_FILE, 'test_sheet_stage_replay_matrix.py', 'CI runs QA-702 sheet_stage_replay matrix tests');
  requireText(CI_FILE, 'stageReplayReducer.test.ts', 'CI runs FE-702 reducer tests');
  requireText(CI_FILE, 'StageReplayPanel.test.tsx', 'CI runs FE-702 panel tests');
  requireText(CI_FILE, 'stage_latency_ms', 'CI contains stage_latency_ms gate marker');
  requireText(CI_FILE, 'stage_error_cardinality', 'CI contains stage_error_cardinality gate marker');

  requireText(RUNTIME_STORE_FILE, '_RUNTIME_PAYLOAD_UPDATED_AT_FIELD', 'runtime store payload timestamp marker exists');
  requireText(RUNTIME_STORE_FILE, 'async def get_payload(', 'runtime store get_payload API exists');
  requireText(RUNTIME_STORE_FILE, 'async def put_payload(', 'runtime store put_payload API exists');

  const report = runLoadProfile(options);
  validateReport(report, options);

  ok(`metrics verification completed mode=${options.ci ? 'ci' : 'local'}`);
}

main();
