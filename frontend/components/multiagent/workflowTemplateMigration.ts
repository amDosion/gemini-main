/**
 * Workflow Template 旧版数据迁移（reverse-compat normalizer）。
 *
 * 1:1 抽离自 `WorkflowTemplateSelector.tsx` L166-452 migrateTemplate
 * （JIRA-frontend-deep-architecture-split.md #4 — 后端下沉候选）。
 *
 * 后端下沉说明：此 287 行迁移逻辑本质是兼容旧 API 响应格式。理想上后端
 * GET /api/templates 应返回已规范化数据，前端 migrateTemplate 可删除。本次先集中
 * 化到单独文件，便于未来一次性切换。
 */

import type { Node, Edge } from 'reactflow';
import { mergeRuntimeHints } from '../views/multiagent/runtimeHints';
import { CustomNodeData } from './CustomNode';
import {
  type WorkflowTemplate,
  normalizeTemplateSourceKind,
  normalizeTemplateRuntimeScope,
} from './workflowTemplateTypes';

export const migrateTemplate = (template: Record<string, unknown>): WorkflowTemplate => {
  const rawConfig = (template?.config || {}) as Record<string, unknown>;
  const rawOrigin = (template?.origin || {}) as Record<string, unknown>;
  const rawTemplateMeta = (rawConfig?._templateMeta || {}) as Record<string, unknown>;
  const rawNodes = Array.isArray(rawConfig.nodes) ? rawConfig.nodes : [];
  const rawEdges = Array.isArray(rawConfig.edges) ? rawConfig.edges : [];
  const migratedNodes = rawNodes.map((node: Record<string, unknown>) => ({
    ...(node as Record<string, unknown>),
    data: {
      ...((node?.data || {}) as Record<string, unknown>),
      type: (node?.data as Record<string, unknown>)?.type || node?.type || 'agent',
    },
  }));
  const migratedEdges = rawEdges;
  const rawTags = Array.isArray(template?.tags) ? template.tags : [];
  const estimatedNodeCount = Number(template?.estimatedNodeCount ?? rawNodes.length ?? 0) || 0;
  const estimatedEdgeCount = Number(template?.estimatedEdgeCount ?? rawEdges.length ?? 0) || 0;
  const rawSampleSummary = template?.sampleResultSummary as Record<string, unknown> | undefined;
  const sampleSummary =
    rawSampleSummary && typeof rawSampleSummary === 'object' && !Array.isArray(rawSampleSummary)
      ? {
          hasResult: Boolean(rawSampleSummary.hasResult),
          textPreview: String(rawSampleSummary.textPreview || '').trim(),
          imageCount:
            Number((rawSampleSummary.imageCount ?? rawSampleSummary.image_count) || 0) || 0,
          imageUrls: Array.isArray(rawSampleSummary.imageUrls)
            ? rawSampleSummary.imageUrls.filter((value: unknown) => typeof value === 'string')
            : Array.isArray(rawSampleSummary.image_urls)
              ? rawSampleSummary.image_urls.filter((value: unknown) => typeof value === 'string')
              : [],
          audioCount:
            Number((rawSampleSummary.audioCount ?? rawSampleSummary.audio_count) || 0) || 0,
          audioUrls: Array.isArray(rawSampleSummary.audioUrls)
            ? rawSampleSummary.audioUrls.filter((value: unknown) => typeof value === 'string')
            : Array.isArray(rawSampleSummary.audio_urls)
              ? rawSampleSummary.audio_urls.filter((value: unknown) => typeof value === 'string')
              : [],
          videoCount:
            Number((rawSampleSummary.videoCount ?? rawSampleSummary.video_count) || 0) || 0,
          videoUrls: Array.isArray(rawSampleSummary.videoUrls)
            ? rawSampleSummary.videoUrls.filter((value: unknown) => typeof value === 'string')
            : Array.isArray(rawSampleSummary.video_urls)
              ? rawSampleSummary.video_urls.filter((value: unknown) => typeof value === 'string')
              : [],
          runtimeHints: mergeRuntimeHints(
            [],
            Array.isArray(rawSampleSummary.runtimeHints) ? rawSampleSummary.runtimeHints : []
          ),
          primaryRuntime: String(rawSampleSummary.primaryRuntime || '').trim() || undefined,
          continuationStrategy:
            String(
              rawSampleSummary.continuationStrategy || rawSampleSummary.continuation_strategy || ''
            ).trim() || undefined,
          videoExtensionCount:
            Number(
              (rawSampleSummary.videoExtensionCount ?? rawSampleSummary.video_extension_count) || 0
            ) || 0,
          videoExtensionApplied:
            Number(
              (rawSampleSummary.videoExtensionApplied ??
                rawSampleSummary.video_extension_applied) ||
                0
            ) || 0,
          totalDurationSeconds:
            Number(
              (rawSampleSummary.totalDurationSeconds ?? rawSampleSummary.total_duration_seconds) ||
                0
            ) || 0,
          continuedFromVideo: Boolean(
            rawSampleSummary.continuedFromVideo ?? rawSampleSummary.continued_from_video ?? false
          ),
          subtitleMode:
            String(rawSampleSummary.subtitleMode || rawSampleSummary.subtitle_mode || '').trim() ||
            undefined,
          subtitleFileCount:
            Number(
              (rawSampleSummary.subtitleFileCount ?? rawSampleSummary.subtitle_file_count) || 0
            ) || 0,
        }
      : undefined;
  const rawSampleInput = template?.sampleInput as Record<string, unknown> | undefined;
  const sampleInput =
    rawSampleInput && typeof rawSampleInput === 'object' && !Array.isArray(rawSampleInput)
      ? {
          task: typeof rawSampleInput.task === 'string' ? rawSampleInput.task : undefined,
          prompt: typeof rawSampleInput.prompt === 'string' ? rawSampleInput.prompt : undefined,
          text: typeof rawSampleInput.text === 'string' ? rawSampleInput.text : undefined,
          imageUrl:
            typeof rawSampleInput.imageUrl === 'string' ? rawSampleInput.imageUrl : undefined,
          imageUrls: Array.isArray(rawSampleInput.imageUrls)
            ? rawSampleInput.imageUrls.filter((value: unknown) => typeof value === 'string')
            : undefined,
          videoUrl:
            typeof rawSampleInput.videoUrl === 'string'
              ? rawSampleInput.videoUrl
              : typeof rawSampleInput.video_url === 'string'
                ? rawSampleInput.video_url
                : undefined,
          videoUrls: Array.isArray(rawSampleInput.videoUrls)
            ? rawSampleInput.videoUrls.filter((value: unknown) => typeof value === 'string')
            : Array.isArray(rawSampleInput.video_urls)
              ? rawSampleInput.video_urls.filter((value: unknown) => typeof value === 'string')
              : undefined,
          audioUrl:
            typeof rawSampleInput.audioUrl === 'string'
              ? rawSampleInput.audioUrl
              : typeof rawSampleInput.audio_url === 'string'
                ? rawSampleInput.audio_url
                : undefined,
          audioUrls: Array.isArray(rawSampleInput.audioUrls)
            ? rawSampleInput.audioUrls.filter((value: unknown) => typeof value === 'string')
            : Array.isArray(rawSampleInput.audio_urls)
              ? rawSampleInput.audio_urls.filter((value: unknown) => typeof value === 'string')
              : undefined,
          prompts: Array.isArray(rawSampleInput.prompts)
            ? rawSampleInput.prompts.filter((value: unknown) => typeof value === 'string')
            : undefined,
          fileUrl: typeof rawSampleInput.fileUrl === 'string' ? rawSampleInput.fileUrl : undefined,
          fileUrls: Array.isArray(rawSampleInput.fileUrls)
            ? rawSampleInput.fileUrls.filter((value: unknown) => typeof value === 'string')
            : Array.isArray(rawSampleInput.file_urls)
              ? rawSampleInput.file_urls.filter((value: unknown) => typeof value === 'string')
              : undefined,
        }
      : undefined;
  const sampleResultUpdatedAt = Number(template?.sampleResultUpdatedAt || 0) || undefined;
  const starterKey =
    String(template?.starterKey ?? template?.starter_key ?? '').trim() || undefined;
  const starterVersion =
    Number(template?.starterVersion ?? template?.starter_version ?? 0) || undefined;
  const isStarter = Boolean(template?.isStarter ?? template?.is_starter ?? starterKey);
  const copiedFromStarterKey =
    String(template?.copiedFromStarterKey ?? template?.copied_from_starter_key ?? '').trim() ||
    undefined;
  const runtimeScope = normalizeTemplateRuntimeScope(
    template?.runtimeScope ??
      template?.runtime_scope ??
      rawOrigin?.runtimeScope ??
      rawOrigin?.runtime_scope
  );
  const runtimeLabel =
    String(
      template?.runtimeLabel ??
        template?.runtime_label ??
        rawOrigin?.runtimeLabel ??
        rawOrigin?.runtime_label ??
        ''
    ).trim() || undefined;
  const originKind = normalizeTemplateSourceKind(
    rawOrigin?.kind ??
      template?.originKind ??
      template?.origin_kind ??
      (isStarter ? 'starter' : template?.isPublic ? 'public' : 'user')
  );
  const originLabel =
    String(
      rawOrigin?.label ??
        template?.originLabel ??
        template?.origin_label ??
        (originKind === 'starter'
          ? '官方 Starter'
          : originKind === 'public'
            ? '公开模板'
            : '我的模板')
    ).trim() ||
    (originKind === 'starter' ? '官方 Starter' : originKind === 'public' ? '公开模板' : '我的模板');
  const originIsLocked = Boolean(
    rawOrigin?.isLocked ??
    rawOrigin?.is_locked ??
    template?.isLocked ??
    template?.is_locked ??
    isStarter
  );
  const rawTaskTypes =
    template?.taskTypes ??
    template?.task_types ??
    rawTemplateMeta?.taskTypes ??
    rawTemplateMeta?.task_types;
  const taskTypes = Array.isArray(rawTaskTypes)
    ? rawTaskTypes.filter((value: unknown) => typeof value === 'string')
    : [];
  const primaryTaskType =
    String(
      template?.primaryTaskType ??
        template?.primary_task_type ??
        rawTemplateMeta?.primaryTaskType ??
        rawTemplateMeta?.primary_task_type ??
        ''
    ).trim() || undefined;
  const bindingStrategy =
    String(
      template?.bindingStrategy ??
        template?.binding_strategy ??
        rawTemplateMeta?.bindingStrategy ??
        rawTemplateMeta?.binding_strategy ??
        ''
    ).trim() || undefined;
  const isLegacyStarterCopy = Boolean(
    template?.isLegacyStarterCopy ??
    template?.is_legacy_starter_copy ??
    rawTemplateMeta?.isLegacyStarterCopy ??
    rawTemplateMeta?.is_legacy_starter_copy
  );
  const legacyFlags = Array.isArray(
    template?.legacyFlags ??
      template?.legacy_flags ??
      rawTemplateMeta?.legacyFlags ??
      rawTemplateMeta?.legacy_flags
  )
    ? (
        (template?.legacyFlags ??
          template?.legacy_flags ??
          rawTemplateMeta?.legacyFlags ??
          rawTemplateMeta?.legacy_flags) as unknown[]
      ).filter((value: unknown) => typeof value === 'string')
    : [];
  const legacyReason =
    String(
      template?.legacyReason ??
        template?.legacy_reason ??
        rawTemplateMeta?.legacyReason ??
        rawTemplateMeta?.legacy_reason ??
        ''
    ).trim() || undefined;

  return {
    id: String(template?.id || ''),
    userId: typeof template?.userId === 'string' ? template.userId : undefined,
    name: String(template?.name || '未命名模板'),
    description: String(template?.description || ''),
    category: String(template?.category || '通用'),
    tags: rawTags,
    thumbnail: typeof template?.thumbnail === 'string' ? template.thumbnail : undefined,
    workflowType: String(template?.workflowType || 'graph'),
    version: typeof template?.version === 'number' ? template.version : undefined,
    isPublic: Boolean(template?.isPublic),
    modeId: String(template?.modeId || ''),
    promptHint: String(template?.promptHint ?? ''),
    promptExample: template?.promptExample as Record<string, unknown> | undefined,
    requiresImage: Boolean(template?.requiresImage),
    estimatedNodeCount,
    estimatedEdgeCount,
    sampleResult: template?.sampleResult as Record<string, unknown> | undefined,
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
      schemaVersion: Number(rawConfig?.schemaVersion || 2),
      nodes: migratedNodes as unknown as Node<CustomNodeData>[],
      edges: migratedEdges as Edge[],
    },
    createdAt: Number(template?.createdAt || Date.now()),
    updatedAt: Number(template?.updatedAt || Date.now()),
  };
};
