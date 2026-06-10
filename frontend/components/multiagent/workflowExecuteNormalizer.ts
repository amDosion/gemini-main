/**
 * Workflow 节点数据归一化（执行前预处理）。
 *
 * 1:1 抽离自 `workflowEditorUtils.ts` L718-1231
 * （< 800 行合规拆分）。
 *
 * 用途：将 React Flow 节点数据（含媒体附件 URL / 表单字段）转换为后端可执行的
 * 输入结构。处理：URL 数组 / 单 URL 字段双向兼容、媒体附件去重、token 修剪等。
 */

import type { WorkflowNodeData } from './types';
import {
  WORKFLOW_AUDIO_OUTPUT_FORMATS,
  WORKFLOW_IMAGE_OUTPUT_MIME_TYPES,
  WORKFLOW_OUTPUT_FORMATS,
  WORKFLOW_VIDEO_ASPECT_RATIOS,
  WORKFLOW_VIDEO_INPUT_STRATEGIES,
  WORKFLOW_VIDEO_SUBTITLE_MODES,
  normalizeWorkflowAgentTaskType,
  normalizeWorkflowImageEditMode,
  normalizeWorkflowVideoMaskMode,
  normalizeWorkflowVideoResolution,
} from './workflowContract';
import { isPlainObject } from './workflowResultUtils';

const WORKFLOW_ALLOWED_ANALYSIS_TYPES = new Set([
  'comprehensive',
  'statistics',
  'correlation',
  'trends',
  'distribution',
]);

const WORKFLOW_ALLOWED_IMAGE_OUTPUT_MIME_TYPES = new Set<string>(WORKFLOW_IMAGE_OUTPUT_MIME_TYPES);

const WORKFLOW_ALLOWED_AUDIO_OUTPUT_FORMATS = new Set<string>(WORKFLOW_AUDIO_OUTPUT_FORMATS);

const WORKFLOW_ALLOWED_VIDEO_ASPECT_RATIOS = new Set<string>(WORKFLOW_VIDEO_ASPECT_RATIOS);

const WORKFLOW_ALLOWED_VIDEO_SUBTITLE_MODES = new Set<string>(WORKFLOW_VIDEO_SUBTITLE_MODES);

const WORKFLOW_ALLOWED_VIDEO_INPUT_STRATEGIES = new Set<string>(WORKFLOW_VIDEO_INPUT_STRATEGIES);

const WORKFLOW_ALLOWED_OUTPUT_FORMATS = new Set<string>(WORKFLOW_OUTPUT_FORMATS);

const normalizeWorkflowStringList = (value: unknown, maxItems = 12): string[] => {
  if (!Array.isArray(value)) return [];
  const deduped = new Set<string>();
  const normalized: string[] = [];
  for (const item of value) {
    const text = String(item || '').trim();
    if (!text || deduped.has(text)) continue;
    deduped.add(text);
    normalized.push(text);
    if (normalized.length >= maxItems) break;
  }
  return normalized;
};

const clampOptionalInt = (value: unknown, minimum: number, maximum: number): number | null => {
  if (value === undefined || value === null || value === '') return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  const integer = Math.trunc(parsed);
  return Math.max(minimum, Math.min(maximum, integer));
};

const clampOptionalFloat = (value: unknown, minimum: number, maximum: number): number | null => {
  if (value === undefined || value === null || value === '') return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return Math.max(minimum, Math.min(maximum, parsed));
};

const normalizeOptionalChoice = (value: unknown, allowed: Set<string>): string | null => {
  const text = String(value || '')
    .trim()
    .toLowerCase();
  if (!text) return null;
  return allowed.has(text) ? text : null;
};

const normalizeOptionalString = (value: unknown, maxLength = 128): string | null => {
  const text = String(value || '').trim();
  if (!text) return null;
  return text.length > maxLength ? text.slice(0, maxLength) : text;
};

// Apply `normalize` to each present field: drop the field when normalization
// yields null, otherwise overwrite with the normalized value. Mirrors the
// per-field guard repeated throughout the execute normalizers. Every normalizer
// used here returns `T | null` (clamp helpers can legitimately return 0, which
// must be kept — hence the strict `=== null` check rather than a falsy check).
const assignNormalizedFields = <T>(
  data: Record<string, unknown>,
  fieldNames: readonly string[],
  normalize: (value: unknown) => T | null
): void => {
  for (const fieldName of fieldNames) {
    if (data[fieldName] === undefined) continue;
    const normalized = normalize(data[fieldName]);
    if (normalized === null) {
      delete data[fieldName];
    } else {
      data[fieldName] = normalized;
    }
  }
};

// Coerce each present field to a strict boolean in place.
const coerceBooleanFields = (
  data: Record<string, unknown>,
  fieldNames: readonly string[]
): void => {
  for (const fieldName of fieldNames) {
    if (data[fieldName] === undefined) continue;
    data[fieldName] = Boolean(data[fieldName]);
  }
};

const normalizeAgentTaskTypeForExecute = (value: unknown): string => {
  return normalizeWorkflowAgentTaskType(value, 'chat') || 'chat';
};

const normalizeAnalysisTypeForExecute = (value: unknown): string => {
  const raw = String(value || '')
    .trim()
    .toLowerCase();
  const aliases: Record<string, string> = {
    summary: 'statistics',
    stats: 'statistics',
    statistic: 'statistics',
    trend: 'trends',
    anomaly: 'distribution',
    anomalies: 'distribution',
    all: 'comprehensive',
  };
  const normalized = aliases[raw] || raw;
  return WORKFLOW_ALLOWED_ANALYSIS_TYPES.has(normalized) ? normalized : 'comprehensive';
};

const normalizeNodeSizeForExecute = (
  value: unknown,
  minimum: number,
  maximum: number
): number | undefined => {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return undefined;
  return Math.max(minimum, Math.min(maximum, Math.round(parsed)));
};

// Reconcile a media URL group with camelCase/snake_case list + single-URL
// aliases into a canonical `{ listKey, singleKey }` pair (or removes them all
// when empty). Mutates `payload` in place.
const reconcileUrlGroup = (
  payload: Record<string, unknown>,
  listKey: string,
  listSnakeKey: string,
  singleKey: string,
  singleSnakeKey: string
): void => {
  let urls = normalizeWorkflowStringList(payload[listKey]);
  if (urls.length === 0) {
    urls = normalizeWorkflowStringList(payload[listSnakeKey]);
  }
  const single = String(payload[singleKey] || payload[singleSnakeKey] || '').trim();
  if (single) {
    urls = normalizeWorkflowStringList([single, ...urls]);
  }
  if (urls.length > 0) {
    payload[listKey] = urls;
    payload[singleKey] = urls[0];
  } else {
    delete payload[listKey];
    delete payload[singleKey];
    delete payload[singleSnakeKey];
  }
};
export const normalizeWorkflowInputForExecute = (
  rawInput: unknown,
  fallbackTask: string
): Record<string, unknown> => {
  const payload = isPlainObject(rawInput) ? { ...rawInput } : {};
  const task = String(payload.task || payload.prompt || payload.text || fallbackTask || '').trim();
  payload.task = task || String(fallbackTask || '').trim();

  reconcileUrlGroup(payload, 'imageUrls', 'image_urls', 'imageUrl', 'image_url');
  reconcileUrlGroup(payload, 'videoUrls', 'video_urls', 'videoUrl', 'video_url');
  reconcileUrlGroup(payload, 'audioUrls', 'audio_urls', 'audioUrl', 'audio_url');
  reconcileUrlGroup(payload, 'fileUrls', 'file_urls', 'fileUrl', 'file_url');

  if (payload.analysisType !== undefined) {
    payload.analysisType = normalizeAnalysisTypeForExecute(payload.analysisType);
  }
  if (payload.analysis_type !== undefined) {
    payload.analysis_type = normalizeAnalysisTypeForExecute(payload.analysis_type);
  }

  return payload;
};

export const normalizeWorkflowNodeDataForExecute = (
  rawData: Partial<WorkflowNodeData> & Record<string, unknown>
): Record<string, unknown> => {
  const data: Record<string, unknown> = isPlainObject(rawData) ? { ...rawData } : {};

  const taskType = data.agentTaskType ?? data.agent_task_type;
  let normalizedTaskType = '';
  if (taskType !== undefined) {
    normalizedTaskType = normalizeAgentTaskTypeForExecute(taskType);
    data.agentTaskType = normalizedTaskType;
    data.agent_task_type = normalizedTaskType;
  }

  const analysisTypeCandidates = [
    'toolAnalysisType',
    'tool_analysis_type',
    'analysisType',
    'analysis_type',
  ];
  for (const fieldName of analysisTypeCandidates) {
    if (data[fieldName] !== undefined) {
      data[fieldName] = normalizeAnalysisTypeForExecute(data[fieldName]);
    }
  }

  assignNormalizedFields(
    data,
    ['agentNumberOfImages', 'toolNumberOfImages', 'numberOfImages', 'number_of_images'],
    (value) => clampOptionalInt(value, 1, 8)
  );

  if (data.agentImageEditMaxRetries !== undefined) {
    const retries = clampOptionalInt(data.agentImageEditMaxRetries, 0, 3);
    data.agentImageEditMaxRetries = retries === null ? 1 : retries;
  }
  if (data.agent_image_edit_max_retries !== undefined) {
    const retries = clampOptionalInt(data.agent_image_edit_max_retries, 0, 3);
    data.agent_image_edit_max_retries = retries === null ? 1 : retries;
  }

  if (data.agentProductMatchThreshold !== undefined) {
    const threshold = clampOptionalInt(data.agentProductMatchThreshold, 50, 95);
    data.agentProductMatchThreshold = threshold === null ? 70 : threshold;
  }
  if (data.agent_product_match_threshold !== undefined) {
    const threshold = clampOptionalInt(data.agent_product_match_threshold, 50, 95);
    data.agent_product_match_threshold = threshold === null ? 70 : threshold;
  }

  assignNormalizedFields(data, ['agentOutputMimeType', 'toolOutputMimeType'], (value) =>
    normalizeOptionalChoice(value, WORKFLOW_ALLOWED_IMAGE_OUTPUT_MIME_TYPES)
  );

  assignNormalizedFields(data, ['agentOutputFormat', 'outputFormat'], (value) =>
    normalizeOptionalChoice(value, WORKFLOW_ALLOWED_OUTPUT_FORMATS)
  );

  assignNormalizedFields(data, ['toolEditMode', 'agentEditMode'], normalizeWorkflowImageEditMode);

  for (const [listField, singleField] of [
    ['startImageUrls', 'startImageUrl'],
    ['startVideoUrls', 'startVideoUrl'],
    ['startAudioUrls', 'startAudioUrl'],
    ['startFileUrls', 'startFileUrl'],
  ]) {
    let listValues = normalizeWorkflowStringList(data[listField]);
    const singleValue = String(data[singleField] || '').trim();
    if (singleValue) {
      listValues = normalizeWorkflowStringList([singleValue, ...listValues]);
    }
    if (listValues.length > 0) {
      data[listField] = listValues;
      data[singleField] = listValues[0];
    } else {
      delete data[listField];
      delete data[singleField];
    }
  }

  if (normalizedTaskType === 'video-gen') {
    assignNormalizedFields(
      data,
      ['agentVideoDurationSeconds', 'agent_video_duration_seconds'],
      (value) => clampOptionalInt(value, 1, 20)
    );

    assignNormalizedFields(
      data,
      ['agentVideoExtensionCount', 'agent_video_extension_count'],
      (value) => clampOptionalInt(value, 0, 20)
    );

    assignNormalizedFields(
      data,
      [
        'agentVideoAspectRatio',
        'agent_video_aspect_ratio',
        'videoAspectRatio',
        'video_aspect_ratio',
        'agentAspectRatio',
        'agent_aspect_ratio',
      ],
      (value) => normalizeOptionalChoice(value, WORKFLOW_ALLOWED_VIDEO_ASPECT_RATIOS)
    );

    assignNormalizedFields(
      data,
      [
        'agentVideoResolution',
        'agent_video_resolution',
        'videoResolution',
        'video_resolution',
        'agentResolutionTier',
        'agent_resolution_tier',
      ],
      normalizeWorkflowVideoResolution
    );

    coerceBooleanFields(data, [
      'agentContinueFromPreviousVideo',
      'agent_continue_from_previous_video',
      'agentContinueFromPreviousLastFrame',
      'agent_continue_from_previous_last_frame',
      'agentGenerateAudio',
      'agent_generate_audio',
      'generateAudio',
      'generate_audio',
    ]);

    assignNormalizedFields(data, ['agentSubtitleMode', 'agent_subtitle_mode'], (value) =>
      normalizeOptionalChoice(value, WORKFLOW_ALLOWED_VIDEO_SUBTITLE_MODES)
    );

    assignNormalizedFields(
      data,
      ['agentVideoInputStrategy', 'agent_video_input_strategy'],
      (value) => normalizeOptionalChoice(value, WORKFLOW_ALLOWED_VIDEO_INPUT_STRATEGIES)
    );

    assignNormalizedFields(data, ['agentSubtitleLanguage', 'agent_subtitle_language'], (value) =>
      normalizeOptionalString(value, 32)
    );

    assignNormalizedFields(
      data,
      [
        'agentSubtitleScript',
        'agent_subtitle_script',
        'agentStoryboardPrompt',
        'agent_storyboard_prompt',
      ],
      (value) => normalizeOptionalString(value, 4000)
    );

    assignNormalizedFields(
      data,
      [
        'agentSourceVideoUrl',
        'agent_source_video_url',
        'agentLastFrameImageUrl',
        'agent_last_frame_image_url',
        'agentVideoMaskImageUrl',
        'agent_video_mask_image_url',
        'agentAudioUrl',
        'agent_audio_url',
      ],
      (value) => normalizeOptionalString(value, 2048)
    );

    assignNormalizedFields(
      data,
      ['agentVideoMaskMode', 'agent_video_mask_mode'],
      normalizeWorkflowVideoMaskMode
    );
  }

  const normalizedToolName = String(data.toolName || data.tool_name || '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_');
  if (
    normalizedToolName === 'video_generate' ||
    normalizedToolName === 'generate_video' ||
    normalizedToolName === 'video_gen'
  ) {
    assignNormalizedFields(
      data,
      ['toolVideoDurationSeconds', 'tool_video_duration_seconds'],
      (value) => clampOptionalInt(value, 1, 20)
    );

    assignNormalizedFields(
      data,
      ['toolVideoExtensionCount', 'tool_video_extension_count'],
      (value) => clampOptionalInt(value, 0, 20)
    );

    assignNormalizedFields(data, ['toolAspectRatio', 'tool_aspect_ratio'], (value) =>
      normalizeOptionalChoice(value, WORKFLOW_ALLOWED_VIDEO_ASPECT_RATIOS)
    );

    assignNormalizedFields(
      data,
      [
        'toolResolutionTier',
        'tool_resolution_tier',
        'toolVideoResolution',
        'tool_video_resolution',
      ],
      normalizeWorkflowVideoResolution
    );

    coerceBooleanFields(data, ['toolGenerateAudio', 'tool_generate_audio']);

    assignNormalizedFields(data, ['toolSubtitleMode', 'tool_subtitle_mode'], (value) =>
      normalizeOptionalChoice(value, WORKFLOW_ALLOWED_VIDEO_SUBTITLE_MODES)
    );

    assignNormalizedFields(data, ['toolSubtitleLanguage', 'tool_subtitle_language'], (value) =>
      normalizeOptionalString(value, 32)
    );

    assignNormalizedFields(
      data,
      [
        'toolSubtitleScript',
        'tool_subtitle_script',
        'toolStoryboardPrompt',
        'tool_storyboard_prompt',
        'toolSourceVideoUrl',
        'tool_source_video_url',
        'toolLastFrameImageUrl',
        'tool_last_frame_image_url',
        'toolVideoMaskImageUrl',
        'tool_video_mask_image_url',
      ],
      (value) => normalizeOptionalString(value, 4000)
    );

    assignNormalizedFields(
      data,
      ['toolVideoMaskMode', 'tool_video_mask_mode'],
      normalizeWorkflowVideoMaskMode
    );
  }

  if (normalizedTaskType === 'audio-gen') {
    assignNormalizedFields(
      data,
      ['agentSpeechSpeed', 'agent_speech_speed', 'agentAudioSpeed', 'agent_audio_speed'],
      (value) => clampOptionalFloat(value, 0.25, 4.0)
    );

    assignNormalizedFields(
      data,
      ['agentAudioFormat', 'agent_audio_format', 'agentSpeechFormat', 'agent_speech_format'],
      (value) => normalizeOptionalChoice(value, WORKFLOW_ALLOWED_AUDIO_OUTPUT_FORMATS)
    );

    assignNormalizedFields(data, ['agentVoice', 'agent_voice'], (value) =>
      normalizeOptionalString(value, 64)
    );
  }

  const nodeWidth = normalizeNodeSizeForExecute(data.nodeWidth, 135, 720);
  if (nodeWidth !== undefined) {
    data.nodeWidth = nodeWidth;
  } else if (data.nodeWidth !== undefined) {
    delete data.nodeWidth;
  }

  const nodeHeight = normalizeNodeSizeForExecute(data.nodeHeight, 1, 1200);
  if (nodeHeight !== undefined) {
    data.nodeHeight = nodeHeight;
  } else if (data.nodeHeight !== undefined) {
    delete data.nodeHeight;
  }

  return data;
};
