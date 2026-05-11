/**
 * Tool 节点分类：根据 toolName 推导任务类型 + UI 显示标志。
 *
 * 1:1 抽离自 `PropertiesPanel.tsx` L2393-2444
 * （JIRA-frontend-view-decomposition.md P0 #1 续 — 业务下沉准备）。
 *
 * TODO（后端下沉）：当前 alias 列表硬编码在前端（'image_edit' / 'edit_image' / ... 等多种写法），
 *   应改为后端 `/api/agents/tool-registry` 返回结构化 taxonomy：
 *     { canonicalName, aliases, taskType, capabilities: { modelOverride, providerOverride, ... } }
 *   后端定义一次，前端各处统一消费 — 避免前后端不同步导致的"alias 漏写"bug。
 *   本次仅做前端集中化（便于未来一次性替换），暂保留 1:1 行为。
 */

import type { AgentTaskType } from './providerModelUtils';

export interface ToolClassification {
  /** 规范化后的 toolName（lower-case，连字符转下划线） */
  normalizedToolName: string;

  // 8 个 boolean 标志，覆盖当前已知 tool 类别
  isImageGen: boolean;
  isImageEdit: boolean;
  isVideoGenerate: boolean;
  isVideoUnderstand: boolean;
  isVideoDelete: boolean;
  isPromptOptimize: boolean;
  isTableAnalyze: boolean;
  isAmazonAdsOptimize: boolean;

  /** 推导的 agent 任务类型（用于 modelSupportsTask 校验） */
  taskType: AgentTaskType;

  /** 是否显示模型 override 选择器 */
  shouldShowToolModelOverride: boolean;

  /** 是否显示 provider override 选择器（比 model override 多覆盖 video_delete） */
  shouldShowToolProviderOverride: boolean;
}

const IMAGE_GEN_ALIASES = ['image_generate', 'generate_image', 'image_gen'];
const IMAGE_EDIT_ALIASES = [
  'image_edit',
  'edit_image',
  'image_chat_edit',
  'image_mask_edit',
  'image_inpainting',
  'image_background_edit',
  'image_recontext',
  'image_outpaint',
  'image_outpainting',
  'expand_image',
];
const VIDEO_GEN_ALIASES = ['video_generate', 'generate_video', 'video_gen'];
const VIDEO_UNDERSTAND_ALIASES = ['video_understand', 'understand_video'];
const VIDEO_DELETE_ALIASES = ['video_delete', 'delete_video'];
const PROMPT_OPTIMIZE_ALIASES = [
  'prompt_optimize',
  'prompt_optimizer',
  'optimize_prompt',
  'prompt_rewrite',
  'rewrite_prompt',
];
const TABLE_ANALYZE_ALIASES = [
  'table_analyze',
  'excel_analyze',
  'analyze_table',
  'sheet_analyze',
  'sheet_profile',
];
const AMAZON_ADS_OPTIMIZE_ALIASES = [
  'amazon_ads_keyword_optimize',
  'amazon_ads_optimize',
  'ads_keyword_optimize',
  'amazon_ppc_optimize',
  'amazon_search_term_optimize',
];

/**
 * 将 tool 节点的 toolName 字段分类为 UI 行为需要的全部 boolean + taskType 集合。
 * 调用方一次解构所有标志，避免分散在 render 逻辑中。
 */
export function classifyToolNode(rawToolName: string | undefined | null): ToolClassification {
  const normalizedToolName = (rawToolName || '').trim().toLowerCase().replace(/-/g, '_');

  const isImageGen = IMAGE_GEN_ALIASES.includes(normalizedToolName);
  const isImageEdit = IMAGE_EDIT_ALIASES.includes(normalizedToolName);
  const isVideoGenerate = VIDEO_GEN_ALIASES.includes(normalizedToolName);
  const isVideoUnderstand = VIDEO_UNDERSTAND_ALIASES.includes(normalizedToolName);
  const isVideoDelete = VIDEO_DELETE_ALIASES.includes(normalizedToolName);
  const isPromptOptimize = PROMPT_OPTIMIZE_ALIASES.includes(normalizedToolName);
  const isTableAnalyze = TABLE_ANALYZE_ALIASES.includes(normalizedToolName);
  const isAmazonAdsOptimize = AMAZON_ADS_OPTIMIZE_ALIASES.includes(normalizedToolName);

  const taskType: AgentTaskType = isImageEdit
    ? 'image-edit'
    : isImageGen
      ? 'image-gen'
      : isVideoGenerate
        ? 'video-gen'
        : isVideoUnderstand
          ? 'vision-understand'
          : 'chat';

  const shouldShowToolModelOverride =
    isImageGen || isImageEdit || isPromptOptimize || isVideoGenerate || isVideoUnderstand;
  const shouldShowToolProviderOverride = shouldShowToolModelOverride || isVideoDelete;

  return {
    normalizedToolName,
    isImageGen,
    isImageEdit,
    isVideoGenerate,
    isVideoUnderstand,
    isVideoDelete,
    isPromptOptimize,
    isTableAnalyze,
    isAmazonAdsOptimize,
    taskType,
    shouldShowToolModelOverride,
    shouldShowToolProviderOverride,
  };
}
