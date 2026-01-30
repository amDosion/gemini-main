import { useState, useEffect } from 'react';
import { AppMode, LoraConfig, ModelConfig } from '../types/types';
import { DEFAULT_CONTROLS } from '../controls/constants/index';
import { TRYON_DEFAULTS } from '../controls/constants/tryon';
import { ControlsState, OffsetPixels } from '../controls/types';

export function useControlsState(mode: AppMode, currentModel?: ModelConfig): ControlsState {
  // Chat Controls
  const [enableSearch, setEnableSearch] = useState(false);
  const [enableThinking, setEnableThinking] = useState(false);
  const [enableCodeExecution, setEnableCodeExecution] = useState(false);
  const [enableUrlContext, setEnableUrlContext] = useState(false);
  const [enableBrowser, setEnableBrowser] = useState(false);
  const [enableRAG, setEnableRAG] = useState(false);
  const [enableResearch, setEnableResearch] = useState(false);
  const [googleCacheMode, setGoogleCacheMode] = useState<'none' | 'exact' | 'semantic'>('none');

  // Generation Controls
  const [aspectRatio, setAspectRatio] = useState(DEFAULT_CONTROLS.aspectRatio);
  const [resolution, setResolution] = useState(DEFAULT_CONTROLS.resolution);
  const [numberOfImages, setNumberOfImages] = useState(DEFAULT_CONTROLS.numberOfImages);
  const [style, setStyle] = useState(DEFAULT_CONTROLS.style);

  // Advanced Settings（默认展开）
  const [showAdvanced, setShowAdvanced] = useState(true);
  const [negativePrompt, setNegativePrompt] = useState(DEFAULT_CONTROLS.negativePrompt);
  const [seed, setSeed] = useState(DEFAULT_CONTROLS.seed);
  const [loraConfig, setLoraConfig] = useState<LoraConfig>({ alpha: 0.6 });

  // Google Imagen Advanced Parameters
  // guidanceScale removed - not officially documented by Google Imagen
  // personGeneration parameter removed - API uses default (allow_adult)
  const [outputMimeType, setOutputMimeType] = useState(DEFAULT_CONTROLS.outputMimeType);
  const [outputCompressionQuality, setOutputCompressionQuality] = useState(DEFAULT_CONTROLS.outputCompressionQuality);
  const [enhancePrompt, setEnhancePrompt] = useState(DEFAULT_CONTROLS.enhancePrompt);
  const [enhancePromptModel, setEnhancePromptModel] = useState(DEFAULT_CONTROLS.enhancePromptModel);

  // TongYi Specific Parameters
  const [promptExtend, setPromptExtend] = useState(false); // 阿里的 prompt_extend 参数
  const [addMagicSuffix, setAddMagicSuffix] = useState(true); // 阿里的 add_magic_suffix 参数（默认开启）


  // Out-Painting
  const [outPaintingMode, setOutPaintingMode] = useState<'scale' | 'offset'>(DEFAULT_CONTROLS.outPaintingMode);
  const [scaleFactor, setScaleFactor] = useState(DEFAULT_CONTROLS.scaleFactor);
  const [offsetPixels, setOffsetPixels] = useState<OffsetPixels>(DEFAULT_CONTROLS.offsetPixels);


  // Audio
  const [voice, setVoice] = useState(DEFAULT_CONTROLS.voice);

  // PDF
  const [pdfTemplate, setPdfTemplate] = useState(DEFAULT_CONTROLS.pdfTemplate);
  const [pdfAdditionalInstructions, setPdfAdditionalInstructions] = useState(DEFAULT_CONTROLS.pdfAdditionalInstructions);

  // Virtual Try-On（官方支持的参数，默认值见 constants/tryon）
  // output_mime_type 和 output_compression_quality 使用固定默认值，不提供 UI
  const [baseSteps, setBaseSteps] = useState<number>(TRYON_DEFAULTS.baseSteps);

  // Deep Research Controls
  const [thinkingSummaries, setThinkingSummaries] = useState<'auto' | 'none'>('auto');
  const [enableMultiAgent, setEnableMultiAgent] = useState(false);
  const [researchMode, setResearchMode] = useState<'vertex-ai' | 'gemini-api'>('vertex-ai');

  // Mask Edit Controls (仅用于 image-mask-edit 模式)
  const [editMode, setEditMode] = useState(DEFAULT_CONTROLS.editMode);
  const [maskDilation, setMaskDilation] = useState(DEFAULT_CONTROLS.maskDilation);
  const [guidanceScale, setGuidanceScale] = useState(DEFAULT_CONTROLS.guidanceScale);
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
    enableResearch, setEnableResearch,
    googleCacheMode, setGoogleCacheMode,

    // Generation Controls
    aspectRatio, setAspectRatio,
    resolution, setResolution,
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


    // Out-Painting
    outPaintingMode, setOutPaintingMode,
    scaleFactor, setScaleFactor,
    offsetPixels, setOffsetPixels,

    // Audio
    voice, setVoice,

    // PDF
    pdfTemplate, setPdfTemplate,
    pdfAdditionalInstructions, setPdfAdditionalInstructions,

    // Virtual Try-On
    baseSteps, setBaseSteps,

    // Deep Research Controls
    thinkingSummaries, setThinkingSummaries,
    enableMultiAgent, setEnableMultiAgent,
    researchMode, setResearchMode,

    // Mask Edit Controls
    editMode, setEditMode,
    maskDilation, setMaskDilation,
    guidanceScale, setGuidanceScale,
    maskMode, setMaskMode,
  };
}

export default useControlsState;
