/**
 * 通义图像编辑专用控件（仅 Panel 模式）
 *
 * 后端支持参数（来源: backend/app/services/tongyi/image_edit.py）:
 * - n: 图片数量
 * - negative_prompt: 负面提示词
 * - size: 尺寸
 * - watermark: 水印
 * - seed: 种子
 * - prompt_extend: 提示词扩展
 * - enable_prompt_optimize: Prompt 智能优化
 */
import React, { useEffect, useMemo } from 'react';
import { Ratio, ChevronUp, ChevronDown, Dices } from 'lucide-react';
import { ImageEditControlsProps } from '../../types';
import {
  getPixelResolutionFromSchema,
  useModeControlsSchema,
} from '../../../hooks/useModeControlsSchema';
import { useEnhancePromptModels } from '../../../hooks/useEnhancePromptModels';
import PromptEnhanceControl from '../../shared/PromptEnhanceControl';
import ImageCountSliderControl from '../../shared/ImageCountSliderControl';
import { getUnsupportedParams } from '../../shared/modeControlSchemaUtils';

// 模块级稳定空函数:作为缺失 setter 的回退。内联 (() => {}) 每次渲染都换新身份,
// 当这些 setter 出现在 useEffect 依赖数组里时会导致 effect 每渲染都重跑。
const NOOP = (): void => {};

export const ImageEditControls: React.FC<ImageEditControlsProps> = ({
  providerId = 'tongyi',
  mode = 'image-edit',
  currentModel,
  controls,
  // 单独 props（向后兼容）
  numberOfImages: propNumberOfImages,
  setNumberOfImages: propSetNumberOfImages,
  aspectRatio: propAspectRatio,
  setAspectRatio: propSetAspectRatio,
  resolution: propResolution,
  setResolution: propSetResolution,
  showAdvanced: propShowAdvanced,
  setShowAdvanced: propSetShowAdvanced,
}) => {
  const { schema, loading, error } = useModeControlsSchema(providerId, mode, currentModel?.id);
  const defaults = schema?.defaults ?? {};
  const seedRange = schema?.numericRanges?.seed;
  const unsupportedParams = useMemo(() => getUnsupportedParams(schema), [schema]);
  const supportsNegativePrompt = !unsupportedParams.has('negative_prompt');
  const supportsLocalPromptEnhance = !unsupportedParams.has('enhance_prompt');
  const imageCountOptions = useMemo(
    () =>
      (schema?.paramOptions?.number_of_images ?? [])
        .map((option) => option.value)
        .filter((value): value is number => typeof value === 'number'),
    [schema]
  );

  const defaultAspectRatio =
    typeof defaults.aspect_ratio === 'string' ? defaults.aspect_ratio : '1:1';
  const defaultResolution = typeof defaults.resolution === 'string' ? defaults.resolution : '1K';
  const defaultImageCount =
    (typeof defaults.number_of_images === 'number' ? defaults.number_of_images : undefined) ??
    imageCountOptions[0] ??
    1;
  const defaultNegativePrompt =
    typeof defaults.negative_prompt === 'string' ? defaults.negative_prompt : '';
  const defaultSeed = typeof defaults.seed === 'number' ? defaults.seed : -1;
  const defaultPromptExtend =
    typeof defaults.prompt_extend === 'boolean' ? defaults.prompt_extend : false;
  const defaultEnhancePrompt =
    typeof defaults.enhance_prompt === 'boolean' ? defaults.enhance_prompt : false;

  // 优先使用 controls 对象，fallback 到单独 props
  const numberOfImages = controls?.numberOfImages ?? propNumberOfImages ?? defaultImageCount;
  const setNumberOfImages = controls?.setNumberOfImages ?? propSetNumberOfImages ?? NOOP;
  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? defaultAspectRatio;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? NOOP;
  const resolution = controls?.resolution ?? propResolution ?? defaultResolution;
  const setResolution = controls?.setResolution ?? propSetResolution ?? NOOP;
  const showAdvanced = controls?.showAdvanced ?? propShowAdvanced ?? false;
  const setShowAdvanced = controls?.setShowAdvanced ?? propSetShowAdvanced ?? NOOP;

  // TongYi 专用参数
  const negativePrompt = controls?.negativePrompt ?? defaultNegativePrompt;
  const setNegativePrompt = controls?.setNegativePrompt ?? NOOP;
  const seed = controls?.seed ?? defaultSeed;
  const setSeed = controls?.setSeed ?? NOOP;
  const promptExtend = controls?.promptExtend ?? defaultPromptExtend;
  const setPromptExtend = controls?.setPromptExtend ?? NOOP;
  const enhancePrompt = controls?.enhancePrompt ?? promptExtend ?? defaultEnhancePrompt;
  const setEnhancePrompt = controls?.setEnhancePrompt ?? setPromptExtend;
  const enhancePromptModel = controls?.enhancePromptModel ?? '';
  const setEnhancePromptModel = controls?.setEnhancePromptModel;
  const enhancePromptThinkingLevel = controls?.enhancePromptThinkingLevel ?? 'auto';
  const setEnhancePromptThinkingLevel = controls?.setEnhancePromptThinkingLevel;
  const enhancePromptModels = useEnhancePromptModels(providerId, undefined, {
    requiresVision: true,
    includeHidden: true,
  });
  const maxImageCount =
    (typeof schema?.constraints?.max_image_count === 'number'
      ? schema.constraints.max_image_count
      : undefined) ?? Math.max(...imageCountOptions, 1);
  const minImageCount = imageCountOptions.length > 0 ? Math.min(...imageCountOptions) : 1;
  const maxSelectableImageCount =
    imageCountOptions.length > 0
      ? Math.min(maxImageCount, Math.max(...imageCountOptions))
      : maxImageCount;
  const availableRatios = useMemo(() => {
    return schema?.aspectRatios ?? [];
  }, [schema]);
  const availableResolutionTiers = useMemo(() => {
    return schema?.resolutionTiers ?? [];
  }, [schema]);

  // 计算当前像素分辨率
  const currentPixelResolution = useMemo(() => {
    const schemaPixelRes = getPixelResolutionFromSchema(schema, aspectRatio, resolution);
    return schemaPixelRes ? schemaPixelRes.replace('*', '×') : '';
  }, [schema, aspectRatio, resolution]);

  useEffect(() => {
    if (imageCountOptions.length === 0) return;
    if (numberOfImages < minImageCount) {
      setNumberOfImages(minImageCount);
    } else if (numberOfImages > maxSelectableImageCount) {
      setNumberOfImages(maxSelectableImageCount);
    } else if (!imageCountOptions.includes(numberOfImages)) {
      setNumberOfImages(imageCountOptions[0]);
    }
  }, [
    imageCountOptions,
    maxSelectableImageCount,
    minImageCount,
    numberOfImages,
    setNumberOfImages,
  ]);

  useEffect(() => {
    const validRatios = availableRatios.map((r) => r.value);
    if (validRatios.length > 0 && !validRatios.includes(aspectRatio)) {
      setAspectRatio(validRatios[0]);
    }
  }, [availableRatios, aspectRatio, setAspectRatio]);

  useEffect(() => {
    const validTiers = availableResolutionTiers.map((t) => t.value);
    if (validTiers.length > 0 && !validTiers.includes(resolution)) {
      setResolution(validTiers[0]);
    }
  }, [availableResolutionTiers, resolution, setResolution]);

  return (
    <div className="space-y-4">
      {/* ==================== 基础参数 ==================== */}
      {!loading && (error || availableRatios.length === 0) && (
        <div className="text-[10px] text-rose-400">
          比例/分辨率配置加载失败，请检查后端 `mode_controls_catalog.json`。
        </div>
      )}

      <ImageCountSliderControl
        value={numberOfImages}
        onChange={setNumberOfImages}
        min={minImageCount}
        max={maxSelectableImageCount}
        label="图片数量"
      />

      {/* 图片比例 + 分辨率联动 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Ratio size={12} className="text-pink-400" />
            <span className="text-xs text-slate-300">图片比例</span>
          </div>
          {currentPixelResolution && (
            <span className="text-[10px] text-pink-400 font-mono">{currentPixelResolution}</span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {availableRatios.map((ratio) => (
            <button
              key={ratio.value}
              onClick={() => setAspectRatio(ratio.value)}
              className={`py-1.5 text-[10px] font-medium rounded-lg transition-all ${
                aspectRatio === ratio.value
                  ? 'bg-pink-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {ratio.value}
            </button>
          ))}
        </div>
      </div>

      {/* 分辨率档位 */}
      {availableResolutionTiers.length > 0 && (
        <div className="space-y-2">
          <span className="text-xs text-slate-300">分辨率</span>
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
                      ? 'bg-pink-600 text-white'
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

      {/* ==================== 高级参数折叠区 ==================== */}
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
            {/* 负面提示词 */}
            {supportsNegativePrompt && (
              <div className="space-y-2">
                <span className="text-xs text-slate-300">负面提示词</span>
                <textarea
                  value={negativePrompt}
                  onChange={(e) => setNegativePrompt(e.target.value)}
                  placeholder="不想出现的元素..."
                  className="w-full h-16 bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-pink-500/50"
                />
              </div>
            )}

            {/* Seed */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-300">Seed</span>
                <button
                  onClick={() => setSeed(Math.floor(Math.random() * 2147483647))}
                  className="text-xs text-pink-400 hover:text-pink-300"
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
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-pink-500/50"
              />
            </div>

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
          </div>
        )}
      </div>
    </div>
  );
};

export default ImageEditControls;
