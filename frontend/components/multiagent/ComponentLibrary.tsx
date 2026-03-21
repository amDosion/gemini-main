/**
 * Component Library Panel (Dark Theme, Compact)
 */

import React, { useState, useMemo } from 'react';
import { ChevronLeft, ChevronRight, Search, X } from 'lucide-react';
import { NodeType, nodeTypeConfigs } from './nodeTypeConfigs';

interface ComponentLibraryProps {
  onDragStart?: (event: React.DragEvent, nodeType: NodeType, payload?: Record<string, any>) => void;
}

const nodeCategories: Array<{ key: string; title: string; nodes: NodeType[] }> = [
  {
    key: 'flow',
    title: '流程控制',
    nodes: ['start', 'end', 'input_text', 'input_image', 'input_video', 'input_audio', 'input_file', 'condition', 'merge', 'loop'] as NodeType[],
  },
  { key: 'agent', title: '智能体', nodes: ['agent', 'tool', 'human'] as NodeType[] },
  { key: 'orchestration', title: '编排模式', nodes: ['router', 'parallel'] as NodeType[] },
];

export const ComponentLibrary: React.FC<ComponentLibraryProps> = ({ onDragStart }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isCollapsed, setIsCollapsed] = useState(false);

  const handleDragStart = (event: React.DragEvent, nodeType: NodeType, payload?: Record<string, any>) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    if (payload) {
      event.dataTransfer.setData('application/reactflow-node-payload', JSON.stringify(payload));
    }
    event.dataTransfer.effectAllowed = 'move';
    onDragStart?.(event, nodeType, payload);
  };

  const filteredNodeCategories = useMemo(() => {
    const query = searchQuery.toLowerCase().trim();
    return nodeCategories.reduce((acc, category) => {
      const filtered = category.nodes.filter((nodeType) => {
        if (!query) return true;
        const config = nodeTypeConfigs[nodeType];
        return config.label.toLowerCase().includes(query) || config.description.toLowerCase().includes(query);
      });
      if (filtered.length > 0) acc.push({ ...category, nodes: filtered });
      return acc;
    }, [] as Array<{ key: string; title: string; nodes: NodeType[] }>);
  }, [searchQuery]);

  if (isCollapsed) {
    return (
      <div className="absolute left-3 top-3 z-20">
        <button
          type="button"
          onClick={() => setIsCollapsed(false)}
          className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-900/95 text-slate-300 shadow-lg shadow-black/25 backdrop-blur transition-colors hover:border-teal-500/50 hover:bg-slate-800 hover:text-teal-300"
          aria-label="展开组件库"
          title="展开组件库"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="w-[220px] bg-slate-900 border-r border-slate-800 flex flex-col h-full overflow-hidden transition-[width] duration-200 ease-out">
      <div className="p-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="shrink-0 text-xs font-semibold text-slate-400">组件库</div>
          <div className="relative min-w-0 flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
            <input
              type="text"
              placeholder="搜索..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-7 py-1.5 text-xs bg-slate-800 border border-slate-700 rounded-lg text-slate-300 placeholder-slate-600 focus:outline-none focus:border-teal-500/50"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 hover:bg-slate-700 rounded"
                aria-label="清空组件搜索"
                title="清空搜索"
              >
                <X className="w-3 h-3 text-slate-500" />
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => setIsCollapsed(true)}
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-slate-700 bg-slate-800 text-slate-400 transition-colors hover:border-teal-500/40 hover:bg-slate-700 hover:text-teal-300"
            aria-label="收起组件库"
            title="收起组件库"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2.5 space-y-4">
        {filteredNodeCategories.map((category) => (
          <div key={category.key}>
            <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5 px-1">{category.title}</div>
            <div className="space-y-1">
              {category.nodes.map((nodeType) => {
                const config = nodeTypeConfigs[nodeType];
                return (
                  <div
                    key={nodeType}
                    draggable
                    onDragStart={(e) => handleDragStart(e, nodeType)}
                    className="flex items-center gap-2.5 px-2.5 py-2 bg-slate-800/50 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 rounded-lg cursor-grab transition-all active:scale-95 active:cursor-grabbing"
                  >
                    <div className={`w-7 h-7 ${config.iconColor} rounded-md flex items-center justify-center text-white text-sm flex-shrink-0`}>
                      {config.icon}
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-slate-300 truncate">{config.label}</div>
                      <div className="text-[10px] text-slate-600 truncate">{config.description}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="p-2.5 border-t border-slate-800">
        <p className="text-[10px] text-slate-600 text-center">拖拽节点到画布</p>
      </div>
    </div>
  );
};

export default ComponentLibrary;
