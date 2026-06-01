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

export const MODE_OPTION_KEYS = new Set([
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
  'voice',
  'size',
  'quality',
  'style',
  'background',
  'moderation',
  'outputFormat',
  'outputCompression',
  'openaiPreviousResponseId',
  'seconds',
  'videoInputStrategy',
  'videoExtensionCount',
  'storyboardShotSeconds',
  'generateAudio',
  'subtitleMode',
  'subtitleLanguage',
  'subtitleScript',
  'storyboardPrompt',
  'storyboardSegments',
  'trackedFeature',
  'trackingOverlayText',
  'numberOfImages',
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
  'negativePrompt',
  'guidanceScale',
  'maskDilation',
  'seed',
  'outputMimeType',
  'outputCompressionQuality',
  'enhancePrompt',
  'enhancePromptModel',
  'enhancePromptThinkingLevel',
  'promptExtend',
  'addMagicSuffix',
  'thinkingMode',
  'enableSequential',
  'outpaintMode',
  'xScale',
  'yScale',
  'leftOffset',
  'rightOffset',
  'topOffset',
  'bottomOffset',
  'outputRatio',
  'upscaleFactor',
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
  'baseSteps',
  'maskMode',
  'segmentationClasses',
  'pdfExtractTemplate',
  'pdfAdditionalInstructions',
]);

export const MODE_EXTRA_KEYS = new Set([
  'workflow',
  'messages',
  'targetClothing',
  'templateType',
  'additionalInstructions',
  'pdfBytes',
  'pdfUrl',
  'n',
  'numImages',
  'numberOfImages',
  'negativePrompt',
  'promptExtend',
  'addMagicSuffix',
  'thinkingMode',
  'enableSequential',
  'enhancePrompt',
  'enhancePromptModel',
  'enhancePromptThinkingLevel',
  'maskDilation',
  'guidanceScale',
  'outputMimeType',
  'outputCompressionQuality',
  'xScale',
  'yScale',
  'leftOffset',
  'rightOffset',
  'topOffset',
  'bottomOffset',
  'outputRatio',
  'upscaleFactor',
  'angle',
  'watermark',
  'responseFormat',
  'background',
  'moderation',
  'outputFormat',
  'outputCompression',
  'openaiPreviousResponseId',
  'voice',
  'baseSteps',
  'maskMode',
  'segmentationClasses',
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
]);

export function pruneUndefinedEntries(source: Record<string, any>): Record<string, any> {
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

export function normalizeLegacyModeOptions(mode: string, options: Partial<ChatOptions>): Record<string, any> {
  const normalized = pruneUndefinedEntries({ ...(options || {}) });

  if (mode === 'image-outpainting' && normalized.outPainting && typeof normalized.outPainting === 'object') {
    const legacyOutPainting = normalized.outPainting as Record<string, any>;
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
  source: Record<string, any>,
  allowedKeys: Set<string>
): { kept: Record<string, any>; droppedKeys: string[] } {
  const kept: Record<string, any> = {};
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
