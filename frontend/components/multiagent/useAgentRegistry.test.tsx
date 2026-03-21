// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AgentDef } from './types';
import { useAgentRegistry } from './useAgentRegistry';

interface AgentListFetchResult {
  agents: AgentDef[];
  count: number;
  activeCount: number;
  inactiveCount: number;
}

const {
  fetchAgentListMock,
  subscribeAgentRegistryUpdatedMock,
} = vi.hoisted(() => ({
  fetchAgentListMock: vi.fn(),
  subscribeAgentRegistryUpdatedMock: vi.fn(),
}));

vi.mock('./agentRegistryService', () => ({
  fetchAgentList: fetchAgentListMock,
  subscribeAgentRegistryUpdated: subscribeAgentRegistryUpdatedMock,
}));

const buildAgent = (id: string, name: string): AgentDef => ({
  id,
  name,
  description: '',
  agentType: 'custom',
  providerId: 'openai',
  modelId: 'gpt-4.1',
  systemPrompt: '',
  temperature: 0.7,
  maxTokens: 4096,
  icon: 'bot',
  color: '#14b8a6',
  status: 'active',
});

const buildResult = (agents: AgentDef[]): AgentListFetchResult => ({
  agents,
  count: agents.length,
  activeCount: agents.filter((agent) => agent.status === 'active').length,
  inactiveCount: agents.filter((agent) => agent.status === 'inactive').length,
});

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('useAgentRegistry', () => {
  beforeEach(() => {
    fetchAgentListMock.mockReset();
    subscribeAgentRegistryUpdatedMock.mockReset();
    subscribeAgentRegistryUpdatedMock.mockReturnValue(() => {});
  });

  it('ignores stale response when a newer refresh resolves first', async () => {
    const first = createDeferred<AgentListFetchResult>();
    const second = createDeferred<AgentListFetchResult>();
    fetchAgentListMock
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);

    const { result } = renderHook(() => useAgentRegistry());
    await waitFor(() => {
      expect(fetchAgentListMock).toHaveBeenCalledTimes(1);
    });

    let secondRefreshPromise!: Promise<AgentDef[]>;
    act(() => {
      secondRefreshPromise = result.current.refreshAgents();
    });
    await waitFor(() => {
      expect(fetchAgentListMock).toHaveBeenCalledTimes(2);
      expect(result.current.loading).toBe(true);
    });

    const latestAgents = [buildAgent('new-agent', 'Latest Agent')];
    await act(async () => {
      second.resolve(buildResult(latestAgents));
      await secondRefreshPromise;
    });

    expect(result.current.agents).toEqual(latestAgents);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();

    await act(async () => {
      first.resolve(buildResult([buildAgent('old-agent', 'Old Agent')]));
      await first.promise;
    });

    expect(result.current.agents).toEqual(latestAgents);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('clears error on a new refresh and resets loading after success', async () => {
    const agent = buildAgent('agent-1', 'Agent 1');
    fetchAgentListMock
      .mockRejectedValueOnce(new Error('network failed'))
      .mockResolvedValueOnce(buildResult([agent]));

    const { result } = renderHook(() => useAgentRegistry({ autoLoad: false }));

    let failedRefreshPromise!: Promise<AgentDef[]>;
    act(() => {
      failedRefreshPromise = result.current.refreshAgents();
    });
    expect(result.current.loading).toBe(true);
    expect(result.current.error).toBeNull();

    await act(async () => {
      await failedRefreshPromise;
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe('network failed');
    expect(result.current.agents).toEqual([]);

    let successRefreshPromise!: Promise<AgentDef[]>;
    act(() => {
      successRefreshPromise = result.current.refreshAgents();
    });
    expect(result.current.loading).toBe(true);
    expect(result.current.error).toBeNull();

    await act(async () => {
      await successRefreshPromise;
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.agents).toEqual([agent]);
  });
});
