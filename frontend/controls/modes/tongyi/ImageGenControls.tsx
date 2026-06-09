/**
 * 通义图像生成专用控件（仅 Panel 模式）
 * 支持 wan2.x-t2i / z-image-turbo / wan2.6-image 系列模型
 */
import React, { useEffect, useMemo } from 'react';
import {
  BrainCircuit,
  Palette,
  Ratio,
  Maximize2,
  ChevronUp,
  ChevronDown,
  Dices,
  Wand2,
  Layers,
} from 'lucide-react';
import { ControlsState } from '../../types';
import { ModelConfig } from '../../../types/types';
import {
  getPixelResolutionFromSchema,
  useModeControlsSchema,
} from '../../../hooks/useModeControlsSchema';
import { useEnhancePromptModels } from '../../../hooks/useEnhancePromptModels';
import PromptEnhanceControl from '../../shared/PromptEnhanceControl';
import FeatureToggleControl from '../../shared/FeatureToggleControl';
import ImageCountSliderControl from '../../shared/ImageCountSliderControl';
import {
  getBooleanDefault,
  getUnsupportedParams,
  supportsBooleanParam,
} from '../../shared/modeControlSchemaUtils';

export interface ImageGenControlsProps {
  providerId?: string;
  currentModel?: { id: string; name?: string };
  controls?: ControlsState;
  availableModels?: ModelConfig[];
  style?: string;
  setStyle?: (v: string) => void;
  numberOfImages?: number;
  setNumberOfImages?: (v: number) => void;
  aspectRatio?: string;
  setAspectRatio?: (v: string) => void;
  resolution?: string;
  setResolution?: (v: string) => void;
  showAdvanced?: boolean;
  setShowAdvanced?: (v: boolean) => void;
  seed?: number;
  setSeed?: (v: number) => void;
  negativePrompt?: string;
  setNegativePrompt?: (v: string) => void;
  promptExtend?: boolean;
  setPromptExtend?: (v: boolean) => void;
  enhancePrompt?: boolean;
  setEnhancePrompt?: (v: boolean) => void;
  addMagicSuffix?: boolean;
  setAddMagicSuffix?: (v: boolean) => void;
  enableSequential?: boolean;
  setEnableSequential?: (v: boolean) => void;
}

export const ImageGenControls: React.FC<ImageGenControlsProps> = ({
  providerId = 'tongyi',
  currentModel,
  controls,
  style: propStyle,
  setStyle: propSetStyle,
  numberOfImages: propNumberOfImages,
  setNumberOfImages: propSetNumberOfImages,
  aspectRatio: propAspectRatio,
  setAspectRatio: propSetAspectRatio,
  resolution: propResolution,
  setResolution: propSetResolution,
  showAdvanced: propShowAdvanced,
  setShowAdvanced: propSetShowAdvanced,
  seed: propSeed,
  setSeed: propSetSeed,
  negativePrompt: propNegativePrompt,
  setNegativePrompt: propSetNegativePrompt,
  promptExtend: propPromptExtend,
  setPromptExtend: propSetPromptExtend,
  enhancePrompt: propEnhancePrompt,
  setEnhancePrompt: propSetEnhancePrompt,
  addMagicSuffix: propAddMagicSuffix,
  setAddMagicSuffix: propSetAddMagicSuffix,
  enableSequential: propEnableSequential,
  setEnableSequential: propSetEnableSequential,
}) => {
  const modelId = currentModel?.id || '';
  const { schema, loading, error } = useModeControlsSchema(providerId, 'image-gen', modelId);
  const defaults = schema?.defaults ?? {};
  const unsupportedParams = useMemo(() => getUnsupportedParams(schema), [schema]);
  const supportsStyle = !unsupportedParams.has('style');
  const supportsNegativePrompt = !unsupportedParams.has('negative_prompt');
  const supportsLocalPromptEnhance = !unsupportedParams.has('enhance_prompt');
  const supportsAddMagicSuffix = !unsupportedParams.has('add_magic_suffix');
  const supportsThinkingMode =
    !unsupportedParams.has('thinking_mode') && supportsBooleanParam(schema, 'thinking_mode');
  const supportsSequentialMode =
    !unsupportedParams.has('enable_sequential') &&
    supportsBooleanParam(schema, 'enable_sequential');

  const styleOptions = useMemo(
    () => (schema?.paramOptions?.style ?? []).filter((option) => typeof option.value === 'string'),
    [schema]
  );
  const imageCountOptions = useMemo(
    () =>
      (schema?.paramOptions?.number_of_images ?? [])
        .map((option) => option.value)
        .filter((value): value is number => typeof value === 'number'),
    [schema]
  );
  const seedRange = schema?.numericRanges?.seed;

  const defaultStyle =
    (typeof defaults.style === 'string' ? defaults.style : undefined) ??
    (typeof styleOptions[0]?.value === 'string' ? styleOptions[0].value : undefined) ??
    'None';
  const defaultImageCount =
    (typeof defaults.number_of_images === 'number' ? defaults.number_of_images : undefined) ??
    imageCountOptions[0] ??
    1;
  const defaultAspectRatio =
    typeof defaults.aspect_ratio === 'string' ? defaults.aspect_ratio : '1:1';
  const defaultResolution = typeof defaults.resolution === 'string' ? defaults.resolution : '1.25K';
  const defaultSeed = typeof defaults.seed === 'number' ? defaults.seed : -1;
  const defaultNegativePrompt =
    typeof defaults.negative_prompt === 'string' ? defaults.negative_prompt : '';
  const defaultPromptExtend =
    typeof defaults.prompt_extend === 'boolean' ? defaults.prompt_extend : false;
  const defaultEnhancePrompt =
    typeof defaults.enhance_prompt === 'boolean' ? defaults.enhance_prompt : false;
  const defaultAddMagicSuffix =
    typeof defaults.add_magic_suffix === 'boolean' ? defaults.add_magic_suffix : true;
  const defaultThinkingMode = getBooleanDefault(schema, 'thinking_mode', true);
  const defaultEnableSequential = getBooleanDefault(schema, 'enable_sequential', false);

  const style = controls?.style ?? propStyle ?? defaultStyle;
  const setStyle = controls?.setStyle ?? propSetStyle ?? (() => {});
  const numberOfImages = controls?.numberOfImages ?? propNumberOfImages ?? defaultImageCount;
  const setNumberOfImages = controls?.setNumberOfImages ?? propSetNumberOfImages ?? (() => {});
  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? defaultAspectRatio;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? (() => {});
  const resolution = controls?.resolution ?? propResolution ?? defaultResolution;
  const setResolution = controls?.setResolution ?? propSetResolution ?? (() => {});
  const showAdvanced = controls?.showAdvanced ?? propShowAdvanced ?? true;
  const setShowAdvanced = controls?.setShowAdvanced ?? propSetShowAdvanced ?? (() => {});
  const seed = controls?.seed ?? propSeed ?? defaultSeed;
  const setSeed = controls?.setSeed ?? propSetSeed ?? (() => {});
  const negativePrompt = controls?.negativePrompt ?? propNegativePrompt ?? defaultNegativePrompt;
  const setNegativePrompt = controls?.setNegativePrompt ?? propSetNegativePrompt ?? (() => {});
  const promptExtend = controls?.promptExtend ?? propPromptExtend ?? defaultPromptExtend;
  const setPromptExtend = controls?.setPromptExtend ?? propSetPromptExtend ?? (() => {});
  const enhancePrompt =
    controls?.enhancePrompt ?? propEnhancePrompt ?? promptExtend ?? defaultEnhancePrompt;
  const setEnhancePrompt = controls?.setEnhancePrompt ?? propSetEnhancePrompt ?? setPromptExtend;
  const enhancePromptModel = controls?.enhancePromptModel ?? '';
  const setEnhancePromptModel = controls?.setEnhancePromptModel;
  const enhancePromptThinkingLevel = controls?.enhancePromptThinkingLevel ?? 'auto';
  const setEnhancePromptThinkingLevel = controls?.setEnhancePromptThinkingLevel;
  const enhancePromptModels = useEnhancePromptModels(providerId, undefined, {
    requiresVision: true,
    includeHidden: true,
  });
  const addMagicSuffix = controls?.addMagicSuffix ?? propAddMagicSuffix ?? defaultAddMagicSuffix;
  const setAddMagicSuffix = controls?.setAddMagicSuffix ?? propSetAddMagicSuffix ?? (() => {});
  const thinkingMode = controls?.thinkingMode ?? defaultThinkingMode;
  const setThinkingMode = controls?.setThinkingMode ?? (() => {});
  const enableSequential =
    controls?.enableSequential ?? propEnableSequential ?? defaultEnableSequential;
  const setEnableSequential =
    controls?.setEnableSequential ?? propSetEnableSequential ?? (() => {});

  const maxImageCount =
    (typeof schema?.constraints?.max_image_count === 'number'
      ? schema?.constraints?.max_image_count
      : undefined) ?? Math.max(...imageCountOptions, 1);
  const minImageCount = imageCountOptions.length > 0 ? Math.min(...imageCountOptions) : 1;
  const standardMaxImageCount = supportsSequentialMode ? Math.min(maxImageCount, 4) : maxImageCount;
  const effectiveMaxImageCount =
    supportsSequentialMode && enableSequential ? maxImageCount : standardMaxImageCount;
  const maxSelectableImageCount =
    imageCountOptions.length > 0
      ? Math.min(effectiveMaxImageCount, Math.max(...imageCountOptions))
      : effectiveMaxImageCount;
  const selectableImageCountOptions = useMemo(
    () =>
      imageCountOptions.filter(
        (value) => value >= minImageCount && value <= maxSelectableImageCount
      ),
    [imageCountOptions, maxSelectableImageCount, minImageCount]
  );
  const availableAspectRatios = useMemo(() => schema?.aspectRatios ?? [], [schema]);
  const availableResolutionTiers = useMemo(() => schema?.resolutionTiers ?? [], [schema]);
  const showResolutionTier = availableResolutionTiers.length > 0;

  useEffect(() => {
    if (!supportsStyle) return;
    const validStyles = styleOptions
      .map((option) => option.value)
      .filter((value): value is string => typeof value === 'string');
    if (validStyles.length > 0 && !validStyles.includes(style)) {
      setStyle(validStyles[0]);
    }
  }, [style, styleOptions, setStyle, supportsStyle]);

  useEffect(() => {
    if (selectableImageCountOptions.length === 0) return;
    if (numberOfImages < minImageCount) {
      setNumberOfImages(minImageCount);
    } else if (numberOfImages > maxSelectableImageCount) {
      setNumberOfImages(maxSelectableImageCount);
    } else if (!selectableImageCountOptions.includes(numberOfImages)) {
      setNumberOfImages(selectableImageCountOptions[0]);
    }
  }, [
    maxSelectableImageCount,
    minImageCount,
    numberOfImages,
    selectableImageCountOptions,
    setNumberOfImages,
  ]);

  useEffect(() => {
    if (supportsSequentialMode && enableSequential && thinkingMode) {
      setThinkingMode(false);
    }
  }, [enableSequential, setThinkingMode, supportsSequentialMode, thinkingMode]);

  useEffect(() => {
    const validRatios = availableAspectRatios.map((r) => r.value);
    if (validRatios.length > 0 && !validRatios.includes(aspectRatio)) {
      setAspectRatio(validRatios[0] || defaultAspectRatio);
    }
  }, [availableAspectRatios, aspectRatio, defaultAspectRatio, setAspectRatio]);

  useEffect(() => {
    if (availableResolutionTiers.length > 0) {
      const validTiers = availableResolutionTiers.map((t) => t.value);
      if (!validTiers.includes(resolution)) {
        setResolution(validTiers[0] || defaultResolution);
      }
    }
  }, [availableResolutionTiers, resolution, defaultResolution, setResolution]);

  const currentPixelResolution = useMemo(() => {
    const schemaPixelRes = getPixelResolutionFromSchema(schema, aspectRatio, resolution);
    return schemaPixelRes ? schemaPixelRes.replace('*', '×') : '';
  }, [schema, aspectRatio, resolution]);

  return (
    <div className="space-y-4">
      {!loading &&
        (error ||
          availableAspectRatios.length === 0 ||
          (supportsStyle && styleOptions.length === 0) ||
          imageCountOptions.length === 0) && (
          <div className="text-[10px] text-rose-400">
            比例/分辨率配置加载失败，请检查后端 `mode_controls_catalog.json`。
          </div>
        )}

      {supportsStyle && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Palette size={12} className="text-pink-400" />
            <span className="text-xs text-slate-300">风格</span>
          </div>
          <select
            value={style}
            onChange={(e) => setStyle(e.target.value)}
            className="w-full px-3 py-2 text-xs bg-slate-800 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-pink-500"
          >
            {styleOptions.map((s) => (
              <option key={String(s.value)} value={String(s.value)}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {supportsSequentialMode && (
        <FeatureToggleControl
          enabled={enableSequential}
          onEnabledChange={setEnableSequential}
          icon={<Layers size={12} className="text-blue-400" />}
          label="组图生成"
          activeClass="bg-blue-600"
        />
      )}

      <ImageCountSliderControl
        value={numberOfImages}
        onChange={setNumberOfImages}
        min={minImageCount}
        max={maxSelectableImageCount}
        label="图片数量"
      />

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Ratio size={12} className="text-indigo-400" />
            <span className="text-xs text-slate-300">图片比例</span>
          </div>
          {currentPixelResolution && (
            <span className="text-[10px] text-indigo-400 font-mono">{currentPixelResolution}</span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {availableAspectRatios.map((ratio) => (
            <button
              key={ratio.value}
              onClick={() => setAspectRatio(ratio.value)}
              className={`py-1.5 text-[10px] font-medium rounded-lg transition-all ${
                aspectRatio === ratio.value
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {ratio.value}
            </button>
          ))}
        </div>
      </div>

      {showResolutionTier && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Maximize2 size={12} className="text-emerald-400" />
            <span className="text-xs text-slate-300">分辨率档位</span>
          </div>
          <div className="flex gap-2">
            {availableResolutionTiers.map((tier) => {
              const schemaPixelRes = getPixelResolutionFromSchema(schema, aspectRatio, tier.value);
              const tierPixelRes = schemaPixelRes ? schemaPixelRes.replace('*', '×') : '--';
              return (
                <button
                  key={tier.value}
                  onClick={() => setResolution(tier.value)}
                  className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all flex flex-col items-center gap-0.5 ${
                    resolution === tier.value
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                  }`}
                >
                  <span className="font-bold">{tier.value}</span>
                  <span className="text-[10px] opacity-70">{tierPixelRes}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="border-t border-slate-700/50 pt-4">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full flex items-center justify-between text-xs text-slate-400 hover:text-slate-200 transition-colors"
        >
          <span>高级参数</span>
          {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        {showAdvanced && (
          <div className="mt-4 space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-300">Seed</span>
                <button
                  onClick={() => setSeed(Math.floor(Math.random() * 2147483647))}
                  className="text-xs text-indigo-400 hover:text-indigo-300"
                  title="随机种子"
                >
                  <Dices size={14} />
                </button>
              </div>
              <input
                type="number"
                value={seed === -1 ? '' : seed}
                onChange={(e) => setSeed(e.target.value ? parseInt(e.target.value) : -1)}
                placeholder="随机 (-1)"
                min={seedRange?.min}
                max={seedRange?.max}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500/50"
              />
            </div>

            {supportsNegativePrompt && (
              <div className="space-y-2">
                <span className="text-xs text-slate-300">负向提示词</span>
                <textarea
                  value={negativePrompt}
                  onChange={(e) => setNegativePrompt(e.target.value)}
                  placeholder="不想出现的内容..."
                  className="w-full h-16 bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50"
                />
              </div>
            )}

            {supportsLocalPromptEnhance && (
              <PromptEnhanceControl
                enabled={enhancePrompt}
                onEnabledChange={setEnhancePrompt}
                modelId={enhancePromptModel}
                onModelIdChange={setEnhancePromptModel}
                modelOptions={enhancePromptModels}
                allowAutoModel
                thinkingLevel={enhancePromptThinkingLevel}
                onThinkingLevelChange={setEnhancePromptThinkingLevel}
              />
            )}

            {supportsAddMagicSuffix && (
              <>
                <div className="flex items-center justify-between py-1">
                  <div className="flex items-center gap-2">
                    <Wand2 size={12} className="text-pink-400" />
                    <span className="text-xs text-slate-300">魔法词组</span>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={addMagicSuffix}
                    aria-label="魔法词组"
                    onClick={() => setAddMagicSuffix(!addMagicSuffix)}
                    className={`w-10 h-6 flex items-center rounded-full p-1 cursor-pointer transition-colors duration-200 ${
                      addMagicSuffix ? 'bg-pink-600' : 'bg-slate-600'
                    }`}
                  >
                    <span
                      className={`w-4 h-4 bg-white rounded-full shadow-md transform transition-transform duration-200 ${
                        addMagicSuffix ? 'translate-x-4' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
                <p className="text-[10px] text-slate-500 mt-1">
                  自动添加"超清，4K，电影级构图"等质量增强词
                </p>
              </>
            )}

            {supportsThinkingMode && !enableSequential && (
              <FeatureToggleControl
                enabled={thinkingMode}
                onEnabledChange={setThinkingMode}
                icon={<BrainCircuit size={12} className="text-cyan-400" />}
                label="思考模式"
                activeClass="bg-cyan-600"
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ImageGenControls;
