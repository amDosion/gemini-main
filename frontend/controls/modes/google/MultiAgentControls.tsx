import React from 'react';
import { Network } from 'lucide-react';
import { MultiAgentControlsProps } from '../../types';

export const MultiAgentControls: React.FC<MultiAgentControlsProps> = ({
  enableMultiAgent,
  setEnableMultiAgent,
}) => {
  return (
    <div className="flex items-center gap-1 bg-slate-900/60 p-1 rounded-full border border-slate-700/50 backdrop-blur-md overflow-x-auto max-w-full custom-scrollbar shadow-sm">
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium text-slate-400">
        <Network size={13} strokeWidth={2.5} />
        <span>Multi-Agent 工作流编排</span>
      </div>
      <div className="text-xs text-slate-500 px-2">
        在工作流编辑器中配置节点和连接
      </div>
    </div>
  );
};

export default MultiAgentControls;
