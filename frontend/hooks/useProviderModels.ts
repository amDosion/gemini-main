/**
 * `useProviderModels` — 拉取 multi-agent workflow 节点可用的 provider/model 列表。
 *
 * 1:1 抽离自 `PropertiesPanel.tsx` L206-245
 * （JIRA-frontend-view-decomposition.md P0 #1 Step 2）。
 *
 * 仅在选中节点为 `agent` 或 `tool` 类型时拉取 `/api/agents/available-models`，
 * 切换节点或类型时通过 `cancelled` 标志丢弃在途响应（防止 race 写脏 state）。
 */

import { useEffect, useState } from 'react';
import { Node } from 'reactflow';
import { CustomNodeData } from '../components/multiagent/CustomNode';
import { NodeType } from '../components/multiagent/nodeTypeConfigs';
import {
  ProviderModels,
  normalizeProviderModels,
} from '../components/multiagent/providerModelUtils';
import { getAuthHeaders } from '../services/apiClient';

export interface UseProviderModelsResult {
  providers: ProviderModels[];
  providersLoading: boolean;
}

export function useProviderModels(
  selectedNode: Node<CustomNodeData> | null,
  nodeType: NodeType
): UseProviderModelsResult {
  const [providers, setProviders] = useState<ProviderModels[]>([]);
  const [providersLoading, setProvidersLoading] = useState(false);

  useEffect(() => {
    if (!selectedNode || (nodeType !== 'agent' && nodeType !== 'tool')) {
      return;
    }
    let cancelled = false;

    const fetchProviders = async () => {
      setProvidersLoading(true);
      try {
        const res = await fetch('/api/agents/available-models', {
          headers: getAuthHeaders(),
        });
        if (!res.ok || cancelled) return;
        const data = await res.json();
        // res.json() 也是悬挂点：解析期间若已切换节点，丢弃在途响应，防止写脏 state。
        if (cancelled) return;
        setProviders(normalizeProviderModels(data));
      } catch {
        // 1:1 保留原行为：失败时静默；错误处理改善留待后续 ticket
      } finally {
        if (!cancelled) {
          setProvidersLoading(false);
        }
      }
    };

    fetchProviders();
    return () => {
      cancelled = true;
    };
  }, [nodeType, selectedNode?.id]);

  return {
    providers,
    providersLoading,
  };
}
