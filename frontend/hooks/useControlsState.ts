import { useState, useEffect, useMemo, useRef } from 'react';
import { AppMode, LoraConfig, ModelConfig } from '../types/types';
import { ControlsState, OffsetPixels } from '../controls/types';

/**
 * Centralized controls state hook.
 *
 * Implementation notes (Wave 3 ARCH-D refactor):
 * - State is split into many independent `useState` calls (one per field).
 *   This means a change to one field only causes React to schedule a single
 *   re-render of this hook's host component, not invalidate an entire object.
 * - The returned aggregate object is memoized via `useMemo` keyed on every
 *   field value. When NO field changes between renders, the returned reference
 *   is stable — letting downstream `React.memo` children that receive
 *   `controls` as a prop bail out of re-rendering.
 * - `useState` setter identities are guaranteed stable by React, so consumer
 *   `useEffect` / `useCallback` deps that reference setters do not churn.
 * - The model-capability sync effect uses a ref-mirror of current values so
 *   the effect only re-runs when `currentModel` actually changes — not on
 *   every flip of enableSearch / enableThinking.
 *
 * External API surface (`ControlsState` in controls/types.ts) is unchanged.
 */
export function useControlsState(mode: AppMode, currentModel?: ModelConfig): ControlsState {
  // Chat Controls
  const [enableSearch, setEnableSearch] = useState(false);
  const [enableThinking, setEnableThinking] = useState(false);
  const [enableCodeExecution, setEnableCodeExecution] = useState(false);
  const [enableUrlContext, setEnableUrlContext] = useState(false);
  const [enableBrowser, setEnableBrowser] = useState(false);
  const [enableRAG, setEnableRAG] = useState(false);
  const [enableEnhancedRetrieval, setEnableEnhancedRetrieval] = useState(false);
  const [enableDeepResearch, setEnableDeepResearch] = useState(false);
  const [enableAutoDeepResearch, setEnableAutoDeepResearch] = useState(false);
  const [deepResearchAgentId, setDeepResearchAgentId] = useState('');
  const [googleCacheMode, setGoogleCacheMode] = useState<'none' | 'exact' | 'semantic'>('none');
  const [selectedMcpServerKey, setSelectedMcpServerKey] = useState('');

  // Generation Controls
  // Video-specific defaults are intentionally neutral placeholders.
  // Backend controls schema / video_contract is the source of truth.
  const [aspectRatio, setAspectRatio] = useState('1:1');
  const [resolution, setResolution] = useState('1K');
  const [videoSeconds, setVideoSeconds] = useState('');
  const [videoExtensionCount, setVideoExtensionCount] = useState(0);
  const [storyboardShotSeconds, setStoryboardShotSeconds] = useState(0);
  const [generateAudio, setGenerateAudio] = useState(true);
  const [subtitleMode, setSubtitleMode] = useState('none');
  const [subtitleLanguage, setSubtitleLanguage] = useState('');
  const [subtitleScript, setSubtitleScript] = useState('');
  const [storyboardPrompt, setStoryboardPrompt] = useState('');
  const [storyboardSegments, setStoryboardSegments] = useState<string[]>([]);
  const [numberOfImages, setNumberOfImages] = useState(1);
  const [style, setStyle] = useState('None');

  // Advanced Settings（默认展开）
  const [showAdvanced, setShowAdvanced] = useState(true);
  const [negativePrompt, setNegativePrompt] = useState('');
  const [seed, setSeed] = useState(-1);
  const [loraConfig, setLoraConfig] = useState<LoraConfig>({ alpha: 0.6 });

  // Google Imagen Advanced Parameters
  // guidanceScale removed - not officially documented by Google Imagen
  const [outputMimeType, setOutputMimeType] = useState('image/png');
  const [outputCompressionQuality, setOutputCompressionQuality] = useState(100);
  const [enhancePrompt, setEnhancePrompt] = useState(true);
  const [enhancePromptModel, setEnhancePromptModel] = useState('');

  // TongYi Specific Parameters
  const [promptExtend, setPromptExtend] = useState(false); // 阿里的 prompt_extend 参数
  const [addMagicSuffix, setAddMagicSuffix] = useState(true); // 阿里的 add_magic_suffix 参数（默认开启）


  // Out-Painting (旧参数，保留向后兼容)
  const [outPaintingMode, setOutPaintingMode] = useState<'scale' | 'offset'>('scale');
  const [scaleFactor, setScaleFactor] = useState(2.0);
  const [offsetPixels, setOffsetPixels] = useState<OffsetPixels>({ left: 0, right: 0, top: 0, bottom: 0 });

  // Out-Painting (新参数)
  const [outpaintMode, setOutpaintMode] = useState<'ratio' | 'scale' | 'offset' | 'upscale'>('ratio');
  const [xScale, setXScale] = useState(1.5);
  const [yScale, setYScale] = useState(1.5);
  const [upscaleFactor, setUpscaleFactor] = useState<'x2' | 'x3' | 'x4'>('x2');


  // Audio
  const [voice, setVoice] = useState('Puck');

  // PDF
  const [pdfTemplate, setPdfTemplate] = useState('invoice');
  const [pdfAdditionalInstructions, setPdfAdditionalInstructions] = useState('');

  // Virtual Try-On（官方支持参数；运行时由 schema 校正）
  // output_mime_type 和 output_compression_quality 使用固定默认值，不提供 UI
  const [baseSteps, setBaseSteps] = useState<number>(32);

  const [enableMultiAgent, setEnableMultiAgent] = useState(false);

  // Mask Edit Controls (仅用于 image-mask-edit 模式)
  const [editMode, setEditMode] = useState('EDIT_MODE_INPAINT_INSERTION');
  const [maskDilation, setMaskDilation] = useState(0.06);
  const [guidanceScale, setGuidanceScale] = useState(15.0);
  // Mask 模式 (对应 Vertex AI MaskReferenceConfig.mask_mode)
  const [maskMode, setMaskMode] = useState<'MASK_MODE_USER_PROVIDED' | 'MASK_MODE_BACKGROUND' | 'MASK_MODE_FOREGROUND' | 'MASK_MODE_SEMANTIC'>('MASK_MODE_USER_PROVIDED');

  // Reset UI state when mode changes (only generic resets, no mode-specific logic)
  // 高级参数保持默认展开状态
  useEffect(() => {
    setShowAdvanced(true);
  }, [mode]);

  // Sync with model capabilities.
  // Use a ref mirror for the boolean toggles so this effect only runs when
  // `currentModel` actually changes — flipping enableSearch / enableThinking
  // no longer re-fires the effect (and the previous `[currentModel, enableSearch, enableThinking]`
  // deps caused redundant work plus a subtle behavior where toggling the booleans
  // re-evaluated the capability check on every change).
  const toggleRef = useRef({ enableSearch, enableThinking });
  toggleRef.current.enableSearch = enableSearch;
  toggleRef.current.enableThinking = enableThinking;
  useEffect(() => {
    if (!currentModel) return;
    if (!currentModel.capabilities.search && toggleRef.current.enableSearch) {
      setEnableSearch(false);
    }
    if (!currentModel.capabilities.reasoning && toggleRef.current.enableThinking) {
      setEnableThinking(false);
    }
  }, [currentModel]);

  // Memoize the returned aggregate so the reference is stable across renders
  // when no field has changed. Children consuming `controls` through
  // React.memo can bail out of re-rendering in that case.
  //
  // All `setXxx` references come from `useState` which React guarantees stable,
  // so they are intentionally omitted from the dependency array.
  return useMemo<ControlsState>(
    () => ({
      // Chat Controls
      enableSearch, setEnableSearch,
      enableThinking, setEnableThinking,
      enableCodeExecution, setEnableCodeExecution,
      enableUrlContext, setEnableUrlContext,
      enableBrowser, setEnableBrowser,
      enableRAG, setEnableRAG,
      enableEnhancedRetrieval, setEnableEnhancedRetrieval,
      enableDeepResearch, setEnableDeepResearch,
      enableAutoDeepResearch, setEnableAutoDeepResearch,
      deepResearchAgentId, setDeepResearchAgentId,
      googleCacheMode, setGoogleCacheMode,
      selectedMcpServerKey, setSelectedMcpServerKey,

      // Generation Controls
      aspectRatio, setAspectRatio,
      resolution, setResolution,
      videoSeconds, setVideoSeconds,
      videoExtensionCount, setVideoExtensionCount,
      storyboardShotSeconds, setStoryboardShotSeconds,
      generateAudio, setGenerateAudio,
      subtitleMode, setSubtitleMode,
      subtitleLanguage, setSubtitleLanguage,
      subtitleScript, setSubtitleScript,
      storyboardPrompt, setStoryboardPrompt,
      storyboardSegments, setStoryboardSegments,
      numberOfImages, setNumberOfImages,
      style, setStyle,


      // Advanced Settings
      showAdvanced, setShowAdvanced,
      negativePrompt, setNegativePrompt,
      seed, setSeed,
      loraConfig, setLoraConfig,

      // Google Imagen Advanced Parameters
      // guidanceScale removed - not officially documented by Google Imagen
      outputMimeType, setOutputMimeType,
      outputCompressionQuality, setOutputCompressionQuality,
      enhancePrompt, setEnhancePrompt,
      enhancePromptModel, setEnhancePromptModel,

      // TongYi Specific Parameters
      promptExtend, setPromptExtend,
      addMagicSuffix, setAddMagicSuffix,


      // Out-Painting (旧参数，保留向后兼容)
      outPaintingMode, setOutPaintingMode,
      scaleFactor, setScaleFactor,
      offsetPixels, setOffsetPixels,

      // Out-Painting (新参数)
      outpaintMode, setOutpaintMode,
      xScale, setXScale,
      yScale, setYScale,
      upscaleFactor, setUpscaleFactor,

      // Audio
      voice, setVoice,

      // PDF
      pdfTemplate, setPdfTemplate,
      pdfAdditionalInstructions, setPdfAdditionalInstructions,

      // Virtual Try-On
      baseSteps, setBaseSteps,

      // Multi-Agent Controls
      enableMultiAgent, setEnableMultiAgent,

      // Mask Edit Controls
      editMode, setEditMode,
      maskDilation, setMaskDilation,
      guidanceScale, setGuidanceScale,
      maskMode, setMaskMode,
    }),
    [
      enableSearch, enableThinking, enableCodeExecution, enableUrlContext,
      enableBrowser, enableRAG, enableEnhancedRetrieval, enableDeepResearch,
      enableAutoDeepResearch, deepResearchAgentId, googleCacheMode, selectedMcpServerKey,
      aspectRatio, resolution, videoSeconds, videoExtensionCount, storyboardShotSeconds,
      generateAudio, subtitleMode, subtitleLanguage, subtitleScript,
      storyboardPrompt, storyboardSegments, numberOfImages, style,
      showAdvanced, negativePrompt, seed, loraConfig,
      outputMimeType, outputCompressionQuality, enhancePrompt, enhancePromptModel,
      promptExtend, addMagicSuffix,
      outPaintingMode, scaleFactor, offsetPixels,
      outpaintMode, xScale, yScale, upscaleFactor,
      voice,
      pdfTemplate, pdfAdditionalInstructions,
      baseSteps,
      enableMultiAgent,
      editMode, maskDilation, guidanceScale, maskMode,
    ],
  );
}

export default useControlsState;
