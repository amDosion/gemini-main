/**
 * Custom Node Component for React Flow
 * 
 * Displays workflow nodes with:
 * - Colored icon and title
 * - Description text
 * - Visible connection points (blue dots)
 * - Multiple handles for condition/merge nodes
 * - Execution status and progress
 * - Agent information
 */

import React from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Clock, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { nodeTypeConfigs } from './nodeTypeConfigs';
import type { NodeStatus, WorkflowNodeData } from './types';

// Re-export for backward compatibility
export type CustomNodeData = WorkflowNodeData;

// Status configuration
const statusConfig: Record<NodeStatus, {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  color: string;
  bg: string;
  animate?: string;
}> = {
  pending: {
    icon: Clock,
    color: 'text-gray-400',
    bg: 'bg-gray-50'
  },
  running: {
    icon: Loader2,
    color: 'text-blue-500',
    bg: 'bg-blue-50',
    animate: 'animate-spin'
  },
  completed: {
    icon: CheckCircle2,
    color: 'text-green-500',
    bg: 'bg-green-50'
  },
  failed: {
    icon: XCircle,
    color: 'text-red-500',
    bg: 'bg-red-50'
  }
};

export const CustomNode: React.FC<NodeProps<CustomNodeData>> = ({ data, selected }) => {
  const config = nodeTypeConfigs[data.type];
  const status = data.status || 'pending';
  const statusInfo = statusConfig[status];
  const StatusIcon = statusInfo.icon;

  return (
    <div
      className={`
        w-[220px] bg-white rounded-lg border-2 shadow-md
        ${selected ? 'border-blue-500 shadow-lg' : 'border-gray-200'}
        transition-all hover:shadow-lg
      `}
    >
      {/* Node Header */}
      <div className="p-3 border-b border-gray-100">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {/* Colored Icon */}
            <span
              className={`w-8 h-8 ${config.iconColor} rounded flex items-center justify-center text-white text-lg`}
            >
              {config.icon}
            </span>
            {/* Node Title */}
            <span className="text-sm font-semibold text-gray-800">
              {data.label}
            </span>
          </div>
          {/* Status Icon */}
          <StatusIcon
            size={16}
            className={`${statusInfo.color} ${statusInfo.animate || ''}`}
          />
        </div>
        {/* Description */}
        <p className="text-xs text-gray-500">{data.description}</p>
      </div>

      {/* Node Body */}
      <div className="p-3">
        {/* Agent Information */}
        {data.agentName && (
          <div className="text-xs text-gray-600 mb-2">
            <span className="font-medium">智能体:</span> {data.agentName}
          </div>
        )}

        {/* Progress Bar */}
        {(status === 'running' || status === 'completed') && (
          <div className="mb-2">
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  status === 'completed' ? 'bg-green-500' : 'bg-blue-500'
                }`}
                style={{ width: `${status === 'completed' ? 100 : data.progress || 0}%` }}
              />
            </div>
            <div className="text-[10px] text-gray-500 mt-1">
              {status === 'completed' ? '100%' : `${Math.round(data.progress || 0)}%`}
            </div>
          </div>
        )}

        {/* Error Message */}
        {status === 'failed' && data.error && (
          <div className="p-2 bg-red-50 rounded text-[10px] text-red-600">
            {data.error.substring(0, 50)}...
          </div>
        )}
      </div>

      {/* Input Connection Points (Left) */}
      {config.defaultInputs === 1 && (
        <Handle
          type="target"
          position={Position.Left}
          className="w-3 h-3 !bg-blue-500 !border-2 !border-white"
          style={{ left: '-6px' }}
        />
      )}
      {config.defaultInputs === 2 && (
        <>
          <Handle
            type="target"
            position={Position.Left}
            id="input-1"
            className="w-3 h-3 !bg-blue-500 !border-2 !border-white"
            style={{ left: '-6px', top: '35%' }}
          />
          <Handle
            type="target"
            position={Position.Left}
            id="input-2"
            className="w-3 h-3 !bg-blue-500 !border-2 !border-white"
            style={{ left: '-6px', top: '65%' }}
          />
        </>
      )}

      {/* Output Connection Points (Right) */}
      {config.defaultOutputs === 1 && (
        <Handle
          type="source"
          position={Position.Right}
          className="w-3 h-3 !bg-blue-500 !border-2 !border-white"
          style={{ right: '-6px' }}
        />
      )}
      {config.defaultOutputs === 2 && (
        <>
          <Handle
            type="source"
            position={Position.Right}
            id="output-true"
            className="w-3 h-3 !bg-green-500 !border-2 !border-white"
            style={{ right: '-6px', top: '35%' }}
          />
          <Handle
            type="source"
            position={Position.Right}
            id="output-false"
            className="w-3 h-3 !bg-red-500 !border-2 !border-white"
            style={{ right: '-6px', top: '65%' }}
          />
        </>
      )}
      {/* Multiple outputs for parallel node */}
      {config.defaultOutputs > 2 && (
        <>
          {Array.from({ length: config.defaultOutputs }).map((_, i) => (
            <Handle
              key={`output-${i}`}
              type="source"
              position={Position.Right}
              id={`output-${i}`}
              className="w-3 h-3 !bg-blue-500 !border-2 !border-white"
              style={{ 
                right: '-6px', 
                top: `${((i + 1) / (config.defaultOutputs + 1)) * 100}%` 
              }}
            />
          ))}
        </>
      )}
    </div>
  );
};

export default CustomNode;
