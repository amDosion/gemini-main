/**
 * Workflow Template Selector Component
 *
 * Modal dialog for selecting and loading workflow templates:
 * - Template list with categories
 * - Template preview
 * - Template search and filtering
 * - Load template functionality
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Loader2, Trash2, X } from 'lucide-react';
import {
  extractAudioUrls,
  extractImageUrls,
  extractTextContent,
  extractVideoUrls,
  isDirectlyRenderableAudioUrl,
  isDirectlyRenderableImageUrl,
  isDirectlyRenderableVideoUrl,
} from './workflowResultUtils';
import { getAuthHeaders } from '../../services/apiClient';
import { WorkflowTemplateCategoryCreateDialog } from './WorkflowTemplateCategoryCreateDialog';
import {
  createWorkflowTemplateCategory,
  listWorkflowTemplateCategories,
} from '../../services/workflowTemplateCategoryService';
import { getErrorMessage } from '../../utils/errorMessage';
import { type WorkflowTemplate } from './workflowTemplateTypes';

// Re-export WorkflowTemplate for backwards compat（既有 5 个 importer 用 ./WorkflowTemplateSelector）
export type { WorkflowTemplate } from './workflowTemplateTypes';
import { migrateTemplate } from './workflowTemplateMigration';
import { TemplateSearchFilter } from './templates/TemplateSearchFilter';
import { TemplateListPanel } from './templates/TemplateListPanel';
import { TemplatePreviewPanel } from './templates/TemplatePreviewPanel';
import { TemplateFooterActions } from './templates/TemplateFooterActions';

interface WorkflowTemplateSelectorProps {
  isOpen: boolean;
  onClose: () => void;
  onLoadTemplate: (template: WorkflowTemplate) => void;
}

/**
 * 从失败的模板 API 响应中解析错误消息：优先 JSON 的 detail/message，回退到响应正文文本。
 */
const resolveTemplateResponseError = async (
  response: Response,
  fallback: string
): Promise<string> => {
  try {
    const payload = await response.json();
    return payload?.detail || payload?.message || fallback;
  } catch {
    const raw = await response.text();
    return raw || fallback;
  }
};

export const WorkflowTemplateSelector: React.FC<WorkflowTemplateSelectorProps> = ({
  isOpen,
  onClose,
  onLoadTemplate,
}) => {
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [showLegacyStarterCopies, setShowLegacyStarterCopies] = useState(false);
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplate | null>(null);
  const [copyingTemplateId, setCopyingTemplateId] = useState<string | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const [editingTemplateId, setEditingTemplateId] = useState<string | null>(null);
  const [editingTemplateName, setEditingTemplateName] = useState('');
  const [savingTemplateId, setSavingTemplateId] = useState<string | null>(null);
  const [deletingTemplateId, setDeletingTemplateId] = useState<string | null>(null);
  const [pendingDeleteTemplate, setPendingDeleteTemplate] = useState<WorkflowTemplate | null>(null);
  const [isCreateCategoryDialogOpen, setIsCreateCategoryDialogOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [addingCategory, setAddingCategory] = useState(false);
  const [categoryActionFeedback, setCategoryActionFeedback] = useState<string | null>(null);
  const [templateActionFeedback, setTemplateActionFeedback] = useState<string | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchTemplates();
      fetchCategories();
      fetchCurrentUser();
    } else {
      setEditingTemplateId(null);
      setEditingTemplateName('');
      setSavingTemplateId(null);
      setDeletingTemplateId(null);
      setPendingDeleteTemplate(null);
      setIsCreateCategoryDialogOpen(false);
      setNewCategoryName('');
      setAddingCategory(false);
      setCategoryActionFeedback(null);
      setTemplateActionFeedback(null);
      setShowLegacyStarterCopies(false);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') {
        return;
      }
      event.preventDefault();

      if (pendingDeleteTemplate) {
        if (!deletingTemplateId) {
          setPendingDeleteTemplate(null);
        }
        return;
      }

      if (isCreateCategoryDialogOpen) {
        if (!addingCategory) {
          setIsCreateCategoryDialogOpen(false);
          setNewCategoryName('');
        }
        return;
      }

      if (!savingTemplateId && !deletingTemplateId && !copyingTemplateId) {
        onClose();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [
    isOpen,
    pendingDeleteTemplate,
    deletingTemplateId,
    isCreateCategoryDialogOpen,
    addingCategory,
    savingTemplateId,
    copyingTemplateId,
    onClose,
  ]);

  useEffect(() => {
    setTemplateActionFeedback(null);
    setCopyFeedback(null);
    if (!selectedTemplate || selectedTemplate.id !== editingTemplateId) {
      setEditingTemplateId(null);
      setEditingTemplateName('');
    }
  }, [selectedTemplate?.id]);

  const fetchCurrentUser = async () => {
    try {
      const response = await fetch('/api/auth/me', {
        headers: getAuthHeaders(),
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      setCurrentUserId(typeof payload?.id === 'string' ? payload.id : null);
    } catch {
      // Ignore auth fetch errors in template dialog.
    }
  };

  const fetchTemplates = async () => {
    setLoading(true);
    setError(null);
    setSelectedTemplate(null);
    try {
      const templateResponse = await fetch('/api/workflows/templates', {
        headers: getAuthHeaders(),
      });

      if (!templateResponse.ok) {
        throw new Error(await resolveTemplateResponseError(templateResponse, '加载模板失败'));
      }

      const templatePayload = await templateResponse.json();
      const userTemplates = (templatePayload.templates || []).map(
        (template: Record<string, unknown>) => ({
          ...migrateTemplate(template),
          sourceType: 'template' as const,
        })
      );

      setTemplates(userTemplates);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const fetchCategories = async () => {
    try {
      const categories = await listWorkflowTemplateCategories({
        includePublic: true,
        ensureDefaults: true,
      });
      const names = categories.map((item) => String(item.name || '').trim()).filter(Boolean);
      setAvailableCategories(names);
    } catch {
      // Ignore category fetch errors and fallback to template-derived categories.
    }
  };

  const hiddenLegacyStarterCopyCount = useMemo(
    () => templates.filter((template) => template.isLegacyStarterCopy).length,
    [templates]
  );

  const browseableTemplates = useMemo(
    () => templates.filter((template) => showLegacyStarterCopies || !template.isLegacyStarterCopy),
    [showLegacyStarterCopies, templates]
  );

  const categories = useMemo(() => {
    const merged = new Set<string>();
    availableCategories.forEach((value) => {
      const normalized = String(value || '').trim();
      if (normalized) {
        merged.add(normalized);
      }
    });
    browseableTemplates.forEach((template) => {
      const normalized = String(template.category || '').trim();
      if (normalized) {
        merged.add(normalized);
      }
    });
    return ['all', ...Array.from(merged)];
  }, [availableCategories, browseableTemplates]);

  useEffect(() => {
    if (selectedCategory === 'all') {
      return;
    }
    if (!categories.includes(selectedCategory)) {
      setSelectedCategory('all');
    }
  }, [categories, selectedCategory]);

  const filteredTemplates = useMemo(
    () =>
      browseableTemplates.filter((template) => {
        const matchesSearch =
          template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          template.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
          template.tags.some((tag) => tag.toLowerCase().includes(searchQuery.toLowerCase()));

        const matchesCategory =
          selectedCategory === 'all' || template.category === selectedCategory;

        return matchesSearch && matchesCategory;
      }),
    [browseableTemplates, searchQuery, selectedCategory]
  );

  useEffect(() => {
    if (!selectedTemplate) {
      return;
    }
    const stillVisible = filteredTemplates.some((template) => template.id === selectedTemplate.id);
    if (stillVisible) {
      return;
    }
    setSelectedTemplate(filteredTemplates[0] || null);
  }, [filteredTemplates, selectedTemplate]);

  const handleLoadTemplate = () => {
    if (!selectedTemplate) return;
    onLoadTemplate(selectedTemplate);
    onClose();
  };

  const handleEditTemplate = () => {
    if (!selectedTemplate) return;
    if (!canManageTemplate(selectedTemplate)) {
      setTemplateActionFeedback('当前模板为只读，无法直接进入编辑模式');
      return;
    }
    onLoadTemplate(selectedTemplate);
    onClose();
  };

  const handleCopyTemplate = async () => {
    if (!selectedTemplate) {
      return;
    }

    const sourceTemplateId = String(selectedTemplate.id || '').trim();
    if (!sourceTemplateId) {
      setCopyFeedback('复制失败：模板 ID 无效');
      return;
    }

    setCopyingTemplateId(sourceTemplateId);
    setCopyFeedback(null);
    try {
      const response = await fetch(
        `/api/workflows/templates/${encodeURIComponent(sourceTemplateId)}/copy`,
        {
          method: 'POST',
          headers: {
            ...getAuthHeaders(),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({}),
        }
      );

      if (!response.ok) {
        throw new Error(await resolveTemplateResponseError(response, '复制模板失败'));
      }

      const copiedPayload = await response.json();
      const copiedTemplate: WorkflowTemplate = {
        ...migrateTemplate(copiedPayload),
        sourceType: 'template',
      };

      setTemplates((prev) => {
        const filtered = prev.filter((item) => item.id !== copiedTemplate.id);
        return [copiedTemplate, ...filtered];
      });
      setSelectedTemplate(copiedTemplate);
      setCopyFeedback(`已复制模板：${copiedTemplate.name}`);
    } catch (err) {
      const message = getErrorMessage(err);
      setCopyFeedback(`复制失败：${message}`);
    } finally {
      setCopyingTemplateId(null);
    }
  };

  const canManageTemplate = (template: WorkflowTemplate | null): boolean => {
    if (!template) return false;
    if (
      template.origin?.isLocked ||
      template.isEditable === false ||
      template.isDeletable === false
    ) {
      return false;
    }
    if (!template.userId) return true;
    if (!currentUserId) return true;
    return template.userId === currentUserId;
  };

  const handleStartRenameTemplate = () => {
    if (!selectedTemplate) return;
    if (!canManageTemplate(selectedTemplate)) {
      setTemplateActionFeedback('当前模板为只读，无法编辑标题');
      return;
    }
    setEditingTemplateId(selectedTemplate.id);
    setEditingTemplateName(selectedTemplate.name);
    setTemplateActionFeedback(null);
  };

  const handleCancelRenameTemplate = () => {
    setEditingTemplateId(null);
    setEditingTemplateName('');
    setTemplateActionFeedback(null);
  };

  const handleSaveTemplateTitle = async () => {
    if (!selectedTemplate) return;
    if (!canManageTemplate(selectedTemplate)) {
      setTemplateActionFeedback('当前模板为只读，无法编辑标题');
      return;
    }

    const templateId = String(selectedTemplate.id || '').trim();
    const normalizedName = editingTemplateName.trim();
    if (!templateId) {
      setTemplateActionFeedback('更新失败：模板 ID 无效');
      return;
    }
    if (!normalizedName) {
      setTemplateActionFeedback('更新失败：模板标题不能为空');
      return;
    }
    if (normalizedName === selectedTemplate.name) {
      setEditingTemplateId(null);
      setEditingTemplateName('');
      return;
    }

    setSavingTemplateId(templateId);
    setTemplateActionFeedback(null);

    try {
      const response = await fetch(`/api/workflows/templates/${encodeURIComponent(templateId)}`, {
        method: 'PUT',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: normalizedName,
        }),
      });

      if (!response.ok) {
        throw new Error(await resolveTemplateResponseError(response, '更新模板标题失败'));
      }

      const payload = await response.json();
      const updatedTemplate: WorkflowTemplate = {
        ...migrateTemplate(payload),
        sourceType: 'template',
      };

      setTemplates((prev) =>
        prev.map((item) => (item.id === updatedTemplate.id ? updatedTemplate : item))
      );
      setSelectedTemplate(updatedTemplate);
      setEditingTemplateId(null);
      setEditingTemplateName('');
      setTemplateActionFeedback(`已更新模板标题：${updatedTemplate.name}`);
    } catch (err) {
      const message = getErrorMessage(err);
      setTemplateActionFeedback(`更新失败：${message}`);
    } finally {
      setSavingTemplateId(null);
    }
  };

  const handleRequestDeleteTemplate = () => {
    if (!selectedTemplate) return;
    if (!canManageTemplate(selectedTemplate)) {
      setTemplateActionFeedback('当前模板为只读，无法删除');
      return;
    }
    setPendingDeleteTemplate(selectedTemplate);
    setTemplateActionFeedback(null);
  };

  const handleConfirmDeleteTemplate = async () => {
    const targetTemplate = pendingDeleteTemplate || selectedTemplate;
    if (!targetTemplate) return;
    if (!canManageTemplate(targetTemplate)) {
      setTemplateActionFeedback('当前模板为只读，无法删除');
      return;
    }

    const templateId = String(targetTemplate.id || '').trim();
    if (!templateId) {
      setTemplateActionFeedback('删除失败：模板 ID 无效');
      return;
    }

    setDeletingTemplateId(templateId);
    setTemplateActionFeedback(null);
    try {
      const response = await fetch(`/api/workflows/templates/${encodeURIComponent(templateId)}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      if (!response.ok) {
        throw new Error(await resolveTemplateResponseError(response, '删除模板失败'));
      }

      const nextTemplates = templates.filter((item) => item.id !== templateId);
      setTemplates(nextTemplates);
      setSelectedTemplate(nextTemplates.length > 0 ? nextTemplates[0] : null);
      setEditingTemplateId(null);
      setEditingTemplateName('');
      setPendingDeleteTemplate(null);
      setTemplateActionFeedback('模板已删除');
    } catch (err) {
      const message = getErrorMessage(err);
      setTemplateActionFeedback(`删除失败：${message}`);
    } finally {
      setDeletingTemplateId(null);
    }
  };

  const handleCreateCategory = async () => {
    const normalizedName = newCategoryName.trim();
    if (!normalizedName) {
      setCategoryActionFeedback('新增失败：分类名称不能为空');
      return;
    }
    if (normalizedName.toLowerCase() === 'all') {
      setCategoryActionFeedback('新增失败：分类名称不能为 all');
      return;
    }

    const existingCategory = categories.find(
      (item) => item !== 'all' && item.toLowerCase() === normalizedName.toLowerCase()
    );
    if (existingCategory) {
      setSelectedCategory(existingCategory);
      setNewCategoryName('');
      setIsCreateCategoryDialogOpen(false);
      setCategoryActionFeedback(`分类已存在，已定位到：${existingCategory}`);
      return;
    }

    setAddingCategory(true);
    setCategoryActionFeedback(null);
    try {
      const created = await createWorkflowTemplateCategory(normalizedName);
      const createdName = String(created?.name || normalizedName).trim();
      if (!createdName) {
        throw new Error('返回的分类名称无效');
      }

      setAvailableCategories((prev) => {
        const next = [...prev];
        const exists = next.some((item) => item.toLowerCase() === createdName.toLowerCase());
        if (!exists) {
          next.push(createdName);
        }
        return next;
      });
      setSelectedCategory(createdName);
      setNewCategoryName('');
      setIsCreateCategoryDialogOpen(false);
      setCategoryActionFeedback(`已新增分类：${createdName}`);
    } catch (err) {
      const message = getErrorMessage(err);
      setCategoryActionFeedback(`新增失败：${message}`);
    } finally {
      setAddingCategory(false);
    }
  };

  const mergeSampleUrls = (
    summaryUrls: string[] | undefined,
    extracted: string[],
    isRenderable: (url: string) => boolean
  ): string[] =>
    Array.from(new Set([...(Array.isArray(summaryUrls) ? summaryUrls : []), ...extracted])).filter(
      isRenderable
    );

  const selectedTemplateSampleImageUrls = selectedTemplate
    ? mergeSampleUrls(
        selectedTemplate.sampleResultSummary?.imageUrls,
        extractImageUrls(selectedTemplate.sampleResult),
        isDirectlyRenderableImageUrl
      )
    : [];
  const selectedTemplateSampleAudioUrls = selectedTemplate
    ? mergeSampleUrls(
        selectedTemplate.sampleResultSummary?.audioUrls,
        extractAudioUrls(selectedTemplate.sampleResult),
        isDirectlyRenderableAudioUrl
      )
    : [];
  const selectedTemplateSampleVideoUrls = selectedTemplate
    ? mergeSampleUrls(
        selectedTemplate.sampleResultSummary?.videoUrls,
        extractVideoUrls(selectedTemplate.sampleResult),
        isDirectlyRenderableVideoUrl
      )
    : [];
  const selectedTemplateSampleTextPreview = selectedTemplate
    ? (
        selectedTemplate.sampleResultSummary?.textPreview ||
        extractTextContent(selectedTemplate.sampleResult)
      ).trim()
    : '';
  const selectedTemplateHasSampleResult = selectedTemplate
    ? Boolean(selectedTemplate.sampleResultSummary?.hasResult || selectedTemplate.sampleResult)
    : false;

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="relative bg-slate-900 rounded-xl shadow-2xl border border-slate-700 w-[920px] max-h-[82vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-700">
          <h2 className="text-xl font-semibold text-slate-100">选择工作流模板</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-800 rounded transition-colors"
            aria-label="关闭"
          >
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        {/* Search and Filter */}
        <TemplateSearchFilter
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          categories={categories}
          selectedCategory={selectedCategory}
          setSelectedCategory={setSelectedCategory}
          isCreateCategoryDialogOpen={isCreateCategoryDialogOpen}
          setIsCreateCategoryDialogOpen={setIsCreateCategoryDialogOpen}
          hiddenLegacyStarterCopyCount={hiddenLegacyStarterCopyCount}
          showLegacyStarterCopies={showLegacyStarterCopies}
          setShowLegacyStarterCopies={setShowLegacyStarterCopies}
          addingCategory={addingCategory}
          categoryActionFeedback={categoryActionFeedback}
          setCategoryActionFeedback={setCategoryActionFeedback}
        />

        {/* Content */}
        <div className="flex-1 overflow-hidden flex">
          {/* Template List */}
          <TemplateListPanel
            loading={loading}
            error={error}
            filteredTemplates={filteredTemplates}
            selectedTemplate={selectedTemplate}
            setSelectedTemplate={setSelectedTemplate}
            fetchTemplates={fetchTemplates}
          />

          {/* Template Preview */}
          <TemplatePreviewPanel
            selectedTemplate={selectedTemplate}
            editingTemplateId={editingTemplateId}
            editingTemplateName={editingTemplateName}
            setEditingTemplateName={setEditingTemplateName}
            savingTemplateId={savingTemplateId}
            handleSaveTemplateTitle={handleSaveTemplateTitle}
            handleCancelRenameTemplate={handleCancelRenameTemplate}
            handleStartRenameTemplate={handleStartRenameTemplate}
            canManageTemplate={canManageTemplate}
            selectedTemplateHasSampleResult={selectedTemplateHasSampleResult}
            selectedTemplateSampleImageUrls={selectedTemplateSampleImageUrls}
            selectedTemplateSampleVideoUrls={selectedTemplateSampleVideoUrls}
            selectedTemplateSampleAudioUrls={selectedTemplateSampleAudioUrls}
            selectedTemplateSampleTextPreview={selectedTemplateSampleTextPreview}
            copyFeedback={copyFeedback}
            templateActionFeedback={templateActionFeedback}
          />
        </div>

        {/* Footer */}
        <TemplateFooterActions
          selectedTemplate={selectedTemplate}
          copyingTemplateId={copyingTemplateId}
          deletingTemplateId={deletingTemplateId}
          canManageTemplate={canManageTemplate}
          handleCopyTemplate={handleCopyTemplate}
          handleEditTemplate={handleEditTemplate}
          handleRequestDeleteTemplate={handleRequestDeleteTemplate}
          handleLoadTemplate={handleLoadTemplate}
          onClose={onClose}
        />

        {pendingDeleteTemplate && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/65 backdrop-blur-sm">
            <div className="w-[420px] max-w-[90vw] rounded-xl border border-slate-700 bg-slate-900 shadow-2xl p-5">
              <h3 className="text-base font-semibold text-slate-100 mb-2">确认删除模板</h3>
              <p className="text-sm text-slate-300">
                将永久删除模板「
                <span className="text-rose-200">{pendingDeleteTemplate.name}</span>
                」，此操作不可撤销。
              </p>
              <div className="mt-5 flex items-center justify-end gap-2">
                <button
                  onClick={() => setPendingDeleteTemplate(null)}
                  disabled={Boolean(deletingTemplateId)}
                  className="px-3 py-1.5 text-sm bg-slate-800 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  取消
                </button>
                <button
                  onClick={handleConfirmDeleteTemplate}
                  disabled={Boolean(deletingTemplateId)}
                  className="px-3 py-1.5 text-sm border border-rose-700/70 bg-rose-900/30 text-rose-200 rounded-lg hover:bg-rose-800/40 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                >
                  {deletingTemplateId ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <Trash2 size={13} />
                  )}
                  确认删除
                </button>
              </div>
            </div>
          </div>
        )}

        <WorkflowTemplateCategoryCreateDialog
          isOpen={isCreateCategoryDialogOpen}
          value={newCategoryName}
          onChange={setNewCategoryName}
          onClose={() => {
            if (addingCategory) return;
            setIsCreateCategoryDialogOpen(false);
            setNewCategoryName('');
          }}
          onConfirm={() => {
            void handleCreateCategory();
          }}
          loading={addingCategory}
          error={categoryActionFeedback?.startsWith('新增失败') ? categoryActionFeedback : null}
          title="新增模板分类"
          confirmLabel="添加分类"
        />
      </div>
    </div>
  );
};
