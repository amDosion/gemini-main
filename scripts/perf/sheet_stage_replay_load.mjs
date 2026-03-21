#!/usr/bin/env node
import process from 'node:process';
import { performance } from 'node:perf_hooks';

const CI_SEED = 70200031;
const STAGES = ['profile', 'query', 'export'];

const DEFAULTS = {
  mode: 'local',
  seed: CI_SEED,
  cycles: 40,
  concurrency: 8,
  maxDurationMs: 120000,
};

const CI_PROFILE = {
  cycles: 64,
  concurrency: 12,
  recoveryRate: {
    profile: 0.05,
    query: 0.12,
    export: 0.1,
  },
  hardErrorRate: {
    profile: 0.0,
    query: 0.0,
    export: 0.0,
  },
  stageLatencyBaseMs: {
    profile: 130,
    query: 170,
    export: 210,
  },
  stageLatencyJitterMs: {
    profile: 70,
    query: 85,
    export: 80,
  },
  replayRecoveryBaseMs: {
    profile: 240,
    query: 320,
    export: 380,
  },
  replayRecoveryJitterMs: {
    profile: 100,
    query: 130,
    export: 160,
  },
};

const CI_THRESHOLDS = {
  stageLatencyP95MaxMs: 360,
  stageLatencyMaxMs: 420,
  stageReplayRecoveryP95MaxMs: 560,
  stageReplayRecoveryMaxMs: 700,
  stageErrorCardinalityMax: 2,
  minRecoverySamples: 8,
};

const ERROR_CODES = {
  recovery: ['SHEET_STAGE_ARTIFACT_STALE'],
  hard: ['SHEET_STAGE_TRANSITION_INVALID'],
};

function parseCliArgs(argv) {
  const options = { ...DEFAULTS };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith('--')) {
      throw new Error(`unknown argument: ${token}`);
    }
    const key = token.slice(2);
    const value = argv[index + 1];
    if (value === undefined || value.startsWith('--')) {
      throw new Error(`missing value for --${key}`);
    }
    index += 1;
    if (key === 'mode') {
      options.mode = String(value).trim().toLowerCase();
      continue;
    }
    if (key === 'seed') {
      options.seed = parsePositiveInt(value, '--seed');
      continue;
    }
    if (key === 'cycles') {
      options.cycles = parsePositiveInt(value, '--cycles');
      continue;
    }
    if (key === 'concurrency') {
      options.concurrency = parsePositiveInt(value, '--concurrency');
      continue;
    }
    if (key === 'max-duration-ms') {
      options.maxDurationMs = parsePositiveInt(value, '--max-duration-ms');
      continue;
    }
    throw new Error(`unsupported option: --${key}`);
  }
  if (!['ci', 'local'].includes(options.mode)) {
    throw new Error(`invalid --mode value: ${options.mode} (expected ci|local)`);
  }
  return options;
}

function parsePositiveInt(raw, label) {
  const numeric = Number(String(raw).trim());
  if (!Number.isFinite(numeric) || numeric <= 0 || !Number.isInteger(numeric)) {
    throw new Error(`${label} must be a positive integer`);
  }
  return numeric;
}

function createDeterministicRandom(seed) {
  let state = seed >>> 0;
  if (state === 0) {
    state = 1;
  }
  return () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 0x100000000;
  };
}

function percentile(values, ratio) {
  if (!values.length) return 0;
  const sorted = [...values].sort((left, right) => left - right);
  const rank = Math.max(0, Math.min(sorted.length - 1, Math.ceil(sorted.length * ratio) - 1));
  return sorted[rank];
}

function roundMetric(value) {
  return Math.round(value * 100) / 100;
}

function buildProfile(options) {
  const mode = options.mode;
  if (mode === 'ci') {
    return {
      mode,
      seed: CI_SEED,
      cycles: CI_PROFILE.cycles,
      concurrency: CI_PROFILE.concurrency,
      recoveryRate: CI_PROFILE.recoveryRate,
      hardErrorRate: CI_PROFILE.hardErrorRate,
      stageLatencyBaseMs: CI_PROFILE.stageLatencyBaseMs,
      stageLatencyJitterMs: CI_PROFILE.stageLatencyJitterMs,
      replayRecoveryBaseMs: CI_PROFILE.replayRecoveryBaseMs,
      replayRecoveryJitterMs: CI_PROFILE.replayRecoveryJitterMs,
      thresholds: CI_THRESHOLDS,
      maxDurationMs: options.maxDurationMs,
    };
  }
  return {
    mode,
    seed: options.seed,
    cycles: options.cycles,
    concurrency: options.concurrency,
    recoveryRate: {
      profile: 0.04,
      query: 0.08,
      export: 0.06,
    },
    hardErrorRate: {
      profile: 0.0,
      query: 0.0,
      export: 0.0,
    },
    stageLatencyBaseMs: {
      profile: 140,
      query: 185,
      export: 225,
    },
    stageLatencyJitterMs: {
      profile: 80,
      query: 95,
      export: 85,
    },
    replayRecoveryBaseMs: {
      profile: 280,
      query: 350,
      export: 420,
    },
    replayRecoveryJitterMs: {
      profile: 130,
      query: 150,
      export: 170,
    },
    thresholds: {
      stageLatencyP95MaxMs: 420,
      stageLatencyMaxMs: 520,
      stageReplayRecoveryP95MaxMs: 700,
      stageReplayRecoveryMaxMs: 860,
      stageErrorCardinalityMax: 2,
      minRecoverySamples: 4,
    },
    maxDurationMs: options.maxDurationMs,
  };
}

function simulateLoad(profile) {
  const rand = createDeterministicRandom(profile.seed);
  const totalSamples = profile.cycles * profile.concurrency * STAGES.length;

  const stageLatencies = [];
  const replayRecoveryLatencies = [];
  const errorCodeSet = new Set();
  const perStage = {
    profile: { count: 0, failures: 0 },
    query: { count: 0, failures: 0 },
    export: { count: 0, failures: 0 },
  };

  for (let index = 0; index < totalSamples; index += 1) {
    const stage = STAGES[index % STAGES.length];
    const lanePenalty = Math.floor((index % profile.concurrency) / 3);
    const latencyBase = profile.stageLatencyBaseMs[stage];
    const latencyJitter = profile.stageLatencyJitterMs[stage];
    const latency = latencyBase + Math.floor(rand() * (latencyJitter + 1)) + lanePenalty;
    stageLatencies.push(latency);
    perStage[stage].count += 1;

    const shouldRecover = rand() < profile.recoveryRate[stage];
    const hardFailure = !shouldRecover && rand() < profile.hardErrorRate[stage];

    if (shouldRecover) {
      perStage[stage].failures += 1;
      const recoveryCode = ERROR_CODES.recovery[Math.floor(rand() * ERROR_CODES.recovery.length)];
      errorCodeSet.add(recoveryCode);
      const recoveryBase = profile.replayRecoveryBaseMs[stage];
      const recoveryJitter = profile.replayRecoveryJitterMs[stage];
      const replayRecoveryMs = recoveryBase + Math.floor(rand() * (recoveryJitter + 1));
      replayRecoveryLatencies.push(replayRecoveryMs);
    } else if (hardFailure) {
      perStage[stage].failures += 1;
      const hardErrorCode = ERROR_CODES.hard[Math.floor(rand() * ERROR_CODES.hard.length)];
      errorCodeSet.add(hardErrorCode);
    }
  }

  const stageLatencyP50 = percentile(stageLatencies, 0.5);
  const stageLatencyP95 = percentile(stageLatencies, 0.95);
  const stageLatencyMax = stageLatencies.length ? Math.max(...stageLatencies) : 0;
  const replayRecoveryP95 = percentile(replayRecoveryLatencies, 0.95);
  const replayRecoveryMax = replayRecoveryLatencies.length ? Math.max(...replayRecoveryLatencies) : 0;

  return {
    totalSamples,
    perStage,
    stageLatencyMs: {
      p50: roundMetric(stageLatencyP50),
      p95: roundMetric(stageLatencyP95),
      max: roundMetric(stageLatencyMax),
    },
    stageReplayRecoveryMs: {
      count: replayRecoveryLatencies.length,
      p95: roundMetric(replayRecoveryP95),
      max: roundMetric(replayRecoveryMax),
    },
    stageErrorCardinality: errorCodeSet.size,
    errorCodes: [...errorCodeSet].sort(),
  };
}

function evaluateMetrics(summary, profile, durationMs) {
  const thresholds = profile.thresholds;
  const violations = [];

  if (summary.stageLatencyMs.p95 > thresholds.stageLatencyP95MaxMs) {
    violations.push(
      `stage_latency_ms p95=${summary.stageLatencyMs.p95} exceeds ${thresholds.stageLatencyP95MaxMs}`
    );
  }
  if (summary.stageLatencyMs.max > thresholds.stageLatencyMaxMs) {
    violations.push(
      `stage_latency_ms max=${summary.stageLatencyMs.max} exceeds ${thresholds.stageLatencyMaxMs}`
    );
  }
  if (summary.stageReplayRecoveryMs.count < thresholds.minRecoverySamples) {
    violations.push(
      `stage_replay_recovery_ms count=${summary.stageReplayRecoveryMs.count} below ${thresholds.minRecoverySamples}`
    );
  }
  if (summary.stageReplayRecoveryMs.p95 > thresholds.stageReplayRecoveryP95MaxMs) {
    violations.push(
      `stage_replay_recovery_ms p95=${summary.stageReplayRecoveryMs.p95} exceeds ${thresholds.stageReplayRecoveryP95MaxMs}`
    );
  }
  if (summary.stageReplayRecoveryMs.max > thresholds.stageReplayRecoveryMaxMs) {
    violations.push(
      `stage_replay_recovery_ms max=${summary.stageReplayRecoveryMs.max} exceeds ${thresholds.stageReplayRecoveryMaxMs}`
    );
  }
  if (summary.stageErrorCardinality > thresholds.stageErrorCardinalityMax) {
    violations.push(
      `stage_error_cardinality=${summary.stageErrorCardinality} exceeds ${thresholds.stageErrorCardinalityMax}`
    );
  }
  if (durationMs > profile.maxDurationMs) {
    violations.push(
      `duration_ms=${roundMetric(durationMs)} exceeds ${profile.maxDurationMs}`
    );
  }

  return violations;
}

function main() {
  const startedAt = performance.now();
  let options;
  try {
    options = parseCliArgs(process.argv.slice(2));
  } catch (error) {
    console.error(`[sheet-stage-replay-load] ${String(error?.message || error)}`);
    process.exitCode = 1;
    return;
  }

  const profile = buildProfile(options);
  const summary = simulateLoad(profile);
  const durationMs = performance.now() - startedAt;
  const violations = evaluateMetrics(summary, profile, durationMs);

  const report = {
    mode: profile.mode,
    seed: profile.seed,
    cycles: profile.cycles,
    concurrency: profile.concurrency,
    durationMs: roundMetric(durationMs),
    metrics: {
      stage_latency_ms: summary.stageLatencyMs,
      stage_replay_recovery_ms: summary.stageReplayRecoveryMs,
      stage_error_cardinality: summary.stageErrorCardinality,
      error_codes: summary.errorCodes,
      total_samples: summary.totalSamples,
      per_stage: summary.perStage,
    },
    thresholds: profile.thresholds,
    violations,
  };

  console.log(`[sheet-stage-replay-load] mode=${profile.mode} seed=${profile.seed} samples=${summary.totalSamples}`);
  console.log(JSON.stringify(report, null, 2));

  if (violations.length > 0) {
    console.error('[sheet-stage-replay-load] metric gate failed (fail-closed)');
    process.exitCode = 1;
    return;
  }
  console.log('[sheet-stage-replay-load] metric gate passed');
}

main();
