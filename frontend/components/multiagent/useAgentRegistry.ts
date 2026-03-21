import React from 'react';
import type { AgentDef } from './types';
import { fetchAgentList, subscribeAgentRegistryUpdated } from './agentRegistryService';

interface UseAgentRegistryOptions {
  includeInactive?: boolean;
  search?: string;
  autoLoad?: boolean;
}

interface UseAgentRegistryResult {
  agents: AgentDef[];
  loading: boolean;
  error: string | null;
  refreshAgents: () => Promise<AgentDef[]>;
}

export const useAgentRegistry = (options: UseAgentRegistryOptions = {}): UseAgentRegistryResult => {
  const {
    includeInactive = false,
    search = '',
    autoLoad = true,
  } = options;
  const [agents, setAgents] = React.useState<AgentDef[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const mountedRef = React.useRef(true);
  const latestRequestIdRef = React.useRef(0);
  const activeControllerRef = React.useRef<AbortController | null>(null);

  React.useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      activeControllerRef.current?.abort();
    };
  }, []);

  const refreshAgents = React.useCallback(async (): Promise<AgentDef[]> => {
    const requestId = latestRequestIdRef.current + 1;
    latestRequestIdRef.current = requestId;
    activeControllerRef.current?.abort();
    const controller = new AbortController();
    activeControllerRef.current = controller;
    if (mountedRef.current) {
      setLoading(true);
      setError(null);
    }
    try {
      const result = await fetchAgentList({
        includeInactive,
        search,
        signal: controller.signal,
      });
      if (!mountedRef.current || controller.signal.aborted || requestId !== latestRequestIdRef.current) {
        return [];
      }
      if (mountedRef.current) {
        setAgents(result.agents);
        setError(null);
      }
      return result.agents;
    } catch (e) {
      if (!mountedRef.current || controller.signal.aborted || requestId !== latestRequestIdRef.current) {
        return [];
      }
      const message = e instanceof Error ? e.message : 'Failed to fetch agents';
      if (mountedRef.current) {
        setError(message);
      }
      return [];
    } finally {
      if (requestId === latestRequestIdRef.current) {
        activeControllerRef.current = null;
      }
      if (mountedRef.current && requestId === latestRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, [includeInactive, search]);

  React.useEffect(() => {
    if (!autoLoad) return;
    void refreshAgents();
  }, [autoLoad, refreshAgents]);

  React.useEffect(() => {
    if (!autoLoad) return;
    return subscribeAgentRegistryUpdated(() => {
      void refreshAgents();
    });
  }, [autoLoad, refreshAgents]);

  return {
    agents,
    loading,
    error,
    refreshAgents,
  };
};
