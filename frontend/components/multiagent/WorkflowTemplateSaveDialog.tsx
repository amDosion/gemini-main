/**
 * Workflow Template Save Dialog Component
 *
 * Modal dialog for saving current workflow as a template:
 * - create a new template
 * - overwrite the currently loaded editable template
 * - edit template metadata while saving
 */

import React, { useEffect, useMemo, useState } from 'react';
import { X, Save, Loader2, Plus } from 'lucide-react';
import type { Edge, Node } from 'reactflow';
import type { CustomNodeData } from './CustomNode';
import type { WorkflowTemplate } from './WorkflowTemplateSelector';
import { WorkflowTemplateCategoryCreateDialog } from './WorkflowTemplateCategoryCreateDialog';
import { getAuthHeaders } from '../../services/apiClient';
import {
  createWorkflowTemplateCategory,
  listWorkflowTemplateCategories,
} from '../../services/workflowTemplateCategoryService';

export interface WorkflowTemplateSaveTarget {
  id: string;
  name: string;
  description?: string;
  category?: string;
  tags?: string[];
  isEditable?: boolean;
  isLocked?: boolean;
}

interface WorkflowTemplateSaveDialogProps {
  isOpen: boolean;
  onClose: () => void;
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
  activeTemplate?: WorkflowTemplateSaveTarget | null;
  onSaveSuccess?: (
    template: WorkflowTemplate,
    meta?: { mode: 'create' | 'update' }
  ) => void;
}

const getAuthHeadersWithJson = (): HeadersInit => ({
  'Content-Type': 'application/json',
  ...getAuthHeaders(),
});

const normalizeTemplateResponse = (template: Record<string, unknown>): WorkflowTemplate => {
  const rawConfig = template?.config || {};
  return {
    id: template?.id,
    userId: typeof template?.userId === 'string' ? template.userId : undefined,
    name: template?.name || '未命名模板',
    description: template?.description || '',
    category: template?.category || '通用',
    tags: Array.isArray(template?.tags) ? template.tags : [],
    workflowType: template?.workflowType || 'graph',
    version: template?.version,
    isEditable: Boolean(template?.isEditable ?? template?.is_editable ?? true),
    isDeletable: Boolean(template?.isDeletable ?? template?.is_deletable ?? true),
    isPublic: Boolean(template?.isPublic ?? template?.is_public),
    config: {
      schemaVersion: rawConfig?.schemaVersion || 2,
      nodes: Array.isArray(rawConfig?.nodes) ? rawConfig.nodes : [],
      edges: Array.isArray(rawConfig?.edges) ? rawConfig.edges : [],
    },
    createdAt: template?.createdAt || Date.now(),
    updatedAt: template?.updatedAt || Date.now(),
  };
};

const buildTemplateConfigPayload = (
  nodes: Node<CustomNodeData>[],
  edges: Edge[],
) => ({
  schemaVersion: 2,
  nodes: nodes.map((node) => ({
    ...node,
    data: {
      ...node.data,
      status: undefined,
      progress: undefined,
      result: undefined,
      error: undefined,
      startTime: undefined,
      endTime: undefined,
    },
  })),
  edges,
});

const normalizeInitialCategory = (
  categories: string[],
  activeTemplate: WorkflowTemplateSaveTarget | null | undefined,
): string => {
  const preferred = String(activeTemplate?.category || '').trim();
  if (preferred) {
    return preferred;
  }
  return categories[0] || '';
};

export const WorkflowTemplateSaveDialog: React.FC<WorkflowTemplateSaveDialogProps> = ({
  isOpen,
  onClose,
  nodes,
  edges,
  activeTemplate = null,
  onSaveSuccess,
}) => {
  const [saveMode, setSaveMode] = useState<'create' | 'update'>('create');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(false);
  const [creatingCategory, setCreatingCategory] = useState(false);
  const [isCreateCategoryDialogOpen, setIsCreateCategoryDialogOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [categoryFeedback, setCategoryFeedback] = useState<string | null>(null);
  const [tagsInput, setTagsInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canOverwriteActiveTemplate = useMemo(
    () => Boolean(activeTemplate?.id && activeTemplate?.isEditable !== false && !activeTemplate?.isLocked),
    [activeTemplate?.id, activeTemplate?.isEditable, activeTemplate?.isLocked],
  );

  const resetForm = React.useCallback(() => {
    setSaveMode(canOverwriteActiveTemplate ? 'update' : 'create');
    setName('');
    setDescription('');
    setCategory(normalizeInitialCategory(availableCategories, activeTemplate));
    setTagsInput('');
    setIsCreateCategoryDialogOpen(false);
    setNewCategoryName('');
    setCategoryFeedback(null);
    setError(null);
  }, [activeTemplate, availableCategories, canOverwriteActiveTemplate]);

  const handleClose = React.useCallback(() => {
    if (!saving && !creatingCategory) {
      resetForm();
      onClose();
    }
  }, [creatingCategory, onClose, resetForm, saving]);

  const fetchCategories = React.useCallback(async () => {
    setLoadingCategories(true);
    setCategoryFeedback(null);
    try {
      const items = await listWorkflowTemplateCategories({
        includePublic: true,
        ensureDefaults: true,
      });
      const names = items
        .map((item) => String(item.name || '').trim())
        .filter(Boolean);
      const preferredCategory = String(activeTemplate?.category || '').trim();
      const nextNames = preferredCategory && !names.some((item) => item.toLowerCase() === preferredCategory.toLowerCase())
        ? [...names, preferredCategory]
        : names;
      setAvailableCategories(nextNames);
      setCategory((prev) => {
        if (prev && nextNames.some((item) => item.toLowerCase() === prev.toLowerCase())) {
          return prev;
        }
        return normalizeInitialCategory(nextNames, activeTemplate);
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setCategoryFeedback(`加载分类失败：${message}`);
      setAvailableCategories([]);
      setCategory(String(activeTemplate?.category || '').trim());
    } finally {
      setLoadingCategories(false);
    }
  }, [activeTemplate]);

  const handleCreateCategory = async () => {
    const normalizedName = newCategoryName.trim();
    if (!normalizedName) {
      setCategoryFeedback('新增失败：分类名称不能为空');
      return;
    }
    if (normalizedName.toLowerCase() === 'all') {
      setCategoryFeedback('新增失败：分类名称不能为 all');
      return;
    }

    const existing = availableCategories.find(
      (item) => item.toLowerCase() === normalizedName.toLowerCase(),
    );
    if (existing) {
      setCategory(existing);
      setIsCreateCategoryDialogOpen(false);
      setNewCategoryName('');
      setCategoryFeedback(`分类已存在，已选择：${existing}`);
      return;
    }

    setCreatingCategory(true);
    setCategoryFeedback(null);
    try {
      const created = await createWorkflowTemplateCategory(normalizedName);
      const createdName = String(created?.name || normalizedName).trim();
      if (!createdName) {
        throw new Error('返回的分类名称无效');
      }
      setAvailableCategories((prev) => {
        const next = [...prev];
        if (!next.some((item) => item.toLowerCase() === createdName.toLowerCase())) {
          next.push(createdName);
        }
        return next;
      });
      setCategory(createdName);
      setIsCreateCategoryDialogOpen(false);
      setNewCategoryName('');
      setCategoryFeedback(`已新增分类：${createdName}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setCategoryFeedback(`新增失败：${message}`);
    } finally {
      setCreatingCategory(false);
    }
  };

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    void fetchCategories();
  }, [fetchCategories, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const initialMode: 'create' | 'update' = canOverwriteActiveTemplate ? 'update' : 'create';
    setSaveMode(initialMode);
    if (initialMode === 'update' && activeTemplate) {
      setName(String(activeTemplate.name || '').trim());
      setDescription(String(activeTemplate.description || '').trim());
      setCategory(String(activeTemplate.category || '').trim());
      setTagsInput(Array.isArray(activeTemplate.tags) ? activeTemplate.tags.join(', ') : '');
    } else {
      setName('');
      setDescription('');
      setCategory(normalizeInitialCategory(availableCategories, activeTemplate));
      setTagsInput('');
    }
    setError(null);
    setCategoryFeedback(null);
  }, [
    activeTemplate,
    canOverwriteActiveTemplate,
    isOpen,
  ]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') {
        return;
      }
      event.preventDefault();
      if (isCreateCategoryDialogOpen) {
        if (!creatingCategory) {
          setIsCreateCategoryDialogOpen(false);
          setNewCategoryName('');
        }
        return;
      }
      if (!saving && !creatingCategory) {
        handleClose();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [creatingCategory, handleClose, isCreateCategoryDialogOpen, isOpen, saving]);

  const handleSave = async () => {
    if (!name.trim()) {
      setError('请输入模板名称');
      return;
    }
    if (!description.trim()) {
      setError('请输入模板描述');
      return;
    }
    if (!category.trim()) {
      setError('请选择模板分类');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const tags = tagsInput
        .split(',')
        .map((tag) => tag.trim())
        .filter((tag) => tag.length > 0);

      const templatePayload = {
        name: name.trim(),
        description: description.trim(),
        category: category.trim(),
        workflowType: 'graph',
        tags,
        config: buildTemplateConfigPayload(nodes, edges),
      };

      const isUpdateMode = saveMode === 'update' && canOverwriteActiveTemplate && Boolean(activeTemplate?.id);
      const endpoint = isUpdateMode
        ? `/api/workflows/templates/${encodeURIComponent(String(activeTemplate?.id || '').trim())}`
        : '/api/workflows/templates';
      const response = await fetch(endpoint, {
        method: isUpdateMode ? 'PUT' : 'POST',
        headers: getAuthHeadersWithJson(),
        body: JSON.stringify(templatePayload),
      });

      if (!response.ok) {
        let message = isUpdateMode ? '更新模板失败' : '保存模板失败';
        try {
          const errorPayload = await response.json();
          message = errorPayload?.detail || errorPayload?.message || message;
        } catch {
          const text = await response.text();
          if (text) {
            message = text;
          }
        }
        throw new Error(message);
      }

      const savedTemplate = normalizeTemplateResponse(await response.json());
      onSaveSuccess?.(savedTemplate, {
        mode: isUpdateMode ? 'update' : 'create',
      });

      resetForm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="relative bg-slate-900 rounded-xl shadow-2xl border border-slate-700 w-[620px] max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-6 border-b border-slate-700">
          <h2 className="text-xl font-semibold text-slate-100">
            {saveMode === 'update' ? '更新模板' : '保存为模板'}
          </h2>
          <button
            onClick={handleClose}
            disabled={saving}
            className="p-1 hover:bg-slate-800 rounded transition-colors disabled:opacity-50"
            aria-label="关闭"
          >
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {activeTemplate?.id && (
            <div className="p-3 rounded-lg border border-slate-700 bg-slate-950/60">
              <div className="text-sm text-slate-200">
                {canOverwriteActiveTemplate
                  ? `当前画布正在编辑模板「${activeTemplate.name}」`
                  : `当前画布来自只读模板「${activeTemplate.name}」`}
              </div>
              <div className="mt-1 text-xs text-slate-400">
                {canOverwriteActiveTemplate
                  ? '可以直接覆盖当前模板，也可以切换为另存为新模板。'
                  : '该模板不可直接覆盖，当前只支持另存为新模板。'}
              </div>
              {canOverwriteActiveTemplate && (
                <div className="mt-3 inline-flex items-stretch rounded-lg border border-slate-700 overflow-hidden bg-slate-900">
                  <button
                    type="button"
                    onClick={() => setSaveMode('update')}
                    className={`px-3 py-1.5 text-xs transition-colors ${
                      saveMode === 'update'
                        ? 'bg-teal-600 text-white'
                        : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                    }`}
                  >
                    覆盖当前模板
                  </button>
                  <button
                    type="button"
                    onClick={() => setSaveMode('create')}
                    className={`px-3 py-1.5 text-xs border-l border-slate-700 transition-colors ${
                      saveMode === 'create'
                        ? 'bg-teal-600 text-white'
                        : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                    }`}
                  >
                    另存为新模板
                  </button>
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-sm text-rose-300">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-200 mb-1">
              模板名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="例如：客户服务工作流"
              className="w-full px-3 py-2 border border-slate-700 bg-slate-800 text-slate-100 placeholder-slate-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500/50"
              disabled={saving}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-200 mb-1">
              模板描述 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="描述这个工作流模板的用途和功能..."
              rows={4}
              className="w-full px-3 py-2 border border-slate-700 bg-slate-800 text-slate-100 placeholder-slate-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500/50 resize-none"
              disabled={saving}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-200 mb-1">
              模板分类 <span className="text-red-500">*</span>
            </label>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <select
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                  className="flex-1 px-3 py-2 border border-slate-700 bg-slate-800 text-slate-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500/50 disabled:opacity-50"
                  disabled={saving || creatingCategory || loadingCategories}
                >
                  {availableCategories.length === 0 ? (
                    <option value="">
                      {loadingCategories ? '分类加载中...' : '暂无可用分类'}
                    </option>
                  ) : (
                    availableCategories.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))
                  )}
                </select>
                {!isCreateCategoryDialogOpen && (
                  <button
                    type="button"
                    onClick={() => {
                      setIsCreateCategoryDialogOpen(true);
                      setCategoryFeedback(null);
                    }}
                    disabled={saving || creatingCategory}
                    className="px-3 py-2 text-xs border border-slate-700 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                  >
                    <Plus size={13} />
                    新增分类
                  </button>
                )}
              </div>

              {categoryFeedback && (
                <div className={`text-xs ${
                  categoryFeedback.startsWith('新增失败') || categoryFeedback.startsWith('加载分类失败')
                    ? 'text-rose-300'
                    : 'text-emerald-300'
                }`}
                >
                  {categoryFeedback}
                </div>
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-200 mb-1">
              标签（可选）
            </label>
            <input
              type="text"
              value={tagsInput}
              onChange={(event) => setTagsInput(event.target.value)}
              placeholder="用逗号分隔多个标签，例如：AI, 自动化, 客服"
              className="w-full px-3 py-2 border border-slate-700 bg-slate-800 text-slate-100 placeholder-slate-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500/50"
              disabled={saving}
            />
            <p className="mt-1 text-xs text-slate-500">
              标签可以帮助其他用户更容易找到这个模板
            </p>
          </div>

          <div className="pt-4 border-t border-slate-700">
            <h4 className="text-sm font-semibold text-slate-200 mb-2">工作流信息</h4>
            <div className="space-y-1 text-sm text-slate-400">
              <div className="flex justify-between">
                <span>节点数量:</span>
                <span className="font-medium text-slate-200">{nodes.length}</span>
              </div>
              <div className="flex justify-between">
                <span>连接数量:</span>
                <span className="font-medium text-slate-200">{edges.length}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 p-4 border-t border-slate-700 bg-slate-900/80">
          <button
            onClick={handleClose}
            disabled={saving}
            className="px-4 py-2 text-slate-300 hover:bg-slate-800 rounded-lg transition-colors disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !name.trim() || !description.trim() || !category.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                保存中...
              </>
            ) : (
              <>
                <Save size={16} />
                {saveMode === 'update' ? '保存覆盖' : '保存模板'}
              </>
            )}
          </button>
        </div>

        <WorkflowTemplateCategoryCreateDialog
          isOpen={isCreateCategoryDialogOpen}
          value={newCategoryName}
          onChange={setNewCategoryName}
          onClose={() => {
            if (saving || creatingCategory) return;
            setIsCreateCategoryDialogOpen(false);
            setNewCategoryName('');
          }}
          onConfirm={() => {
            void handleCreateCategory();
          }}
          loading={creatingCategory}
          error={categoryFeedback?.startsWith('新增失败') ? categoryFeedback : null}
          title="新增模板分类"
          confirmLabel="添加分类"
        />
      </div>
    </div>
  );
};
