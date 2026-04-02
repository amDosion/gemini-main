import { describe, expect, it } from 'vitest';

import {
  createInitialStageReplayState,
  stageReplayReducer,
} from './stageReplayReducer';
import type { StageReplayContext, StageReplayResult } from './stageReplayService';

const buildContext = (overrides: Partial<StageReplayContext> = {}): StageReplayContext => ({
  valid: true,
  message: 'ok',
  sessionId: 'session-1',
  timeline: [],
  parseErrors: [],
  anchors: [
    {
      id: 'anchor-blocked',
      stage: 'ingest',
      stageLabel: 'Ingest',
      status: 'completed',
      timestampMs: 1,
      timestampLabel: 't1',
      artifact: {
        artifactKey: 'sheet/ingest',
        artifactVersion: 1,
        artifactSessionId: 'session-1',
      },
      inputArtifact: null,
      invocationId: '',
      originalPayload: { foo: 'bar' },
      canReplay: false,
      blockedReason: 'blocked',
      sourcePath: '$.history[0]',
    },
    {
      id: 'anchor-ready',
      stage: 'profile',
      stageLabel: 'Profile',
      status: 'completed',
      timestampMs: 2,
      timestampLabel: 't2',
      artifact: {
        artifactKey: 'sheet/profile',
        artifactVersion: 1,
        artifactSessionId: 'session-1',
      },
      inputArtifact: {
        artifactKey: 'sheet/ingest',
        artifactVersion: 1,
        artifactSessionId: 'session-1',
      },
      invocationId: 'inv-1',
      originalPayload: { summary: { row_count: 2 } },
      canReplay: true,
      blockedReason: '',
      sourcePath: '$.history[1]',
    },
  ],
  ...overrides,
});

const buildReplayResult = (): StageReplayResult => ({
  anchor: buildContext().anchors[1],
  replayEnvelope: {
    protocolVersion: 'sheet-stage/v1',
    stage: 'profile',
    status: 'completed',
    sessionId: 'session-1',
    artifact: {
      artifactKey: 'sheet/profile',
      artifactVersion: 2,
      artifactSessionId: 'session-1',
    },
    inputArtifact: {
      artifactKey: 'sheet/ingest',
      artifactVersion: 1,
      artifactSessionId: 'session-1',
    },
    nextStage: 'query',
    payload: { summary: { row_count: 2 } },
    error: null,
    timeline: [],
    playbackRefs: [],
    precheckIssues: [],
    sourcePath: '$root',
    raw: {},
  },
  originalPayload: { summary: { row_count: 2 } },
  replayedPayload: { summary: { row_count: 2 } },
  diff: [],
  requestedAtMs: 1,
});

describe('stageReplayReducer', () => {
  it('hydrates valid context and picks first replayable anchor', () => {
    const prev = createInitialStageReplayState();
    const next = stageReplayReducer(prev, {
      type: 'hydrate_context',
      context: buildContext(),
    });

    expect(next.status).toBe('ready');
    expect(next.selectedAnchorId).toBe('anchor-ready');
    expect(next.errorMessage).toBe('');
    expect(next.result).toBeNull();
  });

  it('hydrates invalid context as snapshot_invalid', () => {
    const next = stageReplayReducer(createInitialStageReplayState(), {
      type: 'hydrate_context',
      context: buildContext({
        valid: false,
        message: 'invalid snapshot',
        anchors: [],
      }),
    });

    expect(next.status).toBe('snapshot_invalid');
    expect(next.errorMessage).toBe('invalid snapshot');
  });

  it('moves to failed when start replay is requested on blocked anchor', () => {
    const hydrated = stageReplayReducer(createInitialStageReplayState(), {
      type: 'hydrate_context',
      context: buildContext(),
    });
    const selectedBlocked = stageReplayReducer(hydrated, {
      type: 'select_anchor',
      anchorId: 'anchor-blocked',
    });

    const next = stageReplayReducer(selectedBlocked, { type: 'start_replay' });

    expect(next.status).toBe('failed');
    expect(next.errorMessage).toBe('blocked');
  });

  it('supports replay success only after replaying state', () => {
    const hydrated = stageReplayReducer(createInitialStageReplayState(), {
      type: 'hydrate_context',
      context: buildContext(),
    });
    const replaying = stageReplayReducer(hydrated, { type: 'start_replay' });
    expect(replaying.status).toBe('replaying');

    const result = buildReplayResult();
    const succeeded = stageReplayReducer(replaying, { type: 'replay_succeeded', result });
    expect(succeeded.status).toBe('succeeded');
    expect(succeeded.result).toEqual(result);

    const ignored = stageReplayReducer(hydrated, { type: 'replay_succeeded', result });
    expect(ignored.status).toBe('ready');
    expect(ignored.result).toBeNull();
  });

  it('clears feedback back to ready when context remains valid', () => {
    const hydrated = stageReplayReducer(createInitialStageReplayState(), {
      type: 'hydrate_context',
      context: buildContext(),
    });
    const failed = stageReplayReducer(hydrated, {
      type: 'replay_failed',
      errorMessage: 'boom',
    });
    expect(failed.status).toBe('failed');

    const cleared = stageReplayReducer(failed, { type: 'clear_feedback' });
    expect(cleared.status).toBe('ready');
    expect(cleared.errorMessage).toBe('');
    expect(cleared.result).toBeNull();
  });
});
