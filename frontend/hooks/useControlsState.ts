import { useState, useEffect } from 'react';
import { AppMode, LoraConfig, ModelConfig } from '../types/types';
import { DEFAULT_CONTROLS } from '../controls/constants';
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

  // Advanced Settings
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [negativePrompt, setNegativePrompt] = useState(DEFAULT_CONTROLS.negativePrompt);
  const [seed, setSeed] = useState(DEFAULT_CONTROLS.seed);
  const [loraConfig, setLoraConfig] = useState<LoraConfig>({ alpha: 0.6 });

  // Google Imagen Advanced Parameters
  const [guidanceScale, setGuidanceScale] = useState(DEFAULT_CONTROLS.guidanceScale);
  // personGeneration parameter removed - API uses default (allow_adult)
  const [outputMimeType, setOutputMimeType] = useState(DEFAULT_CONTROLS.outputMimeType);
  const [outputCompressionQuality, setOutputCompressionQuality] = useState(DEFAULT_CONTROLS.outputCompressionQuality);
  const [enhancePrompt, setEnhancePrompt] = useState(DEFAULT_CONTROLS.enhancePrompt);


  // Out-Painting
  const [outPaintingMode, setOutPaintingMode] = useState<'scale' | 'offset'>(DEFAULT_CONTROLS.outPaintingMode);
  const [scaleFactor, setScaleFactor] = useState(DEFAULT_CONTROLS.scaleFactor);
  const [offsetPixels, setOffsetPixels] = useState<OffsetPixels>(DEFAULT_CONTROLS.offsetPixels);


  // Audio
  const [voice, setVoice] = useState(DEFAULT_CONTROLS.voice);

  // PDF
  const [pdfTemplate, setPdfTemplate] = useState(DEFAULT_CONTROLS.pdfTemplate);
  const [pdfAdditionalInstructions, setPdfAdditionalInstructions] = useState(DEFAULT_CONTROLS.pdfAdditionalInstructions);

  // Virtual Try-On
  const [tryOnTarget, setTryOnTarget] = useState('upper');

  // Deep Research Controls
  const [thinkingSummaries, setThinkingSummaries] = useState<'auto' | 'none'>('auto');
  const [enableMultiAgent, setEnableMultiAgent] = useState(false);
  const [researchMode, setResearchMode] = useState<'vertex-ai' | 'gemini-api'>('vertex-ai');

  // Reset UI state when mode changes (only generic resets, no mode-specific logic)
  useEffect(() => {
    setShowAdvanced(false);
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
    guidanceScale, setGuidanceScale,
    // personGeneration removed - API uses default (allow_adult)
    outputMimeType, setOutputMimeType,
    outputCompressionQuality, setOutputCompressionQuality,
    enhancePrompt, setEnhancePrompt,


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
    tryOnTarget, setTryOnTarget,

    // Deep Research Controls
    thinkingSummaries, setThinkingSummaries,
    enableMultiAgent, setEnableMultiAgent,
    researchMode, setResearchMode,
  };
}

export default useControlsState;
