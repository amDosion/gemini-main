/**
 * Google 图像生成控件（仅 Panel 模式）
 * 
 * 用于右侧参数面板，通过 ModeControlsCoordinator 分发
 * 
 * Google 提供商专用参数：
 * - 风格、图片数量、比例、分辨率档位（1K/2K）、实际像素分辨率
 * - 高级选项：输出格式、压缩质量、Seed、负向提示词、AI增强提示词
 */
import React, { useEffect, useMemo } from 'react';
import { Palette, Layers, Ratio, FileImage, Sparkles, ChevronUp, ChevronDown, Dices } from 'lucide-react';
import { ImageGenControlsProps } from '../../types';
import { useEnhancePromptModels } from '../../../hooks/useEnhancePromptModels';
import { getPixelResolutionFromSchema, useModeControlsSchema } from '../../../hooks/useModeControlsSchema';

export const ImageGenControls: React.FC<ImageGenControlsProps> = (props) => {
  const {
    providerId = 'google',
    currentModel,
    controls,
    maxImageCount = 4,
    // 单独 props（向后兼容）
    style: propStyle, setStyle: propSetStyle,
    numberOfImages: propNumberOfImages, setNumberOfImages: propSetNumberOfImages,
    aspectRatio: propAspectRatio, setAspectRatio: propSetAspectRatio,
    resolution: propResolution, setResolution: propSetResolution,
    showAdvanced: propShowAdvanced, setShowAdvanced: propSetShowAdvanced,
    negativePrompt: propNegativePrompt, setNegativePrompt: propSetNegativePrompt,
    seed: propSeed, setSeed: propSetSeed,
    outputMimeType: propOutputMimeType, setOutputMimeType: propSetOutputMimeType,
    outputCompressionQuality: propOutputCompressionQuality, setOutputCompressionQuality: propSetOutputCompressionQuality,
    enhancePrompt: propEnhancePrompt, setEnhancePrompt: propSetEnhancePrompt,
    availableModels = [],
  } = props;

  const modelId = currentModel?.id;
  const { schema, loading, error } = useModeControlsSchema(providerId, 'image-gen', modelId);
  const defaults = schema?.defaults ?? {};
  const styleOptions = useMemo(
    () =>
      (schema?.paramOptions?.style ?? []).filter(
        (option): option is { label: string; value: string } => typeof option.value === 'string'
      ),
    [schema]
  );
  const imageCountOptions = useMemo(
    () =>
      (schema?.paramOptions?.number_of_images ?? [])
        .map((option) => option.value)
        .filter((value): value is number => typeof value === 'number'),
    [schema]
  );
  const outputMimeOptions = useMemo(
    () =>
      (schema?.paramOptions?.output_mime_type ?? []).filter(
        (option): option is { label: string; value: string } => typeof option.value === 'string'
      ),
    [schema]
  );
  const seedRange = schema?.numericRanges?.seed;
  const compressionRange = schema?.numericRanges?.output_compression_quality;

  const defaultStyle =
    (typeof defaults.style === 'string' ? defaults.style : undefined) ??
    (typeof styleOptions[0]?.value === 'string' ? styleOptions[0].value : undefined) ??
    'None';
  const defaultImageCount =
    (typeof defaults.number_of_images === 'number' ? defaults.number_of_images : undefined) ??
    imageCountOptions[0] ??
    1;
  const defaultAspectRatio = typeof defaults.aspect_ratio === 'string' ? defaults.aspect_ratio : '1:1';
  const defaultResolution = typeof defaults.resolution === 'string' ? defaults.resolution : '1K';
  const defaultSeed = typeof defaults.seed === 'number' ? defaults.seed : -1;
  const defaultOutputMime =
    (typeof defaults.output_mime_type === 'string' ? defaults.output_mime_type : undefined) ??
    (typeof outputMimeOptions[0]?.value === 'string' ? outputMimeOptions[0].value : undefined) ??
    'image/png';
  const defaultCompressionQuality =
    typeof defaults.output_compression_quality === 'number' ? defaults.output_compression_quality : 80;
  const defaultEnhancePrompt = typeof defaults.enhance_prompt === 'boolean' ? defaults.enhance_prompt : false;
  const defaultNegativePrompt = typeof defaults.negative_prompt === 'string' ? defaults.negative_prompt : '';

  // 优先使用 controls 对象，fallback 到单独 props
  const style = controls?.style ?? propStyle ?? defaultStyle;
  const setStyle = controls?.setStyle ?? propSetStyle ?? (() => {});
  const numberOfImages = controls?.numberOfImages ?? propNumberOfImages ?? defaultImageCount;
  const setNumberOfImages = controls?.setNumberOfImages ?? propSetNumberOfImages ?? (() => {});
  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? defaultAspectRatio;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? (() => {});
  const resolution = controls?.resolution ?? propResolution ?? defaultResolution;
  const setResolution = controls?.setResolution ?? propSetResolution ?? (() => {});
  const showAdvanced = controls?.showAdvanced ?? propShowAdvanced ?? false;
  const setShowAdvanced = controls?.setShowAdvanced ?? propSetShowAdvanced ?? (() => {});
  const negativePrompt = controls?.negativePrompt ?? propNegativePrompt ?? defaultNegativePrompt;
  const setNegativePrompt = controls?.setNegativePrompt ?? propSetNegativePrompt ?? (() => {});
  const seed = controls?.seed ?? propSeed ?? defaultSeed;
  const setSeed = controls?.setSeed ?? propSetSeed ?? (() => {});
  const outputMimeType = controls?.outputMimeType ?? propOutputMimeType ?? defaultOutputMime;
  const setOutputMimeType = controls?.setOutputMimeType ?? propSetOutputMimeType ?? (() => {});
  const outputCompressionQuality =
    controls?.outputCompressionQuality ?? propOutputCompressionQuality ?? defaultCompressionQuality;
  const setOutputCompressionQuality = controls?.setOutputCompressionQuality ?? propSetOutputCompressionQuality ?? (() => {});
  const enhancePrompt = controls?.enhancePrompt ?? propEnhancePrompt ?? defaultEnhancePrompt;
  const enhancePromptModels = useEnhancePromptModels();
  const enhancePromptModel = controls?.enhancePromptModel ?? '';
  const setEnhancePromptModel = controls?.setEnhancePromptModel;
  const setEnhancePrompt = controls?.setEnhancePrompt ?? propSetEnhancePrompt ?? (() => {});

  const availableRatios = useMemo(() => {
    return schema?.aspectRatios ?? [];
  }, [schema]);

  const availableResolutionTiers = useMemo(() => {
    return schema?.resolutionTiers ?? [];
  }, [schema]);

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

  useEffect(() => {
    const validStyles = styleOptions
      .map((option) => option.value)
      .filter((value): value is string => typeof value === 'string');
    if (validStyles.length > 0 && !validStyles.includes(style)) {
      setStyle(validStyles[0]);
    }
  }, [style, styleOptions, setStyle]);

  useEffect(() => {
    if (imageCountOptions.length > 0 && !imageCountOptions.includes(numberOfImages)) {
      setNumberOfImages(imageCountOptions[0]);
    }
  }, [numberOfImages, imageCountOptions, setNumberOfImages]);

  useEffect(() => {
    const validMimeTypes = outputMimeOptions
      .map((option) => option.value)
      .filter((value): value is string => typeof value === 'string');
    if (validMimeTypes.length > 0 && !validMimeTypes.includes(outputMimeType)) {
      setOutputMimeType(validMimeTypes[0]);
    }
  }, [outputMimeType, outputMimeOptions, setOutputMimeType]);

  // 计算当前像素分辨率
  const currentPixelResolution = useMemo(() => {
    const schemaPixelRes = getPixelResolutionFromSchema(schema, aspectRatio, resolution);
    return schemaPixelRes ? schemaPixelRes.replace('*', '×') : '';
  }, [schema, aspectRatio, resolution]);

  return (
    <div className="space-y-4">
      {/* ==================== 基础参数 ==================== */}
      {!loading && (error || availableRatios.length === 0 || styleOptions.length === 0 || imageCountOptions.length === 0) && (
        <div className="text-[10px] text-rose-400">
          比例/分辨率配置加载失败，请检查后端 `mode_controls_catalog.json`。
        </div>
      )}
      
      {/* 风格选择 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Palette size={12} className="text-pink-400" />
          <span className="text-xs text-slate-300">风格</span>
        </div>
        <select
          value={style}
          onChange={(e) => setStyle(e.target.value)}
          className="w-full px-3 py-2 text-xs bg-slate-800 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-emerald-500"
        >
          {styleOptions.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>

      {/* 图片比例 + 分辨率联动 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Ratio size={12} className="text-emerald-400" />
            <span className="text-xs text-slate-300">图片比例</span>
          </div>
          {currentPixelResolution && (
            <span className="text-[10px] text-emerald-400 font-mono">{currentPixelResolution}</span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {availableRatios.map((ratio) => (
            <button
              key={ratio.value}
              onClick={() => setAspectRatio(ratio.value)}
              className={`py-1.5 text-[10px] font-medium rounded-lg transition-all ${
                aspectRatio === ratio.value
                  ? 'bg-emerald-600 text-white'
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

      {/* 生成数量 */}
      {maxImageCount > 1 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Layers size={12} className="text-blue-400" />
            <span className="text-xs text-slate-300">生成数量</span>
          </div>
        <div className="flex gap-2">
            {imageCountOptions.filter((n) => n <= maxImageCount).map((num) => (
              <button
                key={num}
                onClick={() => setNumberOfImages(num)}
                className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                  numberOfImages === num
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                }`}
              >
                {num}
              </button>
            ))}
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
            {/* 输出格式 */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <FileImage size={12} className="text-cyan-400" />
                <span className="text-xs text-slate-300">输出格式</span>
              </div>
              <div className="flex gap-2">
                {outputMimeOptions.map((opt) => (
                  <button
                    key={String(opt.value)}
                    onClick={() => typeof opt.value === 'string' && setOutputMimeType(opt.value)}
                    className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                      outputMimeType === opt.value
                        ? 'bg-cyan-600 text-white'
                        : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* JPEG 压缩质量 */}
            {outputMimeType === 'image/jpeg' && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-300">压缩质量</span>
                  <span className="text-xs text-indigo-400 font-mono">{outputCompressionQuality}%</span>
                </div>
                <input
                  type="range"
                  min={compressionRange?.min ?? 1}
                  max={compressionRange?.max ?? 100}
                  step={compressionRange?.step ?? 1}
                  value={outputCompressionQuality}
                  onChange={(e) => setOutputCompressionQuality(parseInt(e.target.value))}
                  className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-indigo-500"
                />
              </div>
            )}

            {/* Seed */}
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
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* 负向提示词 */}
            <div className="space-y-2">
              <span className="text-xs text-slate-300">负向提示词</span>
              <textarea
                value={negativePrompt}
                onChange={(e) => setNegativePrompt(e.target.value)}
                placeholder="不想出现的内容..."
                className="w-full h-16 bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-300 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* 增强提示词 - Switch 开关 */}
            <div className="flex items-center justify-between py-1">
              <div className="flex items-center gap-2">
                <Sparkles size={12} className="text-pink-400" />
                <span className="text-xs text-slate-300">AI 增强提示词</span>
              </div>
              <div
                onClick={() => setEnhancePrompt(!enhancePrompt)}
                className={`w-10 h-6 flex items-center rounded-full p-1 cursor-pointer transition-colors duration-200 ${
                  enhancePrompt ? 'bg-pink-600' : 'bg-slate-600'
                }`}
              >
                <div
                  className={`w-4 h-4 bg-white rounded-full shadow-md transform transition-transform duration-200 ${
                    enhancePrompt ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </div>
            </div>

            {/* 增强提示词模型选择（仅开启时显示） */}
            {enhancePrompt && (
              <div className="space-y-2">
                <span className="text-xs text-slate-300">增强提示词模型</span>
                <select
                  value={enhancePromptModel}
                  onChange={(e) => setEnhancePromptModel?.(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-pink-500/50"
                >
                  <option value="">自动选择</option>
                  {enhancePromptModels.map(model => (
                    <option key={model.id} value={model.id}>
                      {model.name || model.id}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ImageGenControls;
