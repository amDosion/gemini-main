/**
 * Component Library Panel
 * 
 * Left sidebar displaying categorized, draggable node components
 * for the workflow editor with search and filter capabilities.
 */

import React, { useState, useMemo } from 'react';
import { Search, X } from 'lucide-react';
import { NodeType, nodeTypeConfigs } from './nodeTypeConfigs';

interface ComponentLibraryProps {
  onDragStart?: (event: React.DragEvent, nodeType: NodeType) => void;
}

// Node categories for organization
const nodeCategories = {
  basic: {
    title: '基础节点',
    description: '工作流的起点和终点',
    nodes: ['start', 'end'] as NodeType[],
  },
  operation: {
    title: '运维节点',
    description: '大模型和知识库操作',
    nodes: ['llm', 'knowledge', 'agent'] as NodeType[],
  },
  control: {
    title: '分支节点',
    description: '条件判断和流程合并',
    nodes: ['condition', 'merge'] as NodeType[],
  },
  execution: {
    title: '代码节点',
    description: '代码执行和 API 调用',
    nodes: ['code', 'api'] as NodeType[],
  },
};

export const ComponentLibrary: React.FC<ComponentLibraryProps> = ({ onDragStart }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const handleDragStart = (event: React.DragEvent, nodeType: NodeType) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
    
    // Call parent handler if provided
    onDragStart?.(event, nodeType);
  };

  // Filter nodes based on search query and selected category
  const filteredCategories = useMemo(() => {
    const query = searchQuery.toLowerCase().trim();
    
    return Object.entries(nodeCategories).reduce((acc, [key, category]) => {
      // Filter by selected category
      if (selectedCategory && key !== selectedCategory) {
        return acc;
      }

      // Filter nodes by search query
      const filteredNodes = category.nodes.filter((nodeType) => {
        if (!query) return true;
        
        const config = nodeTypeConfigs[nodeType];
        return (
          config.label.toLowerCase().includes(query) ||
          config.description.toLowerCase().includes(query) ||
          nodeType.toLowerCase().includes(query)
        );
      });

      // Only include category if it has matching nodes
      if (filteredNodes.length > 0) {
        acc[key] = {
          ...category,
          nodes: filteredNodes,
        };
      }

      return acc;
    }, {} as typeof nodeCategories);
  }, [searchQuery, selectedCategory]);

  const totalFilteredNodes = useMemo(() => {
    return Object.values(filteredCategories).reduce(
      (sum, category) => sum + category.nodes.length,
      0
    );
  }, [filteredCategories]);

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedCategory(null);
  };

  return (
    <div className="w-[280px] bg-white border-r border-gray-200 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-800">组件库</h2>
        <p className="text-xs text-gray-500 mt-1">拖拽节点到画布</p>
      </div>

      {/* Search Bar */}
      <div className="p-3 border-b border-gray-200 bg-gray-50">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="搜索节点..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="
              w-full pl-9 pr-8 py-2 
              text-sm border border-gray-300 rounded-lg
              focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
              bg-white
            "
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-gray-200 rounded"
            >
              <X className="w-3 h-3 text-gray-500" />
            </button>
          )}
        </div>
      </div>

      {/* Category Filter */}
      <div className="p-3 border-b border-gray-200 bg-white">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedCategory(null)}
            className={`
              px-3 py-1 text-xs rounded-full transition-colors
              ${!selectedCategory 
                ? 'bg-blue-500 text-white' 
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }
            `}
          >
            全部
          </button>
          {Object.entries(nodeCategories).map(([key, category]) => (
            <button
              key={key}
              onClick={() => setSelectedCategory(key)}
              className={`
                px-3 py-1 text-xs rounded-full transition-colors
                ${selectedCategory === key 
                  ? 'bg-blue-500 text-white' 
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }
              `}
            >
              {category.title}
            </button>
          ))}
        </div>
      </div>

      {/* Results Count */}
      {(searchQuery || selectedCategory) && (
        <div className="px-4 py-2 bg-blue-50 border-b border-blue-100 flex items-center justify-between">
          <span className="text-xs text-blue-700">
            找到 {totalFilteredNodes} 个节点
          </span>
          <button
            onClick={clearFilters}
            className="text-xs text-blue-600 hover:text-blue-800 underline"
          >
            清除筛选
          </button>
        </div>
      )}

      {/* Categories */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {Object.keys(filteredCategories).length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-gray-500">未找到匹配的节点</p>
            <button
              onClick={clearFilters}
              className="mt-2 text-xs text-blue-600 hover:text-blue-800 underline"
            >
              清除筛选
            </button>
          </div>
        ) : (
          Object.entries(filteredCategories).map(([key, category]) => (
            <div key={key} className="space-y-3">
              {/* Category Header */}
              <div>
                <h3 className="text-sm font-medium text-gray-700">{category.title}</h3>
                <p className="text-xs text-gray-400 mt-0.5">{category.description}</p>
              </div>

              {/* Node Cards */}
              <div className="space-y-2">
                {category.nodes.map((nodeType) => {
                  const config = nodeTypeConfigs[nodeType];
                  return (
                    <div
                      key={nodeType}
                      draggable
                      onDragStart={(e) => handleDragStart(e, nodeType)}
                      className="
                        flex items-center gap-3 p-3 
                        bg-gray-50 hover:bg-gray-100 
                        border border-gray-200 hover:border-gray-300
                        rounded-lg cursor-move
                        transition-all duration-150
                        active:scale-95 active:shadow-sm
                      "
                    >
                      {/* Icon */}
                      <div
                        className={`
                          w-10 h-10 ${config.iconColor} 
                          rounded flex items-center justify-center 
                          text-white text-lg flex-shrink-0
                        `}
                      >
                        {config.icon}
                      </div>

                      {/* Label and Description */}
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-800 truncate">
                          {config.label}
                        </div>
                        <div className="text-xs text-gray-500 truncate">
                          {config.description}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer Hint */}
      <div className="p-3 border-t border-gray-200 bg-gray-50">
        <p className="text-xs text-gray-500 text-center">
          💡 拖拽节点到画布开始编排
        </p>
      </div>
    </div>
  );
};

export default ComponentLibrary;
