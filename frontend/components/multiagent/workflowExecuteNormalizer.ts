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
import { isPlainObject } from './workflowResultUtils';

const WORKFLOW_ALLOWED_AGENT_TASK_TYPES = new Set([
  'chat',
  'image-gen',
  'image-edit',
  'video-gen',
  'audio-gen',
  'vision-understand',
  'data-analysis',
]);

const WORKFLOW_ALLOWED_ANALYSIS_TYPES = new Set([
  'comprehensive',
  'statistics',
  'correlation',
  'trends',
  'distribution',
]);

const WORKFLOW_ALLOWED_IMAGE_EDIT_MODES = new Set([
  'image-chat-edit',
  'image-mask-edit',
  'image-inpainting',
  'image-background-edit',
  'image-recontext',
  'image-outpainting',
  'virtual-try-on',
]);

const WORKFLOW_ALLOWED_IMAGE_OUTPUT_MIME_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);

const WORKFLOW_ALLOWED_AUDIO_OUTPUT_FORMATS = new Set(['mp3', 'wav', 'opus', 'aac', 'flac', 'pcm']);

const WORKFLOW_ALLOWED_VIDEO_ASPECT_RATIOS = new Set(['16:9', '9:16']);

const WORKFLOW_ALLOWED_VIDEO_RESOLUTIONS = new Set(['720p', '1080p', '4k']);

const WORKFLOW_ALLOWED_VIDEO_SUBTITLE_MODES = new Set(['none', 'vtt', 'srt', 'both']);

const WORKFLOW_ALLOWED_OUTPUT_FORMATS = new Set(['text', 'json', 'markdown']);

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

const normalizeVideoResolutionForExecute = (value: unknown): string | null => {
  const raw = String(value || '').trim();
  if (!raw) return null;

  const normalized = raw.toLowerCase().replace(/\s+/g, '').replace(/\*/g, 'x').replace(/×/g, 'x');
  const aliases: Record<string, string> = {
    '1k': '720p',
    '720p': '720p',
    '1280': '720p',
    '1280x720': '720p',
    '720x1280': '720p',
    '2k': '1080p',
    '1080p': '1080p',
    '1920': '1080p',
    '1920x1080': '1080p',
    '1080x1920': '1080p',
    '4k': '4k',
    '2160p': '4k',
    '3840x2160': '4k',
    '2160x3840': '4k',
  };

  if (normalized in aliases) {
    return aliases[normalized];
  }
  if (WORKFLOW_ALLOWED_VIDEO_RESOLUTIONS.has(normalized)) {
    return normalized;
  }
  return null;
};

const normalizeAgentTaskTypeForExecute = (value: unknown): string => {
  const raw = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/_/g, '-');
  const aliases: Record<string, string> = {
    'vision-analyze': 'vision-understand',
    'image-analyze': 'vision-understand',
    'image-understand': 'vision-understand',
    'table-analysis': 'data-analysis',
    video: 'video-gen',
    'video-generate': 'video-gen',
    'video-generation': 'video-gen',
    audio: 'audio-gen',
    speech: 'audio-gen',
    tts: 'audio-gen',
    'speech-gen': 'audio-gen',
    'speech-generate': 'audio-gen',
    'speech-generation': 'audio-gen',
    'audio-generate': 'audio-gen',
    'audio-generation': 'audio-gen',
  };
  const normalized = aliases[raw] || raw;
  return WORKFLOW_ALLOWED_AGENT_TASK_TYPES.has(normalized) ? normalized : 'chat';
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

const normalizeImageEditModeForExecute = (value: unknown): string | null => {
  const normalized = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/_/g, '-');
  if (!normalized) return null;
  return WORKFLOW_ALLOWED_IMAGE_EDIT_MODES.has(normalized) ? normalized : null;
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
export const normalizeWorkflowInputForExecute = (
  rawInput: unknown,
  fallbackTask: string
): Record<string, unknown> => {
  const payload = isPlainObject(rawInput) ? { ...rawInput } : {};
  const task = String(payload.task || payload.prompt || payload.text || fallbackTask || '').trim();
  payload.task = task || String(fallbackTask || '').trim();

  let imageUrls = normalizeWorkflowStringList(payload.imageUrls);
  if (imageUrls.length === 0) {
    imageUrls = normalizeWorkflowStringList(payload.image_urls);
  }
  const singleImageUrl = String(payload.imageUrl || payload.image_url || '').trim();
  if (singleImageUrl) {
    imageUrls = normalizeWorkflowStringList([singleImageUrl, ...imageUrls]);
  }
  if (imageUrls.length > 0) {
    payload.imageUrls = imageUrls;
    payload.imageUrl = imageUrls[0];
  } else {
    delete payload.imageUrls;
    delete payload.imageUrl;
    delete payload.image_url;
  }

  let videoUrls = normalizeWorkflowStringList(payload.videoUrls);
  if (videoUrls.length === 0) {
    videoUrls = normalizeWorkflowStringList(payload.video_urls);
  }
  const singleVideoUrl = String(payload.videoUrl || payload.video_url || '').trim();
  if (singleVideoUrl) {
    videoUrls = normalizeWorkflowStringList([singleVideoUrl, ...videoUrls]);
  }
  if (videoUrls.length > 0) {
    payload.videoUrls = videoUrls;
    payload.videoUrl = videoUrls[0];
  } else {
    delete payload.videoUrls;
    delete payload.videoUrl;
    delete payload.video_url;
  }

  let audioUrls = normalizeWorkflowStringList(payload.audioUrls);
  if (audioUrls.length === 0) {
    audioUrls = normalizeWorkflowStringList(payload.audio_urls);
  }
  const singleAudioUrl = String(payload.audioUrl || payload.audio_url || '').trim();
  if (singleAudioUrl) {
    audioUrls = normalizeWorkflowStringList([singleAudioUrl, ...audioUrls]);
  }
  if (audioUrls.length > 0) {
    payload.audioUrls = audioUrls;
    payload.audioUrl = audioUrls[0];
  } else {
    delete payload.audioUrls;
    delete payload.audioUrl;
    delete payload.audio_url;
  }

  let fileUrls = normalizeWorkflowStringList(payload.fileUrls);
  if (fileUrls.length === 0) {
    fileUrls = normalizeWorkflowStringList(payload.file_urls);
  }
  const singleFileUrl = String(payload.fileUrl || payload.file_url || '').trim();
  if (singleFileUrl) {
    fileUrls = normalizeWorkflowStringList([singleFileUrl, ...fileUrls]);
  }
  if (fileUrls.length > 0) {
    payload.fileUrls = fileUrls;
    payload.fileUrl = fileUrls[0];
  } else {
    delete payload.fileUrls;
    delete payload.fileUrl;
    delete payload.file_url;
  }

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

  for (const fieldName of [
    'agentNumberOfImages',
    'toolNumberOfImages',
    'numberOfImages',
    'number_of_images',
  ]) {
    if (data[fieldName] === undefined) continue;
    const normalized = clampOptionalInt(data[fieldName], 1, 8);
    if (normalized === null) {
      delete data[fieldName];
    } else {
      data[fieldName] = normalized;
    }
  }

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

  for (const fieldName of ['agentOutputMimeType', 'toolOutputMimeType']) {
    if (data[fieldName] === undefined) continue;
    const normalized = normalizeOptionalChoice(
      data[fieldName],
      WORKFLOW_ALLOWED_IMAGE_OUTPUT_MIME_TYPES
    );
    if (!normalized) {
      delete data[fieldName];
    } else {
      data[fieldName] = normalized;
    }
  }

  for (const fieldName of ['agentOutputFormat', 'outputFormat']) {
    if (data[fieldName] === undefined) continue;
    const normalized = normalizeOptionalChoice(data[fieldName], WORKFLOW_ALLOWED_OUTPUT_FORMATS);
    if (!normalized) {
      delete data[fieldName];
    } else {
      data[fieldName] = normalized;
    }
  }

  for (const fieldName of ['toolEditMode', 'agentEditMode']) {
    if (data[fieldName] === undefined) continue;
    const normalized = normalizeImageEditModeForExecute(data[fieldName]);
    if (!normalized) {
      delete data[fieldName];
    } else {
      data[fieldName] = normalized;
    }
  }

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
    for (const fieldName of ['agentVideoDurationSeconds', 'agent_video_duration_seconds']) {
      if (data[fieldName] === undefined) continue;
      const normalized = clampOptionalInt(data[fieldName], 1, 20);
      if (normalized === null) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of ['agentVideoExtensionCount', 'agent_video_extension_count']) {
      if (data[fieldName] === undefined) continue;
      const normalized = clampOptionalInt(data[fieldName], 0, 20);
      if (normalized === null) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentVideoAspectRatio',
      'agent_video_aspect_ratio',
      'videoAspectRatio',
      'video_aspect_ratio',
      'agentAspectRatio',
      'agent_aspect_ratio',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalChoice(
        data[fieldName],
        WORKFLOW_ALLOWED_VIDEO_ASPECT_RATIOS
      );
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentVideoResolution',
      'agent_video_resolution',
      'videoResolution',
      'video_resolution',
      'agentResolutionTier',
      'agent_resolution_tier',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeVideoResolutionForExecute(data[fieldName]);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentContinueFromPreviousVideo',
      'agent_continue_from_previous_video',
      'agentContinueFromPreviousLastFrame',
      'agent_continue_from_previous_last_frame',
      'agentGenerateAudio',
      'agent_generate_audio',
      'generateAudio',
      'generate_audio',
    ]) {
      if (data[fieldName] === undefined) continue;
      data[fieldName] = Boolean(data[fieldName]);
    }

    for (const fieldName of ['agentSubtitleMode', 'agent_subtitle_mode']) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalChoice(
        data[fieldName],
        WORKFLOW_ALLOWED_VIDEO_SUBTITLE_MODES
      );
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of ['agentSubtitleLanguage', 'agent_subtitle_language']) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 32);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentSubtitleScript',
      'agent_subtitle_script',
      'agentStoryboardPrompt',
      'agent_storyboard_prompt',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 4000);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentSourceVideoUrl',
      'agent_source_video_url',
      'agentLastFrameImageUrl',
      'agent_last_frame_image_url',
      'agentVideoMaskImageUrl',
      'agent_video_mask_image_url',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 2048);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of ['agentVideoMaskMode', 'agent_video_mask_mode']) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 64);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }
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
    for (const fieldName of ['toolVideoDurationSeconds', 'tool_video_duration_seconds']) {
      if (data[fieldName] === undefined) continue;
      const normalized = clampOptionalInt(data[fieldName], 1, 20);
      if (normalized === null) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of ['toolVideoExtensionCount', 'tool_video_extension_count']) {
      if (data[fieldName] === undefined) continue;
      const normalized = clampOptionalInt(data[fieldName], 0, 20);
      if (normalized === null) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of ['toolAspectRatio', 'tool_aspect_ratio']) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalChoice(
        data[fieldName],
        WORKFLOW_ALLOWED_VIDEO_ASPECT_RATIOS
      );
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'toolResolutionTier',
      'tool_resolution_tier',
      'toolVideoResolution',
      'tool_video_resolution',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeVideoResolutionForExecute(data[fieldName]);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of ['toolGenerateAudio', 'tool_generate_audio']) {
      if (data[fieldName] === undefined) continue;
      data[fieldName] = Boolean(data[fieldName]);
    }

    for (const fieldName of ['toolSubtitleMode', 'tool_subtitle_mode']) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalChoice(
        data[fieldName],
        WORKFLOW_ALLOWED_VIDEO_SUBTITLE_MODES
      );
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of ['toolSubtitleLanguage', 'tool_subtitle_language']) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 32);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
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
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 4000);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of ['toolVideoMaskMode', 'tool_video_mask_mode']) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 64);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }
  }

  if (normalizedTaskType === 'audio-gen') {
    for (const fieldName of [
      'agentSpeechSpeed',
      'agent_speech_speed',
      'agentAudioSpeed',
      'agent_audio_speed',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = clampOptionalFloat(data[fieldName], 0.25, 4.0);
      if (normalized === null) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of [
      'agentAudioFormat',
      'agent_audio_format',
      'agentSpeechFormat',
      'agent_speech_format',
    ]) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalChoice(
        data[fieldName],
        WORKFLOW_ALLOWED_AUDIO_OUTPUT_FORMATS
      );
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }

    for (const fieldName of ['agentVoice', 'agent_voice']) {
      if (data[fieldName] === undefined) continue;
      const normalized = normalizeOptionalString(data[fieldName], 64);
      if (!normalized) {
        delete data[fieldName];
      } else {
        data[fieldName] = normalized;
      }
    }
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

