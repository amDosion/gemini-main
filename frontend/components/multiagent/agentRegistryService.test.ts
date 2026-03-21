import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../services/http', () => ({
  requestJson: vi.fn(),
}));

import { requestJson } from '../../services/http';
import { createEmptyAgentTaskCounts, fetchAgentList } from './agentRegistryService';

const requestJsonMock = vi.mocked(requestJson);

describe('agentRegistryService', () => {
  beforeEach(() => {
    requestJsonMock.mockReset();
  });

  it('forwards status/task_type to backend and normalizes task counts', async () => {
    requestJsonMock.mockResolvedValue({
      agents: [
        {
          id: 'agent-video',
          name: 'Video Agent',
          providerId: 'google',
          modelId: 'veo-3.1-generate-preview',
          systemPrompt: '',
          temperature: 0.7,
          maxTokens: 4096,
          icon: '🎬',
          color: '#6366f1',
          status: 'active',
          agentCard: {
            defaults: {
              defaultTaskType: 'video-gen',
            },
          },
        },
      ],
      count: 1,
      active_count: 7,
      inactive_count: 2,
      task_counts: {
        all: 4,
        chat: 1,
        video_gen: 2,
        audio_gen: 1,
      },
    });

    const result = await fetchAgentList({
      search: 'veo',
      status: 'active',
      taskType: 'video-gen',
    });

    const [url] = requestJsonMock.mock.calls[0] as [string];
    const parsedUrl = new URL(url, 'http://localhost');

    expect(parsedUrl.pathname).toBe('/api/agents');
    expect(parsedUrl.searchParams.get('search')).toBe('veo');
    expect(parsedUrl.searchParams.get('status')).toBe('active');
    expect(parsedUrl.searchParams.get('task_type')).toBe('video-gen');

    expect(result.count).toBe(1);
    expect(result.activeCount).toBe(7);
    expect(result.inactiveCount).toBe(2);
    expect(result.taskCounts.all).toBe(4);
    expect(result.taskCounts['video-gen']).toBe(2);
    expect(result.taskCounts['audio-gen']).toBe(1);
  });

  it('falls back to empty task counts when backend omits them', async () => {
    requestJsonMock.mockResolvedValue({
      agents: [],
      count: 0,
      active_count: 0,
      inactive_count: 0,
    });

    const result = await fetchAgentList();

    expect(result.taskCounts).toEqual(createEmptyAgentTaskCounts());
  });

  it('normalizes runtime metadata and exposes runtime session capability', async () => {
    requestJsonMock.mockResolvedValue({
      agents: [
        {
          id: 'agent-runtime',
          name: 'Runtime Agent',
          providerId: 'google',
          modelId: 'gemini-2.5-flash',
          systemPrompt: '',
          temperature: 0.7,
          maxTokens: 4096,
          icon: '🤖',
          color: '#14b8a6',
          status: 'active',
          source: {
            kind: 'seed',
            label: '官方 Seed',
            isSystem: true,
          },
          runtime: {
            kind: 'google-adk',
            label: 'Google ADK',
            supportsSessions: true,
            supportsLiveRun: true,
            supportsMemory: true,
            supportsOfficialOrchestration: true,
          },
        },
      ],
    });

    const result = await fetchAgentList();

    expect(result.agents[0]?.runtime).toEqual(expect.objectContaining({
      kind: 'google-adk',
      label: 'Google ADK',
      supportsSessions: true,
      supportsLiveRun: true,
      supportsMemory: true,
      supportsOfficialOrchestration: true,
    }));
    expect(result.agents[0]?.source).toEqual(expect.objectContaining({
      kind: 'seed',
      label: '官方 Seed',
      isSystem: true,
    }));
    expect(result.agents[0]?.supportsRuntimeSessions).toBe(true);
  });

  it('keeps legacy google-adk agents runtime-capable when backend metadata is absent', async () => {
    requestJsonMock.mockResolvedValue({
      agents: [
        {
          id: 'legacy-adk',
          name: 'Legacy ADK Agent',
          agentType: 'adk',
          providerId: 'google',
          modelId: 'gemini-2.5-flash',
          systemPrompt: '',
          temperature: 0.7,
          maxTokens: 4096,
          icon: '🤖',
          color: '#14b8a6',
          status: 'active',
        },
      ],
    });

    const result = await fetchAgentList();

    expect(result.agents[0]?.runtime?.kind).toBe('google-adk');
    expect(result.agents[0]?.supportsRuntimeSessions).toBe(true);
  });
});
