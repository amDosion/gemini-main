import { useState, useEffect } from 'react';
import { AppMode, LoraConfig, ModelConfig } from '../types/types';
import { ControlsState, OffsetPixels } from '../controls/types';

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
  const [generateAudio, setGenerateAudio] = useState(false);
  const [personGeneration, setPersonGeneration] = useState('');
  const [subtitleMode, setSubtitleMode] = useState('none');
  const [subtitleLanguage, setSubtitleLanguage] = useState('');
  const [subtitleScript, setSubtitleScript] = useState('');
  const [storyboardPrompt, setStoryboardPrompt] = useState('');
  const [numberOfImages, setNumberOfImages] = useState(1);
  const [style, setStyle] = useState('None');

  // Advanced Settings（默认展开）
  const [showAdvanced, setShowAdvanced] = useState(true);
  const [negativePrompt, setNegativePrompt] = useState('');
  const [seed, setSeed] = useState(-1);
  const [loraConfig, setLoraConfig] = useState<LoraConfig>({ alpha: 0.6 });

  // Google Imagen Advanced Parameters
  // guidanceScale removed - not officially documented by Google Imagen
  // personGeneration parameter removed - API uses default (allow_adult)
  const [outputMimeType, setOutputMimeType] = useState('image/png');
  const [outputCompressionQuality, setOutputCompressionQuality] = useState(80);
  const [enhancePrompt, setEnhancePrompt] = useState(false);
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

  // Sync with model capabilities
  useEffect(() => {
    if (currentModel) {
      if (!currentModel.capabilities.search && enableSearch) setEnableSearch(false);
      if (!currentModel.capabilities.reasoning && enableThinking) setEnableThinking(false);
    }
  }, [currentModel, enableSearch, enableThinking]);

  return {
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
    personGeneration, setPersonGeneration,
    subtitleMode, setSubtitleMode,
    subtitleLanguage, setSubtitleLanguage,
    subtitleScript, setSubtitleScript,
    storyboardPrompt, setStoryboardPrompt,
    numberOfImages, setNumberOfImages,
    style, setStyle,


    // Advanced Settings
    showAdvanced, setShowAdvanced,
    negativePrompt, setNegativePrompt,
    seed, setSeed,
    loraConfig, setLoraConfig,

    // Google Imagen Advanced Parameters
    // guidanceScale removed - not officially documented by Google Imagen
    // personGeneration removed - API uses default (allow_adult)
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
  };
}

export default useControlsState;
