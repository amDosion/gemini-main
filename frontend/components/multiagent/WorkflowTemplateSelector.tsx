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
import { X, Search, FileText, Loader2, ChevronRight, Copy, Pencil, Save, Trash2, Plus, Video, Mic } from 'lucide-react';
import { Node, Edge } from 'reactflow';
import { CustomNodeData } from './CustomNode';
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
import { mergeRuntimeHints } from '../views/multiagent/runtimeHints';

interface WorkflowTemplateResultSummary {
  hasResult: boolean;
  textPreview: string;
  imageCount: number;
  imageUrls: string[];
  audioCount: number;
  audioUrls: string[];
  videoCount: number;
  videoUrls: string[];
  runtimeHints: string[];
  primaryRuntime?: string;
  continuationStrategy?: string;
  videoExtensionCount?: number;
  videoExtensionApplied?: number;
  totalDurationSeconds?: number;
  continuedFromVideo?: boolean;
  subtitleMode?: string;
  subtitleFileCount?: number;
}

interface WorkflowTemplateSampleInput {
  task?: string;
  prompt?: string;
  text?: string;
  imageUrl?: string;
  imageUrls?: string[];
  videoUrl?: string;
  videoUrls?: string[];
  audioUrl?: string;
  audioUrls?: string[];
  prompts?: string[];
  fileUrl?: string;
  fileUrls?: string[];
}

type WorkflowTemplateSourceKind = 'all' | 'user' | 'starter' | 'public';

interface WorkflowTemplateOrigin {
  kind: Exclude<WorkflowTemplateSourceKind, 'all'>;
  label: string;
  isLocked: boolean;
  runtimeScope?: string;
  runtimeLabel?: string;
}

export interface WorkflowTemplate {
  id: string;
  userId?: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  thumbnail?: string;
  workflowType?: string;
  version?: number;
  sourceType?: 'template';
  modeId?: string;
  isPublic?: boolean;
  promptHint?: string;
  promptExample?: any;
  requiresImage?: boolean;
  estimatedNodeCount?: number;
  estimatedEdgeCount?: number;
  sampleResult?: any;
  sampleResultSummary?: WorkflowTemplateResultSummary;
  sampleResultUpdatedAt?: number;
  sampleExecutionId?: string;
  sampleInput?: WorkflowTemplateSampleInput;
  isStarter?: boolean;
  starterKey?: string;
  starterVersion?: number;
  copiedFromStarterKey?: string;
  isEditable?: boolean;
  isDeletable?: boolean;
  runtimeScope?: string;
  runtimeLabel?: string;
  origin?: WorkflowTemplateOrigin;
  taskTypes?: string[];
  primaryTaskType?: string;
  bindingStrategy?: string;
  isLegacyStarterCopy?: boolean;
  legacyFlags?: string[];
  legacyReason?: string;
  config: {
    schemaVersion?: number;
    nodes: Node<CustomNodeData>[];
    edges: Edge[];
  };
  createdAt: number;
  updatedAt: number;
}

const normalizeTemplateSourceKind = (value: any): Exclude<WorkflowTemplateSourceKind, 'all'> => {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'starter') return 'starter';
  if (normalized === 'public') return 'public';
  return 'user';
};

const normalizeTemplateRuntimeScope = (value: any): string | undefined => {
  const normalized = String(value || '').trim();
  return normalized || undefined;
};

const resolveTemplateOriginKind = (template: WorkflowTemplate): Exclude<WorkflowTemplateSourceKind, 'all'> => {
  if (template.origin?.kind) {
    return template.origin.kind;
  }
  if (template.isStarter || template.starterKey) {
    return 'starter';
  }
  if (template.isPublic) {
    return 'public';
  }
  return 'user';
};

const resolveTemplateOriginLabel = (template: WorkflowTemplate): string => {
  if (template.origin?.label) {
    return template.origin.label;
  }
  const originKind = resolveTemplateOriginKind(template);
  if (originKind === 'starter') return '官方 Starter';
  if (originKind === 'public') return '公开模板';
  return '我的模板';
};

const resolveTemplateRuntimeLabel = (template: WorkflowTemplate): string | undefined => {
  if (template.origin?.runtimeLabel) {
    return template.origin.runtimeLabel;
  }
  if (template.runtimeLabel) {
    return template.runtimeLabel;
  }
  const runtimeScope = template.origin?.runtimeScope || template.runtimeScope;
  if (runtimeScope === 'google-runtime') {
    return 'Google runtime';
  }
  if (runtimeScope === 'provider-neutral') {
    return 'Provider-neutral';
  }
  return undefined;
};

interface WorkflowTemplateSelectorProps {
  isOpen: boolean;
  onClose: () => void;
  onLoadTemplate: (template: WorkflowTemplate) => void;
}

export const WorkflowTemplateSelector: React.FC<WorkflowTemplateSelectorProps> = ({
  isOpen,
  onClose,
  onLoadTemplate
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

  const migrateTemplate = (template: any): WorkflowTemplate => {
    const rawConfig = template?.config || {};
    const rawNodes = Array.isArray(rawConfig.nodes) ? rawConfig.nodes : [];
    const rawEdges = Array.isArray(rawConfig.edges) ? rawConfig.edges : [];
    const migratedNodes = rawNodes.map((node: any) => ({
      ...node,
      data: {
        ...(node?.data || {}),
        type: node?.data?.type || node?.type || 'agent',
      },
    }));
    const migratedEdges = rawEdges;
    const rawTags = Array.isArray(template?.tags) ? template.tags : [];
    const estimatedNodeCount = Number(
      template?.estimatedNodeCount ?? rawNodes.length ?? 0
    ) || 0;
    const estimatedEdgeCount = Number(
      template?.estimatedEdgeCount ?? rawEdges.length ?? 0
    ) || 0;
    const rawSampleSummary = template?.sampleResultSummary;
    const sampleSummary = rawSampleSummary && typeof rawSampleSummary === 'object' && !Array.isArray(rawSampleSummary)
      ? {
        hasResult: Boolean(rawSampleSummary.hasResult),
        textPreview: String(rawSampleSummary.textPreview || '').trim(),
        imageCount: Number((rawSampleSummary.imageCount ?? rawSampleSummary.image_count) || 0) || 0,
        imageUrls: Array.isArray(rawSampleSummary.imageUrls)
          ? rawSampleSummary.imageUrls.filter((value: any) => typeof value === 'string')
          : Array.isArray(rawSampleSummary.image_urls)
            ? rawSampleSummary.image_urls.filter((value: any) => typeof value === 'string')
            : [],
        audioCount: Number((rawSampleSummary.audioCount ?? rawSampleSummary.audio_count) || 0) || 0,
        audioUrls: Array.isArray(rawSampleSummary.audioUrls)
          ? rawSampleSummary.audioUrls.filter((value: any) => typeof value === 'string')
          : Array.isArray(rawSampleSummary.audio_urls)
            ? rawSampleSummary.audio_urls.filter((value: any) => typeof value === 'string')
            : [],
        videoCount: Number((rawSampleSummary.videoCount ?? rawSampleSummary.video_count) || 0) || 0,
        videoUrls: Array.isArray(rawSampleSummary.videoUrls)
          ? rawSampleSummary.videoUrls.filter((value: any) => typeof value === 'string')
          : Array.isArray(rawSampleSummary.video_urls)
            ? rawSampleSummary.video_urls.filter((value: any) => typeof value === 'string')
            : [],
        runtimeHints: mergeRuntimeHints(
          [],
          Array.isArray(rawSampleSummary.runtimeHints) ? rawSampleSummary.runtimeHints : [],
        ),
        primaryRuntime: String(rawSampleSummary.primaryRuntime || '').trim() || undefined,
        continuationStrategy: String(
          rawSampleSummary.continuationStrategy || rawSampleSummary.continuation_strategy || ''
        ).trim() || undefined,
        videoExtensionCount: Number(
          (rawSampleSummary.videoExtensionCount ?? rawSampleSummary.video_extension_count) || 0
        ) || 0,
        videoExtensionApplied: Number(
          (rawSampleSummary.videoExtensionApplied ?? rawSampleSummary.video_extension_applied) || 0
        ) || 0,
        totalDurationSeconds: Number(
          (rawSampleSummary.totalDurationSeconds ?? rawSampleSummary.total_duration_seconds) || 0
        ) || 0,
        continuedFromVideo: Boolean(
          rawSampleSummary.continuedFromVideo ?? rawSampleSummary.continued_from_video ?? false
        ),
        subtitleMode: String(
          rawSampleSummary.subtitleMode || rawSampleSummary.subtitle_mode || ''
        ).trim() || undefined,
        subtitleFileCount: Number(
          (rawSampleSummary.subtitleFileCount ?? rawSampleSummary.subtitle_file_count) || 0
        ) || 0,
      }
      : undefined;
    const rawSampleInput = template?.sampleInput;
    const sampleInput = rawSampleInput && typeof rawSampleInput === 'object' && !Array.isArray(rawSampleInput)
      ? {
        task: typeof rawSampleInput.task === 'string' ? rawSampleInput.task : undefined,
        prompt: typeof rawSampleInput.prompt === 'string' ? rawSampleInput.prompt : undefined,
        text: typeof rawSampleInput.text === 'string' ? rawSampleInput.text : undefined,
        imageUrl: typeof rawSampleInput.imageUrl === 'string' ? rawSampleInput.imageUrl : undefined,
        imageUrls: Array.isArray(rawSampleInput.imageUrls)
          ? rawSampleInput.imageUrls.filter((value: any) => typeof value === 'string')
          : undefined,
        videoUrl: typeof rawSampleInput.videoUrl === 'string'
          ? rawSampleInput.videoUrl
          : typeof rawSampleInput.video_url === 'string'
            ? rawSampleInput.video_url
            : undefined,
        videoUrls: Array.isArray(rawSampleInput.videoUrls)
          ? rawSampleInput.videoUrls.filter((value: any) => typeof value === 'string')
          : Array.isArray(rawSampleInput.video_urls)
            ? rawSampleInput.video_urls.filter((value: any) => typeof value === 'string')
            : undefined,
        audioUrl: typeof rawSampleInput.audioUrl === 'string'
          ? rawSampleInput.audioUrl
          : typeof rawSampleInput.audio_url === 'string'
            ? rawSampleInput.audio_url
            : undefined,
        audioUrls: Array.isArray(rawSampleInput.audioUrls)
          ? rawSampleInput.audioUrls.filter((value: any) => typeof value === 'string')
          : Array.isArray(rawSampleInput.audio_urls)
            ? rawSampleInput.audio_urls.filter((value: any) => typeof value === 'string')
            : undefined,
        prompts: Array.isArray(rawSampleInput.prompts)
          ? rawSampleInput.prompts.filter((value: any) => typeof value === 'string')
          : undefined,
        fileUrl: typeof rawSampleInput.fileUrl === 'string' ? rawSampleInput.fileUrl : undefined,
        fileUrls: Array.isArray(rawSampleInput.fileUrls)
          ? rawSampleInput.fileUrls.filter((value: any) => typeof value === 'string')
          : Array.isArray(rawSampleInput.file_urls)
            ? rawSampleInput.file_urls.filter((value: any) => typeof value === 'string')
            : undefined,
      }
      : undefined;
    const sampleResultUpdatedAt = Number(template?.sampleResultUpdatedAt || 0) || undefined;
    const starterKey = String(template?.starterKey ?? template?.starter_key ?? '').trim() || undefined;
    const starterVersion = Number(template?.starterVersion ?? template?.starter_version ?? 0) || undefined;
    const isStarter = Boolean(template?.isStarter ?? template?.is_starter ?? starterKey);
    const copiedFromStarterKey = String(
      template?.copiedFromStarterKey
      ?? template?.copied_from_starter_key
      ?? ''
    ).trim() || undefined;
    const runtimeScope = normalizeTemplateRuntimeScope(
      template?.runtimeScope
      ?? template?.runtime_scope
      ?? template?.origin?.runtimeScope
      ?? template?.origin?.runtime_scope
    );
    const runtimeLabel = String(
      template?.runtimeLabel
      ?? template?.runtime_label
      ?? template?.origin?.runtimeLabel
      ?? template?.origin?.runtime_label
      ?? ''
    ).trim() || undefined;
    const originKind = normalizeTemplateSourceKind(
      template?.origin?.kind
      ?? template?.originKind
      ?? template?.origin_kind
      ?? (isStarter ? 'starter' : (template?.isPublic ? 'public' : 'user'))
    );
    const originLabel = String(
      template?.origin?.label
      ?? template?.originLabel
      ?? template?.origin_label
      ?? (originKind === 'starter' ? '官方 Starter' : originKind === 'public' ? '公开模板' : '我的模板')
    ).trim() || (originKind === 'starter' ? '官方 Starter' : originKind === 'public' ? '公开模板' : '我的模板');
    const originIsLocked = Boolean(
      template?.origin?.isLocked
      ?? template?.origin?.is_locked
      ?? template?.isLocked
      ?? template?.is_locked
      ?? isStarter
    );
    const rawTaskTypes =
      template?.taskTypes
      ?? template?.task_types
      ?? rawConfig?._templateMeta?.taskTypes
      ?? rawConfig?._templateMeta?.task_types;
    const taskTypes = Array.isArray(rawTaskTypes)
      ? rawTaskTypes.filter((value: any) => typeof value === 'string')
      : [];
    const primaryTaskType = String(
      template?.primaryTaskType
      ?? template?.primary_task_type
      ?? rawConfig?._templateMeta?.primaryTaskType
      ?? rawConfig?._templateMeta?.primary_task_type
      ?? ''
    ).trim() || undefined;
    const bindingStrategy = String(
      template?.bindingStrategy
      ?? template?.binding_strategy
      ?? rawConfig?._templateMeta?.bindingStrategy
      ?? rawConfig?._templateMeta?.binding_strategy
      ?? ''
    ).trim() || undefined;
    const isLegacyStarterCopy = Boolean(
      template?.isLegacyStarterCopy
      ?? template?.is_legacy_starter_copy
      ?? rawConfig?._templateMeta?.isLegacyStarterCopy
      ?? rawConfig?._templateMeta?.is_legacy_starter_copy
    );
    const legacyFlags = Array.isArray(
      template?.legacyFlags
      ?? template?.legacy_flags
      ?? rawConfig?._templateMeta?.legacyFlags
      ?? rawConfig?._templateMeta?.legacy_flags
    )
      ? (template?.legacyFlags
        ?? template?.legacy_flags
        ?? rawConfig?._templateMeta?.legacyFlags
        ?? rawConfig?._templateMeta?.legacy_flags).filter((value: any) => typeof value === 'string')
      : [];
    const legacyReason = String(
      template?.legacyReason
      ?? template?.legacy_reason
      ?? rawConfig?._templateMeta?.legacyReason
      ?? rawConfig?._templateMeta?.legacy_reason
      ?? ''
    ).trim() || undefined;

    return {
      id: template?.id,
      userId: typeof template?.userId === 'string' ? template.userId : undefined,
      name: template?.name || '未命名模板',
      description: template?.description || '',
      category: template?.category || '通用',
      tags: rawTags,
      thumbnail: template?.thumbnail,
      workflowType: template?.workflowType || 'graph',
      version: template?.version,
      isPublic: Boolean(template?.isPublic),
      modeId: template?.modeId || '',
      promptHint: template?.promptHint ?? '',
      promptExample: template?.promptExample,
      requiresImage: Boolean(template?.requiresImage),
      estimatedNodeCount,
      estimatedEdgeCount,
      sampleResult: template?.sampleResult,
      sampleResultSummary: sampleSummary,
      sampleResultUpdatedAt,
      sampleExecutionId: String(template?.sampleExecutionId || '').trim() || undefined,
      sampleInput,
      isStarter,
      starterKey,
      starterVersion,
      copiedFromStarterKey,
      isEditable: Boolean(template?.isEditable ?? template?.is_editable ?? !originIsLocked),
      isDeletable: Boolean(template?.isDeletable ?? template?.is_deletable ?? !originIsLocked),
      runtimeScope,
      runtimeLabel,
      taskTypes,
      primaryTaskType,
      bindingStrategy,
      isLegacyStarterCopy,
      legacyFlags,
      legacyReason,
      origin: {
        kind: originKind,
        label: originLabel,
        isLocked: originIsLocked,
        runtimeScope,
        runtimeLabel,
      },
      config: {
        schemaVersion: rawConfig?.schemaVersion || 2,
        nodes: migratedNodes,
        edges: migratedEdges,
      },
      createdAt: template?.createdAt || Date.now(),
      updatedAt: template?.updatedAt || Date.now(),
    };
  };

  const fetchCurrentUser = async () => {
    try {
      const response = await fetch('/api/auth/me', {
        headers: getAuthHeaders(),
        credentials: 'include',
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
        credentials: 'include',
      });

      if (!templateResponse.ok) {
        let message = '加载模板失败';
        try {
          const errorPayload = await templateResponse.json();
          message = errorPayload?.detail || errorPayload?.message || message;
        } catch {
          const text = await templateResponse.text();
          if (text) {
            message = text;
          }
        }
        throw new Error(message);
      }

      const templatePayload = await templateResponse.json();
      const userTemplates = (templatePayload.templates || []).map((template: any) => ({
        ...migrateTemplate(template),
        sourceType: 'template' as const,
      }));

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
      const names = categories
        .map((item) => String(item.name || '').trim())
        .filter(Boolean);
      setAvailableCategories(names);
    } catch {
      // Ignore category fetch errors and fallback to template-derived categories.
    }
  };

  const hiddenLegacyStarterCopyCount = useMemo(
    () => templates.filter((template) => template.isLegacyStarterCopy).length,
    [templates],
  );

  const browseableTemplates = useMemo(
    () => templates.filter((template) => showLegacyStarterCopies || !template.isLegacyStarterCopy),
    [showLegacyStarterCopies, templates],
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

  const filteredTemplates = useMemo(() => browseableTemplates.filter(template => {
    const matchesSearch =
      template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesCategory = selectedCategory === 'all' || template.category === selectedCategory;

    return matchesSearch && matchesCategory;
  }), [
    browseableTemplates,
    searchQuery,
    selectedCategory,
  ]);

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
      const response = await fetch(`/api/workflows/templates/${encodeURIComponent(sourceTemplateId)}/copy`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({}),
      });

      if (!response.ok) {
        let message = '复制模板失败';
        try {
          const payload = await response.json();
          message = payload?.detail || payload?.message || message;
        } catch {
          const raw = await response.text();
          if (raw) {
            message = raw;
          }
        }
        throw new Error(message);
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
      const message = err instanceof Error ? err.message : String(err);
      setCopyFeedback(`复制失败：${message}`);
    } finally {
      setCopyingTemplateId(null);
    }
  };

  const canManageTemplate = (template: WorkflowTemplate | null): boolean => {
    if (!template) return false;
    if (template.origin?.isLocked || template.isEditable === false || template.isDeletable === false) {
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
        credentials: 'include',
        body: JSON.stringify({
          name: normalizedName,
        }),
      });

      if (!response.ok) {
        let message = '更新模板标题失败';
        try {
          const payload = await response.json();
          message = payload?.detail || payload?.message || message;
        } catch {
          const raw = await response.text();
          if (raw) {
            message = raw;
          }
        }
        throw new Error(message);
      }

      const payload = await response.json();
      const updatedTemplate: WorkflowTemplate = {
        ...migrateTemplate(payload),
        sourceType: 'template',
      };

      setTemplates((prev) => prev.map((item) => (
        item.id === updatedTemplate.id ? updatedTemplate : item
      )));
      setSelectedTemplate(updatedTemplate);
      setEditingTemplateId(null);
      setEditingTemplateName('');
      setTemplateActionFeedback(`已更新模板标题：${updatedTemplate.name}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
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
        credentials: 'include',
      });
      if (!response.ok) {
        let message = '删除模板失败';
        try {
          const payload = await response.json();
          message = payload?.detail || payload?.message || message;
        } catch {
          const raw = await response.text();
          if (raw) {
            message = raw;
          }
        }
        throw new Error(message);
      }

      const nextTemplates = templates.filter((item) => item.id !== templateId);
      setTemplates(nextTemplates);
      setSelectedTemplate(nextTemplates.length > 0 ? nextTemplates[0] : null);
      setEditingTemplateId(null);
      setEditingTemplateName('');
      setPendingDeleteTemplate(null);
      setTemplateActionFeedback('模板已删除');
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
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
      (item) => item !== 'all' && item.toLowerCase() === normalizedName.toLowerCase(),
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
      const message = err instanceof Error ? err.message : String(err);
      setCategoryActionFeedback(`新增失败：${message}`);
    } finally {
      setAddingCategory(false);
    }
  };

  const selectedTemplateSampleImageUrls = selectedTemplate
    ? Array.from(new Set([
      ...(Array.isArray(selectedTemplate.sampleResultSummary?.imageUrls)
        ? selectedTemplate.sampleResultSummary.imageUrls
        : []),
      ...extractImageUrls(selectedTemplate.sampleResult),
    ]))
      .filter((url) => isDirectlyRenderableImageUrl(url))
    : [];
  const selectedTemplateSampleAudioUrls = selectedTemplate
    ? Array.from(new Set([
      ...(Array.isArray(selectedTemplate.sampleResultSummary?.audioUrls)
        ? selectedTemplate.sampleResultSummary.audioUrls
        : []),
      ...extractAudioUrls(selectedTemplate.sampleResult),
    ]))
      .filter((url) => isDirectlyRenderableAudioUrl(url))
    : [];
  const selectedTemplateSampleVideoUrls = selectedTemplate
    ? Array.from(new Set([
      ...(Array.isArray(selectedTemplate.sampleResultSummary?.videoUrls)
        ? selectedTemplate.sampleResultSummary.videoUrls
        : []),
      ...extractVideoUrls(selectedTemplate.sampleResult),
    ]))
      .filter((url) => isDirectlyRenderableVideoUrl(url))
    : [];
  const selectedTemplateSampleTextPreview = selectedTemplate
    ? (
      selectedTemplate.sampleResultSummary?.textPreview
      || extractTextContent(selectedTemplate.sampleResult)
    ).trim()
    : '';
  const selectedTemplateHasSampleResult = selectedTemplate
    ? Boolean(
      selectedTemplate.sampleResultSummary?.hasResult
      || selectedTemplate.sampleResult
    )
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
        <div className="p-4 border-b border-slate-700 space-y-3 bg-slate-900/80">
          {/* Search Bar */}
          <div className="relative">
            <Search size={18} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索模板名称、描述或标签..."
              className="w-full pl-10 pr-4 py-2 border border-slate-700 rounded-lg bg-slate-800 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500/50"
            />
          </div>

          {/* Category Filter */}
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div className="flex-1 overflow-x-auto">
                <div className="inline-flex items-stretch rounded-lg border border-slate-700 overflow-hidden bg-slate-900 min-w-max">
                  {categories.map((category, index) => (
                    <button
                      key={category}
                      onClick={() => setSelectedCategory(category)}
                      className={`px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors ${
                        index > 0 ? 'border-l border-slate-700' : ''
                      } ${
                        selectedCategory === category
                          ? 'bg-teal-600 text-white'
                          : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                      }`}
                    >
                      {category === 'all' ? '全部' : category}
                    </button>
                  ))}
                </div>
              </div>
              {!isCreateCategoryDialogOpen && (
                <div className="flex items-center gap-2">
                  {hiddenLegacyStarterCopyCount > 0 && (
                    <button
                      type="button"
                      onClick={() => setShowLegacyStarterCopies((prev) => !prev)}
                      className={`px-3 py-1.5 text-xs border rounded-lg transition-colors ${
                        showLegacyStarterCopies
                          ? 'border-amber-500/40 bg-amber-500/10 text-amber-200'
                          : 'border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700'
                      }`}
                    >
                      {showLegacyStarterCopies ? '隐藏遗留 Starter 副本' : `显示遗留 Starter 副本 ${hiddenLegacyStarterCopyCount}`}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      setIsCreateCategoryDialogOpen(true);
                      setCategoryActionFeedback(null);
                    }}
                    disabled={addingCategory}
                    className="px-3 py-1.5 text-xs border border-slate-700 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                  >
                    <Plus size={13} />
                    新增分类
                  </button>
                </div>
              )}
            </div>

            {hiddenLegacyStarterCopyCount > 0 && !showLegacyStarterCopies && (
              <div className="text-[11px] text-amber-200 border border-amber-500/20 bg-amber-500/10 rounded-lg px-3 py-2">
                已默认隐藏 {hiddenLegacyStarterCopyCount} 个遗留 Starter 副本，这些模板仍使用旧的 `agentName` 绑定。
              </div>
            )}

            {categoryActionFeedback && (
              <div
                className={`text-xs ${
                  categoryActionFeedback.startsWith('新增失败') ? 'text-rose-300' : 'text-emerald-300'
                }`}
              >
                {categoryActionFeedback}
              </div>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex">
          {/* Template List */}
          <div className="w-1/2 border-r border-slate-700 overflow-y-auto bg-slate-950/40">
            {loading ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 size={32} className="animate-spin text-teal-400" />
              </div>
            ) : error ? (
              <div className="flex items-center justify-center h-full text-rose-300">
                <div className="text-center">
                  <p className="font-medium">加载失败</p>
                  <p className="text-sm mt-1">{error}</p>
                  <button
                    onClick={fetchTemplates}
                    className="mt-3 px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-500"
                  >
                    重试
                  </button>
                </div>
              </div>
            ) : filteredTemplates.length === 0 ? (
              <div className="flex items-center justify-center h-full text-slate-500">
                <div className="text-center">
                  <FileText size={48} className="mx-auto mb-2" />
                  <p>没有找到匹配的模板</p>
                </div>
              </div>
            ) : (
              <div className="p-4 space-y-4">
                {filteredTemplates.map(template => (
                  <button
                    key={template.id}
                    onClick={() => setSelectedTemplate(template)}
                    className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                      selectedTemplate?.id === template.id
                        ? 'border-teal-500 bg-teal-500/10'
                        : 'border-slate-700 hover:border-slate-600 hover:bg-slate-800/60'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="font-semibold text-slate-100 mb-1">
                          {template.name}
                        </h3>
                        <p className="text-sm text-slate-400 mb-2 line-clamp-2">
                          {template.description}
                        </p>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-xs px-2 py-0.5 bg-slate-800 text-slate-300 rounded border border-slate-700">
                            {template.category}
                          </span>
                          <span className="text-xs px-2 py-0.5 bg-slate-950/80 text-slate-300 rounded border border-slate-700">
                            {resolveTemplateOriginLabel(template)}
                          </span>
                          {resolveTemplateRuntimeLabel(template) && (
                            <span className="text-xs px-2 py-0.5 bg-amber-500/10 text-amber-200 rounded border border-amber-500/20">
                              {resolveTemplateRuntimeLabel(template)}
                            </span>
                          )}
                          {template.isLegacyStarterCopy && (
                            <span className="text-xs px-2 py-0.5 bg-amber-600/15 text-amber-100 rounded border border-amber-500/30">
                              遗留 Starter 副本
                            </span>
                          )}
                          <span className="text-xs text-slate-500">
                            {(template.config.nodes.length || template.estimatedNodeCount || 0)} 个节点
                          </span>
                          {template.sampleResultSummary?.hasResult && (
                            <span className="text-xs px-2 py-0.5 bg-emerald-500/20 text-emerald-200 rounded border border-emerald-500/30">
                              有结果样例
                            </span>
                          )}
                          {(template.sampleResultSummary?.videoCount || 0) > 0 && (
                            <span className="text-xs px-2 py-0.5 bg-sky-500/15 text-sky-200 rounded border border-sky-500/30">
                              视频 {(template.sampleResultSummary?.videoCount || 0)}
                            </span>
                          )}
                          {((template.sampleResultSummary?.videoExtensionApplied || 0) > 0
                            || (template.sampleResultSummary?.videoExtensionCount || 0) > 0) && (
                            <span className="text-xs px-2 py-0.5 bg-orange-500/15 text-orange-200 rounded border border-orange-500/30">
                              延长 {(template.sampleResultSummary?.videoExtensionApplied || template.sampleResultSummary?.videoExtensionCount || 0)}
                            </span>
                          )}
                          {(template.sampleResultSummary?.totalDurationSeconds || 0) > 0 && (
                            <span className="text-xs px-2 py-0.5 bg-cyan-500/15 text-cyan-200 rounded border border-cyan-500/30">
                              {(template.sampleResultSummary?.totalDurationSeconds || 0)}s
                            </span>
                          )}
                          {(((template.sampleResultSummary?.subtitleMode || '') !== '' && template.sampleResultSummary?.subtitleMode !== 'none')
                            || (template.sampleResultSummary?.subtitleFileCount || 0) > 0) && (
                            <span className="text-xs px-2 py-0.5 bg-emerald-500/15 text-emerald-200 rounded border border-emerald-500/30">
                              字幕{(template.sampleResultSummary?.subtitleFileCount || 0) > 0 ? ` · ${template.sampleResultSummary?.subtitleFileCount}` : ''}
                            </span>
                          )}
                          {(template.sampleResultSummary?.audioCount || 0) > 0 && (
                            <span className="text-xs px-2 py-0.5 bg-cyan-500/15 text-cyan-200 rounded border border-cyan-500/30">
                              音频 {(template.sampleResultSummary?.audioCount || 0)}
                            </span>
                          )}
                        </div>
                      </div>
                      <ChevronRight
                        size={20}
                        className={`flex-shrink-0 ml-2 ${
                          selectedTemplate?.id === template.id
                            ? 'text-teal-400'
                            : 'text-slate-500'
                        }`}
                      />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Template Preview */}
          <div className="w-1/2 overflow-y-auto bg-slate-900/40">
            {selectedTemplate ? (
              <div className="p-6 space-y-4">
                <div>
                  {editingTemplateId === selectedTemplate.id ? (
                    <div className="flex items-start gap-2 mb-2">
                      <input
                        type="text"
                        value={editingTemplateName}
                        onChange={(event) => setEditingTemplateName(event.target.value)}
                        className="flex-1 px-3 py-2 border border-slate-700 rounded-lg bg-slate-800 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500/50"
                        placeholder="输入模板标题"
                      />
                      <button
                        onClick={handleSaveTemplateTitle}
                        disabled={savingTemplateId === selectedTemplate.id}
                        className="px-3 py-2 text-xs bg-emerald-600 text-white rounded-lg hover:bg-emerald-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                        title="保存标题"
                      >
                        {savingTemplateId === selectedTemplate.id ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                        保存
                      </button>
                      <button
                        onClick={handleCancelRenameTemplate}
                        disabled={savingTemplateId === selectedTemplate.id}
                        className="px-3 py-2 text-xs bg-slate-800 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        title="取消编辑"
                      >
                        取消
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <h3 className="text-lg font-semibold text-slate-100">
                        {selectedTemplate.name}
                      </h3>
                      <button
                        onClick={handleStartRenameTemplate}
                        disabled={!canManageTemplate(selectedTemplate)}
                        className="px-2.5 py-1.5 text-xs bg-slate-800 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                        title={canManageTemplate(selectedTemplate) ? '编辑模板标题' : '只读模板不可编辑'}
                      >
                        <Pencil size={13} />
                        编辑标题
                      </button>
                    </div>
                  )}
                  <p className="text-sm text-slate-400">
                    {selectedTemplate.description}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs px-2 py-1 bg-teal-500/20 text-teal-200 border border-teal-500/30 rounded font-medium">
                    {selectedTemplate.category}
                  </span>
                  <span className="text-xs px-2 py-1 bg-slate-900 text-slate-200 border border-slate-700 rounded">
                    {resolveTemplateOriginLabel(selectedTemplate)}
                  </span>
                  {resolveTemplateRuntimeLabel(selectedTemplate) && (
                    <span className="text-xs px-2 py-1 bg-amber-500/10 text-amber-200 border border-amber-500/20 rounded">
                      {resolveTemplateRuntimeLabel(selectedTemplate)}
                    </span>
                  )}
                  {selectedTemplate.tags.map(tag => (
                    <span
                      key={tag}
                      className="text-xs px-2 py-1 bg-slate-800 text-slate-300 border border-slate-700 rounded"
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                {selectedTemplate.origin?.isLocked && (
                  <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-xs text-amber-100">
                    这是官方 Starter 模板。建议先复制后再编辑，系统会持续按 starter catalog 维护这类模板。
                  </div>
                )}
                {selectedTemplate.copiedFromStarterKey && !selectedTemplate.origin?.isLocked && (
                  <div className="p-3 rounded-lg border border-slate-700 bg-slate-950/60 text-xs text-slate-300">
                    当前模板来自 starter：<span className="text-slate-100">{selectedTemplate.copiedFromStarterKey}</span>
                  </div>
                )}
                {selectedTemplate.isLegacyStarterCopy && (
                  <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-xs text-amber-100">
                    这是遗留 Starter 副本：仍在通过 `agentName` 绑定旧 Seed Agent。建议复制官方新版 Starter，或改成 `agentId / inlineUseActiveProfile`。
                  </div>
                )}

                <div className="pt-4 border-t border-slate-700">
                  <h4 className="text-sm font-semibold text-slate-200 mb-3">工作流结构</h4>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">节点数量</span>
                      <span className="font-medium text-slate-200">
                        {(selectedTemplate.config.nodes.length || selectedTemplate.estimatedNodeCount || 0)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-400">连接数量</span>
                      <span className="font-medium text-slate-200">
                        {(selectedTemplate.config.edges.length || selectedTemplate.estimatedEdgeCount || 0)}
                      </span>
                    </div>
                    {selectedTemplate.bindingStrategy && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-400">绑定方式</span>
                        <span className="font-medium text-slate-200">
                          {selectedTemplate.bindingStrategy}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {(selectedTemplate.promptHint || selectedTemplate.promptExample) && (
                  <div className="pt-4 border-t border-slate-700">
                    <h4 className="text-sm font-semibold text-slate-200 mb-2">输入建议</h4>
                    {selectedTemplate.promptHint && (
                      <div className="text-xs text-slate-400 mb-2">{selectedTemplate.promptHint}</div>
                    )}
                    {selectedTemplate.promptExample && (
                      <pre className="text-[11px] text-slate-300 bg-slate-950/80 border border-slate-700 rounded p-2 whitespace-pre-wrap break-all">
                        {typeof selectedTemplate.promptExample === 'string'
                          ? selectedTemplate.promptExample
                          : JSON.stringify(selectedTemplate.promptExample, null, 2)}
                      </pre>
                    )}
                    {selectedTemplate.requiresImage && (
                      <div className="mt-2 text-[11px] text-amber-300">该流程需要输入参考图片（imageUrl）。</div>
                    )}
                  </div>
                )}

                <div className="pt-4 border-t border-slate-700">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-semibold text-slate-200">模板最近结果</h4>
                    {selectedTemplate.sampleResultUpdatedAt && (
                      <span className="text-[11px] text-slate-500">
                        {new Date(selectedTemplate.sampleResultUpdatedAt).toLocaleString()}
                      </span>
                    )}
                  </div>
                  {selectedTemplateHasSampleResult ? (
                    <div className="space-y-2">
                      {selectedTemplateSampleImageUrls.length > 0 && (
                        <div className={`grid gap-2 ${selectedTemplateSampleImageUrls.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
                          {selectedTemplateSampleImageUrls.map((imageUrl, index) => (
                            <img
                              key={`${selectedTemplate.id}-sample-image-${index}`}
                              src={imageUrl}
                              alt={`template-sample-${index + 1}`}
                              className="w-full h-24 rounded border border-slate-700 object-cover bg-slate-950/70"
                            />
                          ))}
                        </div>
                      )}
                      {selectedTemplateSampleVideoUrls.length > 0 && (
                        <div className="space-y-2">
                          <div className="text-xs text-slate-400 inline-flex items-center gap-1">
                            <Video size={12} />
                            视频结果（{selectedTemplateSampleVideoUrls.length}）
                          </div>
                          <div className="space-y-2">
                            {selectedTemplateSampleVideoUrls.map((videoUrl, index) => (
                              <video
                                key={`${selectedTemplate.id}-sample-video-${index}`}
                                src={videoUrl}
                                controls
                                className="w-full rounded border border-slate-700 bg-slate-950/70"
                              />
                            ))}
                          </div>
                        </div>
                      )}
                      {selectedTemplateSampleAudioUrls.length > 0 && (
                        <div className="space-y-2">
                          <div className="text-xs text-slate-400 inline-flex items-center gap-1">
                            <Mic size={12} />
                            音频结果（{selectedTemplateSampleAudioUrls.length}）
                          </div>
                          <div className="space-y-2">
                            {selectedTemplateSampleAudioUrls.map((audioUrl, index) => (
                              <audio
                                key={`${selectedTemplate.id}-sample-audio-${index}`}
                                src={audioUrl}
                                controls
                                className="w-full"
                              />
                            ))}
                          </div>
                        </div>
                      )}
                      {selectedTemplateSampleTextPreview && (
                        <pre className="text-[11px] text-slate-300 bg-slate-950/80 border border-slate-700 rounded p-2 whitespace-pre-wrap break-all max-h-[130px] overflow-y-auto">
                          {selectedTemplateSampleTextPreview}
                        </pre>
                      )}
                      {selectedTemplate.sampleResultSummary?.primaryRuntime && (
                        <div className="text-[11px] text-slate-500">
                          runtime: {selectedTemplate.sampleResultSummary.primaryRuntime}
                        </div>
                      )}
                      <div className="flex flex-wrap gap-1.5">
                        {((selectedTemplate.sampleResultSummary?.videoExtensionApplied || 0) > 0
                          || (selectedTemplate.sampleResultSummary?.videoExtensionCount || 0) > 0) && (
                          <span className="text-[11px] px-2 py-0.5 rounded border border-orange-500/30 bg-orange-500/10 text-orange-200">
                            延长 {selectedTemplate.sampleResultSummary?.videoExtensionApplied || selectedTemplate.sampleResultSummary?.videoExtensionCount} 次
                          </span>
                        )}
                        {(selectedTemplate.sampleResultSummary?.totalDurationSeconds || 0) > 0 && (
                          <span className="text-[11px] px-2 py-0.5 rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-200">
                            总时长 {selectedTemplate.sampleResultSummary?.totalDurationSeconds}s
                          </span>
                        )}
                        {(((selectedTemplate.sampleResultSummary?.subtitleMode || '') !== '' && selectedTemplate.sampleResultSummary?.subtitleMode !== 'none')
                          || (selectedTemplate.sampleResultSummary?.subtitleFileCount || 0) > 0) && (
                          <span className="text-[11px] px-2 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
                            字幕{(selectedTemplate.sampleResultSummary?.subtitleFileCount || 0) > 0 ? ` · ${selectedTemplate.sampleResultSummary?.subtitleFileCount}` : ''}
                          </span>
                        )}
                        {(selectedTemplate.sampleResultSummary?.continuedFromVideo
                          || Boolean(selectedTemplate.sampleResultSummary?.continuationStrategy)) && (
                          <span className="text-[11px] px-2 py-0.5 rounded border border-violet-500/30 bg-violet-500/10 text-violet-200">
                            {selectedTemplate.sampleResultSummary?.continuationStrategy === 'video_extension_chain' ? '官方续接' : '视频续接'}
                          </span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 border border-dashed border-slate-700 rounded p-2 bg-slate-800/30">
                      暂无模板结果。加载并执行一次该模板后，会自动写入结果快照用于快速预览。
                    </div>
                  )}
                </div>

                <div className="pt-4 border-t border-slate-700">
                  <h4 className="text-sm font-semibold text-slate-200 mb-3">节点列表</h4>
                  <div className="space-y-2 max-h-[200px] overflow-y-auto">
                    {selectedTemplate.config.nodes.length > 0 ? (
                      selectedTemplate.config.nodes.map(node => (
                        <div
                          key={node.id}
                          className="flex items-center gap-2 p-2 bg-slate-800/60 border border-slate-700 rounded text-sm"
                        >
                          <span className="text-lg">{node.data.icon}</span>
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-slate-100 truncate">
                              {node.data.label}
                            </div>
                            <div className="text-xs text-slate-500 truncate">
                              {node.data.description}
                            </div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-xs text-slate-500 p-2 border border-slate-700 rounded bg-slate-800/30">
                        模板未包含节点定义。
                      </div>
                    )}
                  </div>
                </div>

                <div className="pt-4 text-xs text-slate-500">
                  <div>创建时间: {new Date(selectedTemplate.createdAt).toLocaleString()}</div>
                  <div>更新时间: {new Date(selectedTemplate.updatedAt).toLocaleString()}</div>
                </div>
                {copyFeedback && (
                  <div
                    className={`text-xs ${
                      copyFeedback.startsWith('复制失败')
                        ? 'text-rose-300'
                        : 'text-emerald-300'
                    }`}
                  >
                    {copyFeedback}
                  </div>
                )}
                {templateActionFeedback && (
                  <div
                    className={`text-xs ${
                      templateActionFeedback.startsWith('删除失败') || templateActionFeedback.startsWith('更新失败')
                        ? 'text-rose-300'
                        : 'text-emerald-300'
                    }`}
                  >
                    {templateActionFeedback}
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-500">
                <div className="text-center">
                  <FileText size={48} className="mx-auto mb-2" />
                  <p>选择一个模板查看详情</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end p-4 border-t border-slate-700 bg-slate-900/80">
          <div className="inline-flex items-stretch rounded-lg border border-slate-700 overflow-hidden bg-slate-900">
            <button
              onClick={handleCopyTemplate}
              disabled={!selectedTemplate || Boolean(copyingTemplateId) || Boolean(deletingTemplateId)}
              className="px-3.5 py-1.5 text-xs text-slate-200 bg-slate-800 hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              {copyingTemplateId ? <Loader2 size={13} className="animate-spin" /> : <Copy size={13} />}
              复制模板
            </button>
            <button
              onClick={handleEditTemplate}
              disabled={!selectedTemplate || Boolean(copyingTemplateId) || Boolean(deletingTemplateId) || !canManageTemplate(selectedTemplate)}
              className="px-3.5 py-1.5 text-xs text-amber-100 bg-amber-900/30 hover:bg-amber-800/40 border-l border-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              title={selectedTemplate && !canManageTemplate(selectedTemplate) ? '只读模板不可直接编辑' : '加载到画布并进入编辑'}
            >
              <Pencil size={13} />
              编辑模板
            </button>
            <button
              onClick={handleRequestDeleteTemplate}
              disabled={!selectedTemplate || Boolean(deletingTemplateId) || !canManageTemplate(selectedTemplate)}
              className="px-3.5 py-1.5 text-xs text-rose-200 bg-rose-900/30 hover:bg-rose-800/40 border-l border-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              title={selectedTemplate && !canManageTemplate(selectedTemplate) ? '只读模板不可删除' : '删除模板'}
            >
              {deletingTemplateId ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
              删除模板
            </button>
            <button
              onClick={handleLoadTemplate}
              disabled={!selectedTemplate}
              className="px-3.5 py-1.5 text-xs text-white bg-teal-600 hover:bg-teal-500 border-l border-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              加载到画布
            </button>
            <button
              onClick={onClose}
              className="px-3.5 py-1.5 text-xs text-slate-300 bg-slate-800 hover:bg-slate-700 border-l border-slate-700 transition-colors"
            >
              取消
            </button>
          </div>
        </div>

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
                  {deletingTemplateId ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
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
