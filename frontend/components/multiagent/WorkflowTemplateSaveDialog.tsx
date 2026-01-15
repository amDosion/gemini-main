/**
 * Workflow Template Save Dialog Component
 * 
 * Modal dialog for saving current workflow as a template:
 * - Template name and description input
 * - Category selection
 * - Tags input
 * - Save to API
 */

import React, { useState } from 'react';
import { X, Save, Loader2 } from 'lucide-react';
import { Node, Edge } from 'reactflow';
import { CustomNodeData } from './CustomNode';
import { WorkflowTemplate } from './WorkflowTemplateSelector';

interface WorkflowTemplateSaveDialogProps {
  isOpen: boolean;
  onClose: () => void;
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
  onSaveSuccess?: (template: WorkflowTemplate) => void;
}

const PREDEFINED_CATEGORIES = [
  '数据处理',
  '内容生成',
  '分析报告',
  '自动化任务',
  '客户服务',
  '其他'
];

export const WorkflowTemplateSaveDialog: React.FC<WorkflowTemplateSaveDialogProps> = ({
  isOpen,
  onClose,
  nodes,
  edges,
  onSaveSuccess
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState(PREDEFINED_CATEGORIES[0]);
  const [customCategory, setCustomCategory] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!name.trim()) {
      setError('请输入模板名称');
      return;
    }

    if (!description.trim()) {
      setError('请输入模板描述');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const finalCategory = category === '其他' && customCategory.trim()
        ? customCategory.trim()
        : category;

      const tags = tagsInput
        .split(',')
        .map(tag => tag.trim())
        .filter(tag => tag.length > 0);

      const template: Omit<WorkflowTemplate, 'id' | 'createdAt' | 'updatedAt'> = {
        name: name.trim(),
        description: description.trim(),
        category: finalCategory,
        tags,
        config: {
          nodes: nodes.map(node => ({
            ...node,
            // Remove execution state before saving
            data: {
              ...node.data,
              status: undefined,
              progress: undefined,
              result: undefined,
              error: undefined,
              startTime: undefined,
              endTime: undefined
            }
          })),
          edges
        }
      };

      const response = await fetch('/api/multi-agent/workflows/templates', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(template)
      });

      if (!response.ok) {
        throw new Error('Failed to save template');
      }

      const savedTemplate: WorkflowTemplate = await response.json();
      
      if (onSaveSuccess) {
        onSaveSuccess(savedTemplate);
      }

      // Reset form and close
      resetForm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  };

  const resetForm = () => {
    setName('');
    setDescription('');
    setCategory(PREDEFINED_CATEGORIES[0]);
    setCustomCategory('');
    setTagsInput('');
    setError(null);
  };

  const handleClose = () => {
    if (!saving) {
      resetForm();
      onClose();
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-[600px] max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-800">保存为模板</h2>
          <button
            onClick={handleClose}
            disabled={saving}
            className="p-1 hover:bg-gray-100 rounded transition-colors disabled:opacity-50"
            aria-label="关闭"
          >
            <X size={20} className="text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Error Message */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Template Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              模板名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：客户服务工作流"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={saving}
            />
          </div>

          {/* Template Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              模板描述 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述这个工作流模板的用途和功能..."
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              disabled={saving}
            />
          </div>

          {/* Category Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              模板分类
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={saving}
            >
              {PREDEFINED_CATEGORIES.map(cat => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          {/* Custom Category (if "其他" is selected) */}
          {category === '其他' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                自定义分类
              </label>
              <input
                type="text"
                value={customCategory}
                onChange={(e) => setCustomCategory(e.target.value)}
                placeholder="输入自定义分类名称"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={saving}
              />
            </div>
          )}

          {/* Tags Input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              标签（可选）
            </label>
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="用逗号分隔多个标签，例如：AI, 自动化, 客服"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={saving}
            />
            <p className="mt-1 text-xs text-gray-500">
              标签可以帮助其他用户更容易找到这个模板
            </p>
          </div>

          {/* Workflow Info */}
          <div className="pt-4 border-t border-gray-200">
            <h4 className="text-sm font-semibold text-gray-700 mb-2">工作流信息</h4>
            <div className="space-y-1 text-sm text-gray-600">
              <div className="flex justify-between">
                <span>节点数量:</span>
                <span className="font-medium">{nodes.length}</span>
              </div>
              <div className="flex justify-between">
                <span>连接数量:</span>
                <span className="font-medium">{edges.length}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-gray-200">
          <button
            onClick={handleClose}
            disabled={saving}
            className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !name.trim() || !description.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                保存中...
              </>
            ) : (
              <>
                <Save size={16} />
                保存模板
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
