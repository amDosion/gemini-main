import { describe, expect, it } from 'vitest';
import type { ExecutionStatus } from '../../multiagent/types';
import { executionStreamReducer } from './executionStreamReducer';

const buildExecutionStatus = (overrides: Partial<ExecutionStatus> = {}): ExecutionStatus => ({
  executionId: 'exec-reducer-test',
  finalStatus: 'running',
  finalResult: undefined,
  finalError: undefined,
  completedAt: undefined,
  logs: [],
  nodeStatuses: {},
  nodeProgress: {},
  nodeResults: {},
  nodeErrors: {},
  nodeRuntimes: {},
  runtimeHints: [],
  ...overrides,
});

describe('executionStreamReducer', () => {
  it('preserves preview urls from previous state when completed payload omits them', () => {
    const prev = buildExecutionStatus({
      resultPreviewImageUrls: ['/api/temp-images/image-1'],
      resultPreviewAudioUrls: ['/api/temp-images/audio-1'],
      resultPreviewVideoUrls: ['/api/temp-images/video-1'],
    });

    const next = executionStreamReducer(prev, {
      type: 'apply_completed',
      payload: {
        status: 'completed',
        result: { text: 'done' },
      },
      now: 123456,
    });

    expect(next?.resultPreviewImageUrls).toEqual(['/api/temp-images/image-1']);
    expect(next?.resultPreviewAudioUrls).toEqual(['/api/temp-images/audio-1']);
    expect(next?.resultPreviewVideoUrls).toEqual(['/api/temp-images/video-1']);
  });

  it('hydrates preview urls from snapshot payload when present', () => {
    const prev = buildExecutionStatus();

    const next = executionStreamReducer(prev, {
      type: 'apply_snapshot',
      snapshot: {
        status: 'running',
        resultPreviewImageUrls: ['/api/temp-images/image-2'],
        resultPreviewAudioUrls: ['/api/temp-images/audio-2'],
        resultPreviewVideoUrls: ['/api/temp-images/video-2'],
      },
    });

    expect(next?.resultPreviewImageUrls).toEqual(['/api/temp-images/image-2']);
    expect(next?.resultPreviewAudioUrls).toEqual(['/api/temp-images/audio-2']);
    expect(next?.resultPreviewVideoUrls).toEqual(['/api/temp-images/video-2']);
  });
});
