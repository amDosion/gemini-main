/**
 * Google 图像编辑控件（仅 Panel 模式）
 * 
 * 用于右侧参数面板，通过 ModeControlsCoordinator 分发
 */
import React, { useEffect, useMemo } from 'react';
import { Ratio, Layers, ChevronUp, ChevronDown, FileImage, Dices, Sparkles } from 'lucide-react';
import { ImageEditControlsProps } from '../../types';
import { useEnhancePromptModels } from '../../../hooks/useEnhancePromptModels';
import { getPixelResolutionFromSchema, useModeControlsSchema } from '../../../hooks/useModeControlsSchema';

export const ImageEditControls: React.FC<ImageEditControlsProps> = ({
  providerId = 'google',
  controls,
  availableModels = [],
  maxImageCount = 4,
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
  const { schema, loading, error } = useModeControlsSchema(providerId, 'image-edit');
  const defaults = schema?.defaults ?? {};
  const imageCountOptions = useMemo(
    () =>
      (schema?.paramOptions?.number_of_images ?? [])
        .map((option) => option.value)
        .filter((value): value is number => typeof value === 'number'),
    [schema]
  );
  const outputMimeOptions = useMemo(
    () => (schema?.paramOptions?.output_mime_type ?? []).filter((option) => typeof option.value === 'string'),
    [schema]
  );
  const seedRange = schema?.numericRanges?.seed;
  const compressionRange = schema?.numericRanges?.output_compression_quality;
  const defaultImageCount =
    (typeof defaults.number_of_images === 'number' ? defaults.number_of_images : undefined) ??
    imageCountOptions[0] ??
    1;
  const defaultAspectRatio = typeof defaults.aspect_ratio === 'string' ? defaults.aspect_ratio : '1:1';
  const defaultResolution = typeof defaults.resolution === 'string' ? defaults.resolution : '1K';

  // 优先使用 controls 对象，fallback 到单独 props
  const numberOfImages = controls?.numberOfImages ?? propNumberOfImages ?? defaultImageCount;
  const setNumberOfImages = controls?.setNumberOfImages ?? propSetNumberOfImages ?? (() => {});
  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? defaultAspectRatio;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? (() => {});
  const resolution = controls?.resolution ?? propResolution ?? defaultResolution;
  const setResolution = controls?.setResolution ?? propSetResolution ?? (() => {});
  const showAdvanced = controls?.showAdvanced ?? propShowAdvanced ?? false;
  const setShowAdvanced = controls?.setShowAdvanced ?? propSetShowAdvanced ?? (() => {});
  const availableRatios = useMemo(() => {
    return schema?.aspectRatios ?? [];
  }, [schema]);
  const availableResolutionTiers = useMemo(() => {
    return schema?.resolutionTiers ?? [];
  }, [schema]);
  const enhancePromptModels = useEnhancePromptModels();
  const enhancePromptModel = controls?.enhancePromptModel ?? '';
  const setEnhancePromptModel = controls?.setEnhancePromptModel;
  
  // 计算当前像素分辨率
  const currentPixelResolution = useMemo(() => {
    const schemaPixelRes = getPixelResolutionFromSchema(schema, aspectRatio, resolution);
    return schemaPixelRes ? schemaPixelRes.replace('*', '×') : '';
  }, [schema, aspectRatio, resolution]);

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
    if (imageCountOptions.length > 0 && !imageCountOptions.includes(numberOfImages)) {
      setNumberOfImages(imageCountOptions[0]);
    }
  }, [numberOfImages, imageCountOptions, setNumberOfImages]);

  useEffect(() => {
    if (!controls?.setOutputMimeType) {
      return;
    }
    const validMimeTypes = outputMimeOptions
      .map((option) => option.value)
      .filter((value): value is string => typeof value === 'string');
    if (
      validMimeTypes.length > 0 &&
      controls.outputMimeType &&
      !validMimeTypes.includes(controls.outputMimeType)
    ) {
      controls.setOutputMimeType(validMimeTypes[0]);
    }
  }, [controls, outputMimeOptions]);

  // 当前选中的增强模型如果不再可用（切模式/切模型后），自动清空为“自动选择”
  useEffect(() => {
    if (!enhancePromptModel || !setEnhancePromptModel) {
      return;
    }
    const stillAvailable = enhancePromptModels.some((model) => model.id === enhancePromptModel);
    if (!stillAvailable) {
      setEnhancePromptModel('');
    }
  }, [enhancePromptModel, setEnhancePromptModel, enhancePromptModels]);

  return (
    <div className="space-y-4">
      {/* ==================== 基础参数 ==================== */}
      {!loading && (error || availableRatios.length === 0 || imageCountOptions.length === 0) && (
        <div className="text-[10px] text-rose-400">
          比例/分辨率配置加载失败，请检查后端 `mode_controls_catalog.json`。
        </div>
      )}
      
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

      {/* 分辨率档位（编辑模式支持 4K） */}
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
                    ? 'bg-pink-600 text-white'
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
      {controls && (
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
                      onClick={() => typeof opt.value === 'string' && controls.setOutputMimeType(opt.value)}
                      className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                        controls.outputMimeType === opt.value
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
              {controls.outputMimeType === 'image/jpeg' && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-300">压缩质量</span>
                    <span className="text-xs text-pink-400 font-mono">{controls.outputCompressionQuality}%</span>
                  </div>
                  <input
                    type="range"
                    min={compressionRange?.min ?? 1}
                    max={compressionRange?.max ?? 100}
                    step={compressionRange?.step ?? 1}
                    value={controls.outputCompressionQuality}
                    onChange={(e) => controls.setOutputCompressionQuality(parseInt(e.target.value))}
                    className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-pink-500"
                  />
                </div>
              )}

              {/* 负面提示词 */}
              <div className="space-y-2">
                <span className="text-xs text-slate-300">负面提示词</span>
                <textarea
                  value={controls.negativePrompt || ''}
                  onChange={(e) => controls.setNegativePrompt(e.target.value)}
                  placeholder="不想出现的元素..."
                  className="w-full h-16 bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-pink-500/50"
                />
              </div>

              {/* Seed */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-300">Seed</span>
                  <button
                    onClick={() => controls.setSeed(Math.floor(Math.random() * 2147483647))}
                    className="text-xs text-pink-400 hover:text-pink-300"
                    title="随机种子"
                  >
                    <Dices size={14} />
                  </button>
                </div>
                <input
                  type="number"
                  value={controls.seed === -1 ? '' : controls.seed}
                  onChange={(e) => controls.setSeed(e.target.value ? parseInt(e.target.value) : -1)}
                  placeholder="随机 (-1)"
                  min={seedRange?.min}
                  max={seedRange?.max}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-pink-500/50"
                />
              </div>

              {/* AI 增强提示词 - Switch 开关 */}
              <div className="flex items-center justify-between py-1">
                <div className="flex items-center gap-2">
                  <Sparkles size={12} className="text-pink-400" />
                  <span className="text-xs text-slate-300">AI 增强提示词</span>
                </div>
                <div
                  onClick={() => controls.setEnhancePrompt(!controls.enhancePrompt)}
                  className={`w-10 h-6 flex items-center rounded-full p-1 cursor-pointer transition-colors duration-200 ${
                    controls.enhancePrompt ? 'bg-pink-600' : 'bg-slate-600'
                  }`}
                >
                  <div
                    className={`w-4 h-4 bg-white rounded-full shadow-md transform transition-transform duration-200 ${
                      controls.enhancePrompt ? 'translate-x-4' : 'translate-x-0'
                    }`}
                  />
                </div>
              </div>

              {/* 增强提示词模型选择（仅开启时显示） */}
              {controls.enhancePrompt && (
                <div className="space-y-2">
                  <span className="text-xs text-slate-300">增强提示词模型</span>
                  <select
                    value={controls.enhancePromptModel || ''}
                    onChange={(e) => controls.setEnhancePromptModel(e.target.value)}
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

              {/* 思考过程 - Switch 开关 */}
              <div className="flex items-center justify-between py-1">
                <div className="flex items-center gap-2">
                  <Sparkles size={12} className="text-cyan-400" />
                  <span className="text-xs text-slate-300">显示思考过程</span>
                </div>
                <div
                  onClick={() => controls.setEnableThinking(!controls.enableThinking)}
                  className={`w-10 h-6 flex items-center rounded-full p-1 cursor-pointer transition-colors duration-200 ${
                    controls.enableThinking ? 'bg-cyan-600' : 'bg-slate-600'
                  }`}
                >
                  <div
                    className={`w-4 h-4 bg-white rounded-full shadow-md transform transition-transform duration-200 ${
                      controls.enableThinking ? 'translate-x-4' : 'translate-x-0'
                    }`}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ImageEditControls;
