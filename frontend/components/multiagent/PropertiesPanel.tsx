/**
 * Properties Panel Component
 * 
 * Right sidebar for editing selected node properties:
 * - Label and description editing
 * - Agent selector (for agent nodes)
 * - Execution status display
 * - Result/error display
 * - Retry button for failed nodes
 */

import React, { useState, useEffect } from 'react';
import { Node } from 'reactflow';
import { X, RefreshCw, CheckCircle2, XCircle, Clock, Loader2 } from 'lucide-react';
import { CustomNodeData } from './CustomNode';
import { nodeTypeConfigs } from './nodeTypeConfigs';
import type { NodeStatus } from './types';

interface PropertiesPanelProps {
  selectedNode: Node<CustomNodeData> | null;
  onClose: () => void;
  onUpdateNode: (nodeId: string, updates: Partial<CustomNodeData>) => void;
  onRetry?: (nodeId: string) => void;
}

interface Agent {
  id: string;
  name: string;
  description: string;
  tools: string[];
}

// Status display configuration
const statusDisplayConfig: Record<NodeStatus, {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  color: string;
  bgColor: string;
}> = {
  pending: {
    icon: Clock,
    label: '等待执行',
    color: 'text-gray-600',
    bgColor: 'bg-gray-100'
  },
  running: {
    icon: Loader2,
    label: '执行中',
    color: 'text-blue-600',
    bgColor: 'bg-blue-100'
  },
  completed: {
    icon: CheckCircle2,
    label: '已完成',
    color: 'text-green-600',
    bgColor: 'bg-green-100'
  },
  failed: {
    icon: XCircle,
    label: '执行失败',
    color: 'text-red-600',
    bgColor: 'bg-red-100'
  }
};

export const PropertiesPanel: React.FC<PropertiesPanelProps> = ({
  selectedNode,
  onClose,
  onUpdateNode,
  onRetry
}) => {
  const [label, setLabel] = useState('');
  const [description, setDescription] = useState('');
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(false);

  // Load node data when selection changes
  useEffect(() => {
    if (selectedNode) {
      setLabel(selectedNode.data.label || '');
      setDescription(selectedNode.data.description || '');
      setSelectedAgentId(selectedNode.data.agentId || '');
    }
  }, [selectedNode]);

  // Fetch agents list for agent nodes
  useEffect(() => {
    if (selectedNode?.data.type === 'agent') {
      fetchAgents();
    }
  }, [selectedNode?.data.type]);

  const fetchAgents = async () => {
    setLoadingAgents(true);
    try {
      const response = await fetch('/api/multi-agent/agents');
      if (response.ok) {
        const data = await response.json();
        setAgents(data.agents || []);
      }
    } catch (error) {
      console.error('Failed to fetch agents:', error);
    } finally {
      setLoadingAgents(false);
    }
  };

  const handleLabelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newLabel = e.target.value;
    setLabel(newLabel);
    if (selectedNode) {
      onUpdateNode(selectedNode.id, { label: newLabel });
    }
  };

  const handleDescriptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newDescription = e.target.value;
    setDescription(newDescription);
    if (selectedNode) {
      onUpdateNode(selectedNode.id, { description: newDescription });
    }
  };

  const handleAgentChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const agentId = e.target.value;
    setSelectedAgentId(agentId);
    
    if (selectedNode) {
      const agent = agents.find(a => a.id === agentId);
      onUpdateNode(selectedNode.id, {
        agentId,
        agentName: agent?.name,
        tools: agent?.tools
      });
    }
  };

  const handleRetry = () => {
    if (selectedNode && onRetry) {
      onRetry(selectedNode.id);
    }
  };

  if (!selectedNode) {
    return null;
  }

  const config = nodeTypeConfigs[selectedNode.data.type];
  const status = selectedNode.data.status || 'pending';
  const statusDisplay = statusDisplayConfig[status];
  const StatusIcon = statusDisplay.icon;

  return (
    <div className="w-[320px] bg-white border-l border-gray-200 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-800">节点属性</h3>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded transition-colors"
          aria-label="关闭属性面板"
        >
          <X size={20} className="text-gray-500" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Node Type Display */}
        <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
          <span className={`w-10 h-10 ${config.iconColor} rounded flex items-center justify-center text-white text-xl`}>
            {config.icon}
          </span>
          <div>
            <div className="text-sm font-semibold text-gray-800">{config.label}</div>
            <div className="text-xs text-gray-500">{config.category}</div>
          </div>
        </div>

        {/* Label Input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            节点名称
          </label>
          <input
            type="text"
            value={label}
            onChange={handleLabelChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            placeholder="输入节点名称"
          />
        </div>

        {/* Description Input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            节点描述
          </label>
          <textarea
            value={description}
            onChange={handleDescriptionChange}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            placeholder="输入节点描述"
          />
        </div>

        {/* Agent Selector (only for agent nodes) */}
        {selectedNode.data.type === 'agent' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              选择智能体
            </label>
            {loadingAgents ? (
              <div className="flex items-center justify-center py-3 text-sm text-gray-500">
                <Loader2 size={16} className="animate-spin mr-2" />
                加载中...
              </div>
            ) : (
              <select
                value={selectedAgentId}
                onChange={handleAgentChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">请选择智能体</option>
                {agents.map(agent => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
            )}
            {selectedAgentId && selectedNode.data.agentName && (
              <div className="mt-2 p-2 bg-blue-50 rounded text-xs text-gray-600">
                <div className="font-medium text-blue-700 mb-1">
                  {selectedNode.data.agentName}
                </div>
                {selectedNode.data.tools && selectedNode.data.tools.length > 0 && (
                  <div className="text-gray-500">
                    工具: {selectedNode.data.tools.join(', ')}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Execution Status */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            执行状态
          </label>
          <div className={`flex items-center gap-2 p-3 ${statusDisplay.bgColor} rounded-lg`}>
            <StatusIcon 
              size={20} 
              className={`${statusDisplay.color} ${status === 'running' ? 'animate-spin' : ''}`}
            />
            <span className={`text-sm font-medium ${statusDisplay.color}`}>
              {statusDisplay.label}
            </span>
          </div>

          {/* Progress Bar (for running status) */}
          {status === 'running' && selectedNode.data.progress !== undefined && (
            <div className="mt-2">
              <div className="flex justify-between text-xs text-gray-600 mb-1">
                <span>进度</span>
                <span>{selectedNode.data.progress}%</span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${selectedNode.data.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Execution Time */}
          {(selectedNode.data.startTime || selectedNode.data.endTime) && (
            <div className="mt-2 text-xs text-gray-500 space-y-1">
              {selectedNode.data.startTime && (
                <div>
                  开始时间: {new Date(selectedNode.data.startTime).toLocaleString()}
                </div>
              )}
              {selectedNode.data.endTime && (
                <div>
                  结束时间: {new Date(selectedNode.data.endTime).toLocaleString()}
                </div>
              )}
              {selectedNode.data.startTime && selectedNode.data.endTime && (
                <div className="font-medium text-gray-600">
                  耗时: {((selectedNode.data.endTime - selectedNode.data.startTime) / 1000).toFixed(2)}秒
                </div>
              )}
            </div>
          )}
        </div>

        {/* Result Display (for completed status) */}
        {status === 'completed' && selectedNode.data.result && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              执行结果
            </label>
            <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
              <pre className="text-xs text-gray-700 whitespace-pre-wrap break-words max-h-[200px] overflow-y-auto">
                {typeof selectedNode.data.result === 'string'
                  ? selectedNode.data.result
                  : JSON.stringify(selectedNode.data.result, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {/* Error Display (for failed status) */}
        {status === 'failed' && selectedNode.data.error && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              错误信息
            </label>
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
              <pre className="text-xs text-red-700 whitespace-pre-wrap break-words">
                {selectedNode.data.error}
              </pre>
            </div>
            {/* Retry Button */}
            {onRetry && (
              <button
                onClick={handleRetry}
                className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
              >
                <RefreshCw size={16} />
                重试执行
              </button>
            )}
          </div>
        )}

        {/* Node ID (for debugging) */}
        <div className="pt-4 border-t border-gray-200">
          <div className="text-xs text-gray-400">
            节点 ID: {selectedNode.id}
          </div>
        </div>
      </div>
    </div>
  );
};
