// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

vi.mock('./stageReplayService', async () => {
  const actual = await vi.importActual<typeof import('./stageReplayService')>('./stageReplayService');
  return {
    ...actual,
    extractStageReplayContext: vi.fn(),
    replayStageFromAnchor: vi.fn(),
  };
});

import { StageReplayPanel } from './StageReplayPanel';
import * as stageReplayService from './stageReplayService';
import type { StageReplayContext, StageReplayResult } from './stageReplayService';

const extractContextMock = vi.mocked(stageReplayService.extractStageReplayContext);
const replayStageMock = vi.mocked(stageReplayService.replayStageFromAnchor);

const buildContext = (overrides: Partial<StageReplayContext> = {}): StageReplayContext => ({
  valid: true,
  message: 'ready',
  sessionId: 'session-1',
  parseErrors: [],
  timeline: [
    {
      id: 'timeline-1',
      stage: 'profile',
      status: 'completed',
      artifact: {
        artifactKey: 'sheet/profile',
        artifactVersion: 1,
        artifactSessionId: 'session-1',
      },
      timestampMs: 1,
      sourcePath: '$.timeline[0]',
      source: 'history',
      raw: {},
    },
  ],
  anchors: [
    {
      id: 'anchor-1',
      stage: 'profile',
      stageLabel: 'Profile',
      status: 'completed',
      timestampMs: 1,
      timestampLabel: 't1',
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
      sourcePath: '$.timeline[0]',
    },
  ],
  ...overrides,
});

const buildReplayResult = (): StageReplayResult => ({
  anchor: buildContext().anchors[0],
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
    payload: { summary: { row_count: 2 }, columns: ['a'] },
    error: null,
    timeline: [],
    playbackRefs: [],
    precheckIssues: [],
    sourcePath: '$root',
    raw: {},
  },
  originalPayload: { summary: { row_count: 2 } },
  replayedPayload: { summary: { row_count: 2 }, columns: ['a'] },
  diff: [
    {
      path: '$.columns',
      change: 'added',
      originalPreview: '<undefined>',
      replayedPreview: '["a"]',
    },
  ],
  requestedAtMs: 1,
});

const buildBlockedAnchorContext = (): StageReplayContext => {
  const base = buildContext();
  return {
    ...base,
    anchors: [
      ...base.anchors,
      {
        ...base.anchors[0],
        id: 'anchor-blocked',
        stage: 'query',
        stageLabel: 'Query',
        artifact: {
          artifactKey: 'sheet/query',
          artifactVersion: 1,
          artifactSessionId: 'session-1',
        },
        inputArtifact: {
          artifactKey: 'sheet/profile',
          artifactVersion: 1,
          artifactSessionId: 'session-1',
        },
        originalPayload: { answer: 'ok' },
        canReplay: false,
        blockedReason: 'query 阶段缺少 query 字段，无法安全回放。',
      },
    ],
  };
};

describe('StageReplayPanel', () => {
  beforeEach(() => {
    extractContextMock.mockReset();
    replayStageMock.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('[UI-M1] shows fail-closed messaging when snapshot context is invalid', async () => {
    extractContextMock.mockReturnValue(
      buildContext({
        valid: false,
        message: 'broken snapshot',
        anchors: [],
        timeline: [],
        parseErrors: [
          {
            sourcePath: '$root.session_id',
            message: 'session_id is required',
          },
        ],
      })
    );

    render(
      <StageReplayPanel
        sessionId="session-1"
        sessionSnapshot={{}}
      />
    );

    expect(await screen.findByText('回放已被禁用（fail-closed）')).toBeInTheDocument();
    expect(screen.getAllByText('broken snapshot').length).toBeGreaterThan(0);
    expect(screen.getByText(/session_id is required/)).toBeInTheDocument();
    const runReplayButton = screen.getByRole('button', { name: '执行 Stage 回放' });
    expect(runReplayButton).toBeDisabled();
    fireEvent.click(runReplayButton);
    expect(replayStageMock).not.toHaveBeenCalled();
    expect(screen.getByTestId('stage-replay-status')).toHaveTextContent('快照无效');
  });

  it('[UI-M2] replays selected anchor and renders diff view on success', async () => {
    const context = buildContext();
    extractContextMock.mockReturnValue(context);
    replayStageMock.mockResolvedValue(buildReplayResult());
    const onReplayCompleted = vi.fn();

    render(
      <StageReplayPanel
        sessionId="session-1"
        sessionSnapshot={{ foo: 'bar' }}
        onReplayCompleted={onReplayCompleted}
      />
    );

    await screen.findByLabelText('Replay anchor');
    fireEvent.click(screen.getByRole('button', { name: '执行 Stage 回放' }));

    await waitFor(() => {
      expect(replayStageMock).toHaveBeenCalled();
    });

    expect(replayStageMock).toHaveBeenCalledWith(context, 'anchor-1', expect.any(AbortSignal));
    expect(onReplayCompleted).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('回放完成')).toBeInTheDocument();
    expect(screen.getByText('$.columns')).toBeInTheDocument();
    expect(screen.getByTestId('stage-replay-status')).toHaveTextContent('回放成功');
  });

  it('[UI-M3] keeps replay disabled for blocked anchor and does not issue replay request', async () => {
    const context = buildBlockedAnchorContext();
    extractContextMock.mockReturnValue(context);
    replayStageMock.mockResolvedValue(buildReplayResult());

    render(
      <StageReplayPanel
        sessionId="session-1"
        sessionSnapshot={{ foo: 'bar' }}
      />
    );

    const anchorSelect = await screen.findByLabelText('Replay anchor');
    fireEvent.change(anchorSelect, {
      target: { value: 'anchor-blocked' },
    });

    expect(screen.getAllByText('query 阶段缺少 query 字段，无法安全回放。').length).toBeGreaterThan(0);
    const replayButton = screen.getByRole('button', { name: '执行 Stage 回放' });
    expect(replayButton).toBeDisabled();
    fireEvent.click(replayButton);
    expect(replayStageMock).not.toHaveBeenCalled();
  });

  it('[UI-M4] surfaces replay failures with explicit status', async () => {
    const context = buildContext();
    extractContextMock.mockReturnValue(context);
    replayStageMock.mockRejectedValue(new Error('replay exploded'));

    render(
      <StageReplayPanel
        sessionId="session-1"
        sessionSnapshot={{ foo: 'bar' }}
      />
    );

    await screen.findByRole('button', { name: '执行 Stage 回放' });
    fireEvent.click(screen.getByRole('button', { name: '执行 Stage 回放' }));

    await waitFor(() => {
      expect(screen.getByText('replay exploded')).toBeInTheDocument();
    });
    expect(screen.getByTestId('stage-replay-status')).toHaveTextContent('回放失败');
  });
});
