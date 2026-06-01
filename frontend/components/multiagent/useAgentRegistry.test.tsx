// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cacheManager, CACHE_DOMAINS } from '../../services/CacheManager';
import { clearPrivateMemoryCaches } from '../../services/privateClientCache';
import {
  scopedPrivateCacheKey,
  setPrivateCacheUserScope,
} from '../../services/privateCacheScope';
import type { AgentDef } from './types';
import { useAgentRegistry, __resetAgentRegistryCacheForTesting } from './useAgentRegistry';

interface AgentListFetchResult {
  agents: AgentDef[];
  count: number;
  activeCount: number;
  inactiveCount: number;
}

const { fetchAgentListMock, subscribeAgentRegistryUpdatedMock } = vi.hoisted(() => ({
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
    cleanup();
    fetchAgentListMock.mockReset();
    subscribeAgentRegistryUpdatedMock.mockReset();
    subscribeAgentRegistryUpdatedMock.mockReturnValue(() => {});
    __resetAgentRegistryCacheForTesting();
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
  });

  afterEach(() => {
    cleanup();
    __resetAgentRegistryCacheForTesting();
    cacheManager.clearAll();
    setPrivateCacheUserScope(null);
  });

  it('ignores stale response when a newer refresh resolves first', async () => {
    const first = createDeferred<AgentListFetchResult>();
    const second = createDeferred<AgentListFetchResult>();
    fetchAgentListMock.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);

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

  it('does not reuse agent list cache across private user scopes', async () => {
    setPrivateCacheUserScope('user-1');
    const userOneAgents = [buildAgent('agent-user-1', 'User 1 Agent')];
    fetchAgentListMock.mockResolvedValueOnce(buildResult(userOneAgents));

    const first = renderHook(() => useAgentRegistry());

    await waitFor(() => {
      expect(first.result.current.agents).toEqual(userOneAgents);
    });
    first.unmount();

    setPrivateCacheUserScope('user-2');
    const userTwoAgents = [buildAgent('agent-user-2', 'User 2 Agent')];
    fetchAgentListMock.mockResolvedValueOnce(buildResult(userTwoAgents));

    const second = renderHook(() => useAgentRegistry());

    await waitFor(() => {
      expect(second.result.current.agents).toEqual(userTwoAgents);
    });
    expect(fetchAgentListMock).toHaveBeenCalledTimes(2);
  });

  it('reloads mounted agent registry when private user scope changes', async () => {
    setPrivateCacheUserScope('user-1');
    const userOneAgents = [buildAgent('agent-user-1', 'User 1 Agent')];
    fetchAgentListMock.mockResolvedValueOnce(buildResult(userOneAgents));

    const hook = renderHook(() => useAgentRegistry());

    await waitFor(() => {
      expect(hook.result.current.agents).toEqual(userOneAgents);
    });

    const userTwoAgents = [buildAgent('agent-user-2', 'User 2 Agent')];
    fetchAgentListMock.mockResolvedValueOnce(buildResult(userTwoAgents));
    act(() => {
      setPrivateCacheUserScope('user-2');
    });

    await waitFor(() => {
      expect(hook.result.current.agents).toEqual(userTwoAgents);
    });
    expect(fetchAgentListMock).toHaveBeenCalledTimes(2);
  });

  it('does not repopulate agent cache when an in-flight request resolves after cache clear', async () => {
    setPrivateCacheUserScope('user-1');
    const staleRequest = createDeferred<AgentListFetchResult>();
    const currentRequest = createDeferred<AgentListFetchResult>();
    fetchAgentListMock
      .mockReturnValueOnce(staleRequest.promise)
      .mockReturnValueOnce(currentRequest.promise);

    const hook = renderHook(() => useAgentRegistry());

    await waitFor(() => {
      expect(fetchAgentListMock).toHaveBeenCalledTimes(1);
    });

    setPrivateCacheUserScope('user-2');
    clearPrivateMemoryCaches();
    await waitFor(() => {
      expect(fetchAgentListMock).toHaveBeenCalledTimes(2);
    });

    const lateAgents = [buildAgent('late-agent', 'Late Agent')];
    await act(async () => {
      staleRequest.resolve(buildResult(lateAgents));
      await staleRequest.promise;
    });

    expect(hook.result.current.agents).toEqual([]);
    expect(
      cacheManager.get<AgentDef[]>(
        scopedPrivateCacheKey(CACHE_DOMAINS.AGENT_REGISTRY, '0::', 'user-1')
      )
    ).toBeNull();

    const currentAgents = [buildAgent('current-agent', 'Current Agent')];
    await act(async () => {
      currentRequest.resolve(buildResult(currentAgents));
      await currentRequest.promise;
    });

    expect(hook.result.current.agents).toEqual(currentAgents);
    expect(hook.result.current.loading).toBe(false);
  });

  it('does not resolve stale refresh results after private user scope changes', async () => {
    setPrivateCacheUserScope('user-1');
    const staleRequest = createDeferred<AgentListFetchResult>();
    fetchAgentListMock.mockReturnValueOnce(staleRequest.promise);

    const hook = renderHook(() => useAgentRegistry({ autoLoad: false }));

    let refreshPromise!: Promise<AgentDef[]>;
    act(() => {
      refreshPromise = hook.result.current.refreshAgents();
    });
    await waitFor(() => {
      expect(fetchAgentListMock).toHaveBeenCalledTimes(1);
    });

    act(() => {
      setPrivateCacheUserScope('user-2');
    });

    const staleAgents = [buildAgent('stale-agent', 'Stale Agent')];
    await act(async () => {
      staleRequest.resolve(buildResult(staleAgents));
    });

    await expect(refreshPromise).resolves.toEqual([]);
    expect(hook.result.current.agents).toEqual([]);
    expect(
      cacheManager.get<AgentDef[]>(
        scopedPrivateCacheKey(CACHE_DOMAINS.AGENT_REGISTRY, '0::', 'user-1')
      )
    ).toBeNull();
  });
});
