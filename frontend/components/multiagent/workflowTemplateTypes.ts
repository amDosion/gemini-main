/**
 * Workflow Template 类型 + 来源/runtime 解析辅助函数。
 *
 * 1:1 抽离自 `WorkflowTemplateSelector.tsx` L33-175
 * （< 800 行合规拆分）。
 *
 * 类型先前为模块内未导出，现 export 给同模块 + 测试访问。
 */

import { Node, Edge } from 'reactflow';
import { CustomNodeData } from './CustomNode';

export interface WorkflowTemplateResultSummary {
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

export interface WorkflowTemplateSampleInput {
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

export type WorkflowTemplateSourceKind = 'all' | 'user' | 'starter' | 'public';

export interface WorkflowTemplateOrigin {
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
  promptExample?: Record<string, unknown>;
  requiresImage?: boolean;
  estimatedNodeCount?: number;
  estimatedEdgeCount?: number;
  sampleResult?: Record<string, unknown>;
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

export const normalizeTemplateSourceKind = (value: unknown): Exclude<WorkflowTemplateSourceKind, 'all'> => {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'starter') return 'starter';
  if (normalized === 'public') return 'public';
  return 'user';
};

export const normalizeTemplateRuntimeScope = (value: unknown): string | undefined => {
  const normalized = String(value || '').trim();
  return normalized || undefined;
};

export const resolveTemplateOriginKind = (template: WorkflowTemplate): Exclude<WorkflowTemplateSourceKind, 'all'> => {
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

export const resolveTemplateOriginLabel = (template: WorkflowTemplate): string => {
  if (template.origin?.label) {
    return template.origin.label;
  }
  const originKind = resolveTemplateOriginKind(template);
  if (originKind === 'starter') return '官方 Starter';
  if (originKind === 'public') return '公开模板';
  return '我的模板';
};

export const resolveTemplateRuntimeLabel = (template: WorkflowTemplate): string | undefined => {
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
