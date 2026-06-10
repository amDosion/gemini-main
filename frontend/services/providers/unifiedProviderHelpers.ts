/**
 * UnifiedProviderClient 内部常量 + 工具函数。
 *
 * 1:1 抽离自 `UnifiedProviderClient.ts` L31-244
 * （< 800 行合规拆分）。
 *
 * 包括：
 * - MODE_OPTION_KEYS / MODE_EXTRA_KEYS：模式调用允许的 ChatOptions 键集合
 * - pruneUndefinedEntries / isAbortError：通用 helper
 * - normalizeLegacyModeOptions：旧版字段命名兼容（如 size → resolution）
 * - pickAllowedEntries：白名单字段提取 + 跟踪被丢弃的键
 */

import type { ChatOptions } from '../../types/types';

// MODE_OPTION_KEYS 与 MODE_EXTRA_KEYS 历史上各自维护了一份允许键清单，二者重叠
// 41 个键（提示词增强、局部重绘偏移、OpenAI 通用、视频/分镜等）。这里抽出共享键，
// 再各自补充独有键，避免双份手维护时漏配/错配某个键（漏配会改变实际转发到 provider 的
// 字段，属可观察行为变更）。两个集合仅通过 `pickAllowedEntries` 的 `.has()` 消费，
// 从不被迭代/展开，故构造顺序不影响行为，只要成员集合一致即可。
const SHARED_MODE_KEYS = [
  'negativePrompt',
  'promptExtend',
  'addMagicSuffix',
  'thinkingMode',
  'enableSequential',
  'enhancePrompt',
  'enhancePromptModel',
  'enhancePromptThinkingLevel',
  'numberOfImages',
  'maskDilation',
  'guidanceScale',
  'outputMimeType',
  'outputCompressionQuality',
  'baseSteps',
  'maskMode',
  'segmentationClasses',
  'xScale',
  'yScale',
  'leftOffset',
  'rightOffset',
  'topOffset',
  'bottomOffset',
  'outputRatio',
  'upscaleFactor',
  'background',
  'moderation',
  'outputFormat',
  'outputCompression',
  'openaiPreviousResponseId',
  'voice',
  'videoExtensionCount',
  'videoInputStrategy',
  'storyboardShotSeconds',
  'generateAudio',
  'subtitleMode',
  'subtitleLanguage',
  'subtitleScript',
  'storyboardPrompt',
  'storyboardSegments',
  'trackedFeature',
  'trackingOverlayText',
];

const MODE_OPTION_ONLY_KEYS = [
  'baseUrl',
  'temperature',
  'maxTokens',
  'topP',
  'topK',
  'enableSearch',
  'enableThinking',
  'enableCodeExecution',
  'enableBrowser',
  'enableGrounding',
  'size',
  'quality',
  'style',
  'seconds',
  'aspectRatio',
  'resolution',
  'imageAspectRatio',
  'imageResolution',
  'imageStyle',
  'editMode',
  'frontendSessionId',
  'sessionId',
  'messageId',
  'activeImageUrl',
  'seed',
  'outpaintMode',
  'layers',
  'canvasW',
  'canvasH',
  'maxTextBoxes',
  'locale',
  'layerDoc',
  'simplifyTolerance',
  'smoothIterations',
  'useBezier',
  'bezierSmoothness',
  'threshold',
  'blurRadius',
  'pdfExtractTemplate',
  'pdfAdditionalInstructions',
];

const MODE_EXTRA_ONLY_KEYS = [
  'workflow',
  'messages',
  'targetClothing',
  'templateType',
  'additionalInstructions',
  'pdfBytes',
  'pdfUrl',
  'n',
  'numImages',
  'angle',
  'watermark',
  'responseFormat',
];

export const MODE_OPTION_KEYS = new Set([...SHARED_MODE_KEYS, ...MODE_OPTION_ONLY_KEYS]);

export const MODE_EXTRA_KEYS = new Set([...SHARED_MODE_KEYS, ...MODE_EXTRA_ONLY_KEYS]);

export function pruneUndefinedEntries(source: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(source).filter(([, value]) => value !== undefined && value !== null)
  );
}

export function isAbortError(error: unknown): boolean {
  return (
    !!error &&
    typeof error === 'object' &&
    'name' in error &&
    (error as { name?: unknown }).name === 'AbortError'
  );
}

export function normalizeLegacyModeOptions(
  mode: string,
  options: Partial<ChatOptions>
): Record<string, unknown> {
  const normalized = pruneUndefinedEntries({ ...(options || {}) });

  if (
    mode === 'image-outpainting' &&
    normalized.outPainting &&
    typeof normalized.outPainting === 'object'
  ) {
    const legacyOutPainting = normalized.outPainting as Record<string, unknown>;
    if (normalized.outpaintMode === undefined && legacyOutPainting.mode !== undefined) {
      normalized.outpaintMode = legacyOutPainting.mode;
    }
    if (normalized.xScale === undefined && legacyOutPainting.xScale !== undefined) {
      normalized.xScale = legacyOutPainting.xScale;
    }
    if (normalized.yScale === undefined && legacyOutPainting.yScale !== undefined) {
      normalized.yScale = legacyOutPainting.yScale;
    }
    if (normalized.leftOffset === undefined && legacyOutPainting.leftOffset !== undefined) {
      normalized.leftOffset = legacyOutPainting.leftOffset;
    }
    if (normalized.rightOffset === undefined && legacyOutPainting.rightOffset !== undefined) {
      normalized.rightOffset = legacyOutPainting.rightOffset;
    }
    if (normalized.topOffset === undefined && legacyOutPainting.topOffset !== undefined) {
      normalized.topOffset = legacyOutPainting.topOffset;
    }
    if (normalized.bottomOffset === undefined && legacyOutPainting.bottomOffset !== undefined) {
      normalized.bottomOffset = legacyOutPainting.bottomOffset;
    }
    if (normalized.outputRatio === undefined && legacyOutPainting.outputRatio !== undefined) {
      normalized.outputRatio = legacyOutPainting.outputRatio;
    }
    if (normalized.outputRatio === undefined && legacyOutPainting.aspectRatio !== undefined) {
      normalized.outputRatio = legacyOutPainting.aspectRatio;
    }
    if (normalized.upscaleFactor === undefined && legacyOutPainting.upscaleFactor !== undefined) {
      normalized.upscaleFactor = legacyOutPainting.upscaleFactor;
    }
  }

  delete normalized.outPainting;
  delete normalized.multiAgentConfig;
  delete normalized.liveAPIConfig;
  delete normalized.persona;
  delete normalized.deepResearchAgentId;
  delete normalized.enableAutoDeepResearch;
  delete normalized.enableUrlContext;
  delete normalized.enableEnhancedRetrieval;
  delete normalized.enableDeepResearch;
  delete normalized.enableRAG;
  delete normalized.googleCacheMode;
  delete normalized.useGoogleFilesApi;
  delete normalized.loraConfig;
  delete normalized.enableUpscale;
  delete normalized.addWatermark;
  delete normalized.prompt;
  delete normalized.modelId;
  delete normalized.language;
  delete normalized.platform;
  return normalized;
}

export function pickAllowedEntries(
  source: Record<string, unknown>,
  allowedKeys: Set<string>
): { kept: Record<string, unknown>; droppedKeys: string[] } {
  const kept: Record<string, unknown> = {};
  const droppedKeys: string[] = [];

  for (const [key, value] of Object.entries(source)) {
    if (value === undefined || value === null) {
      continue;
    }
    if (allowedKeys.has(key)) {
      kept[key] = value;
    } else {
      droppedKeys.push(key);
    }
  }

  return { kept, droppedKeys: droppedKeys.sort() };
}
