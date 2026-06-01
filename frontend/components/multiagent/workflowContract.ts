export type WorkflowAgentTaskType =
  | 'chat'
  | 'image-gen'
  | 'image-edit'
  | 'video-gen'
  | 'audio-gen'
  | 'vision-understand'
  | 'data-analysis';

export const WORKFLOW_AGENT_TASK_TYPES: WorkflowAgentTaskType[] = [
  'chat',
  'image-gen',
  'image-edit',
  'video-gen',
  'audio-gen',
  'vision-understand',
  'data-analysis',
];

const WORKFLOW_AGENT_TASK_SET = new Set<WorkflowAgentTaskType>(WORKFLOW_AGENT_TASK_TYPES);

const AGENT_TASK_TYPE_ALIASES: Record<string, WorkflowAgentTaskType> = {
  image_edit: 'image-edit',
  data_analysis: 'data-analysis',
  vision_understand: 'vision-understand',
  image_understand: 'vision-understand',
  vision_analyze: 'vision-understand',
  image_analyze: 'vision-understand',
  video: 'video-gen',
  video_generate: 'video-gen',
  video_generation: 'video-gen',
  audio: 'audio-gen',
  speech: 'audio-gen',
  tts: 'audio-gen',
  speech_gen: 'audio-gen',
  speech_generate: 'audio-gen',
  speech_generation: 'audio-gen',
  audio_generate: 'audio-gen',
  audio_generation: 'audio-gen',
};

export const WORKFLOW_NODE_TYPES = [
  'start',
  'end',
  'input_text',
  'input_image',
  'input_video',
  'input_audio',
  'input_file',
  'agent',
  'tool',
  'router',
  'parallel',
  'condition',
  'merge',
  'loop',
  'human',
] as const;

export const WORKFLOW_IMAGE_EDIT_MODES = [
  'image-chat-edit',
  'image-mask-edit',
  'image-inpainting',
  'image-background-edit',
  'image-recontext',
  'image-outpainting',
] as const;

const WORKFLOW_IMAGE_EDIT_MODE_SET = new Set<string>(WORKFLOW_IMAGE_EDIT_MODES);

const IMAGE_EDIT_MODE_ALIASES: Record<string, string> = {
  'image-chat': 'image-chat-edit',
  'chat-edit': 'image-chat-edit',
  'mask-edit': 'image-mask-edit',
  inpainting: 'image-inpainting',
  'background-edit': 'image-background-edit',
  background: 'image-background-edit',
  recontext: 'image-recontext',
  outpaint: 'image-outpainting',
  'image-outpaint': 'image-outpainting',
};

export const WORKFLOW_IMAGE_OUTPUT_MIME_TYPES = ['image/png', 'image/jpeg', 'image/webp'] as const;
export const WORKFLOW_AUDIO_OUTPUT_FORMATS = ['mp3', 'wav', 'opus', 'aac', 'flac', 'pcm'] as const;
export const WORKFLOW_OUTPUT_FORMATS = ['text', 'json', 'markdown'] as const;
export const WORKFLOW_VIDEO_ASPECT_RATIOS = ['16:9', '9:16'] as const;
export const WORKFLOW_VIDEO_RESOLUTIONS = ['720p', '1080p', '4k'] as const;
export const WORKFLOW_VIDEO_SUBTITLE_MODES = ['none', 'vtt', 'srt', 'both'] as const;
export const WORKFLOW_VIDEO_INPUT_STRATEGIES = [
  'text_to_video',
  'image_to_video',
  'first_last_frame',
  'video_extension',
  'masked_video_edit',
  'video_mask_edit',
  'first_frame_to_video',
  'first_last_frame_to_video',
  'video_continuation',
  'video_continuation_to_last_frame',
  'reference_to_video',
  'video_edit',
] as const;
export const WORKFLOW_VIDEO_MASK_MODES = ['INSERT', 'REMOVE', 'REMOVE_STATIC', 'OUTPAINT'] as const;

const VIDEO_RESOLUTION_ALIASES: Record<string, string> = {
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

const VIDEO_MASK_MODE_ALIASES: Record<string, string> = {
  INSERT: 'INSERT',
  REPLACE: 'INSERT',
  BACKGROUND: 'INSERT',
  BACKGROUND_REPLACE: 'INSERT',
  REMOVE: 'REMOVE',
  REMOVE_OBJECT: 'REMOVE',
  REMOVE_STATIC: 'REMOVE_STATIC',
  OUTPAINT: 'OUTPAINT',
};

const ACTIVE_INLINE_PROVIDER_TOKENS = new Set([
  '__active__',
  '__current__',
  'active',
  'current',
  'active-profile',
  'current-profile',
]);

const AUTO_INLINE_MODEL_TOKENS = new Set([
  '',
  '__auto__',
  '__active__',
  'auto',
  'active',
  'current',
  'active-profile',
  'current-profile',
]);

export const normalizeWorkflowAgentTaskType = (
  value: unknown,
  fallback: WorkflowAgentTaskType | null = 'chat'
): WorkflowAgentTaskType | null => {
  const token = String(value || '').trim().toLowerCase();
  if (!token) return fallback;
  const hyphenatedToken = token.replace(/_/g, '-');
  const normalized = (
    AGENT_TASK_TYPE_ALIASES[token] ||
    AGENT_TASK_TYPE_ALIASES[token.replace(/-/g, '_')] ||
    hyphenatedToken
  ) as WorkflowAgentTaskType;
  return WORKFLOW_AGENT_TASK_SET.has(normalized) ? normalized : fallback;
};

export const normalizeWorkflowImageEditMode = (value: unknown): string | null => {
  const raw = String(value || '').trim().toLowerCase().replace(/_/g, '-');
  if (!raw) return null;
  const normalized = IMAGE_EDIT_MODE_ALIASES[raw] || raw;
  return WORKFLOW_IMAGE_EDIT_MODE_SET.has(normalized) ? normalized : null;
};

export const normalizeWorkflowVideoResolution = (value: unknown): string | null => {
  const raw = String(value || '').trim();
  if (!raw) return null;
  const normalized = raw.toLowerCase().replace(/\s+/g, '').replace(/\*/g, 'x').replace(/×/g, 'x');
  return VIDEO_RESOLUTION_ALIASES[normalized] || null;
};

export const normalizeWorkflowVideoMaskMode = (value: unknown): string | null => {
  const raw = String(value || '').trim().toUpperCase().replace(/-/g, '_');
  if (!raw) return null;
  return VIDEO_MASK_MODE_ALIASES[raw] || null;
};

export const isActiveInlineProviderToken = (value: unknown): boolean =>
  ACTIVE_INLINE_PROVIDER_TOKENS.has(String(value || '').trim().toLowerCase());

export const isAutoInlineModelToken = (value: unknown): boolean =>
  AUTO_INLINE_MODEL_TOKENS.has(String(value || '').trim().toLowerCase());
