/**
 * Google 图像扩展控件（仅 Panel 模式）
 *
 * 支持多种扩图模式：
 * - ratio: 按目标比例扩图
 * - scale: 按缩放因子扩图
 * - offset: 按像素偏移扩图
 * - upscale: 图片放大 (x2/x3/x4)
 */
import React, { useEffect, useMemo } from 'react';
import {
  Ratio,
  Layers,
  ChevronUp,
  ChevronDown,
  FileImage,
  Dices,
  Maximize2,
  Move,
  ZoomIn,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
} from 'lucide-react';
import { ImageOutpaintControlsProps } from '../../types';
import { useModeControlsSchema } from '../../../hooks/useModeControlsSchema';

const MODE_META: Record<string, { label: string; icon: React.ComponentType<any>; description: string }> = {
  ratio: { label: '按比例', icon: Ratio, description: '扩展到目标宽高比' },
  scale: { label: '等比缩放', icon: Maximize2, description: '按倍数扩展画布' },
  offset: { label: '像素偏移', icon: Move, description: '精确控制各方向扩展' },
  upscale: { label: '图片放大', icon: ZoomIn, description: '提高分辨率 (x2/x3/x4)' },
};

const UPSCALE_LABELS: Record<string, string> = {
  x2: '2x',
  x3: '3x',
  x4: '4x',
};

type OutpaintMode = 'ratio' | 'scale' | 'offset' | 'upscale';

function isOutpaintMode(value: string): value is OutpaintMode {
  return value === 'ratio' || value === 'scale' || value === 'offset' || value === 'upscale';
}

export const ImageOutpaintControls: React.FC<ImageOutpaintControlsProps> = ({
  providerId = 'google',
  controls,
  maxImageCount = 4,
  // 单独 props（向后兼容）
  showAdvanced: propShowAdvanced,
  setShowAdvanced: propSetShowAdvanced,
}) => {
  const { schema, loading, error } = useModeControlsSchema(providerId, 'image-outpainting');
  const defaults = schema?.defaults ?? {};

  const availableRatios = useMemo(() => schema?.aspectRatios ?? [], [schema]);
  const outpaintModeOptions = useMemo(
    () =>
      (schema?.paramOptions?.outpaint_mode ?? []).filter(
        (option): option is { label: string; value: OutpaintMode } =>
          typeof option.value === 'string' && isOutpaintMode(option.value)
      ),
    [schema]
  );
  const upscaleOptions = useMemo(
    () => (schema?.paramOptions?.upscale_factor ?? []).filter((option) => typeof option.value === 'string'),
    [schema]
  );
  const numberOfImageOptions = useMemo(
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

  const xScaleRange = schema?.numericRanges?.x_scale;
  const yScaleRange = schema?.numericRanges?.y_scale;
  const leftOffsetRange = schema?.numericRanges?.left_offset;
  const rightOffsetRange = schema?.numericRanges?.right_offset;
  const topOffsetRange = schema?.numericRanges?.top_offset;
  const bottomOffsetRange = schema?.numericRanges?.bottom_offset;
  const seedRange = schema?.numericRanges?.seed;
  const compressionRange = schema?.numericRanges?.output_compression_quality;

  const defaultOutpaintModeRaw =
    (typeof defaults.outpaint_mode === 'string' ? defaults.outpaint_mode : undefined) ??
    (typeof outpaintModeOptions[0]?.value === 'string' ? outpaintModeOptions[0].value : undefined) ??
    'ratio';
  const defaultOutpaintMode: OutpaintMode = isOutpaintMode(defaultOutpaintModeRaw)
    ? defaultOutpaintModeRaw
    : 'ratio';
  const defaultXScale = typeof defaults.x_scale === 'number' ? defaults.x_scale : 1.5;
  const defaultYScale = typeof defaults.y_scale === 'number' ? defaults.y_scale : 1.5;
  const defaultUpscaleFactor =
    (typeof defaults.upscale_factor === 'string' ? defaults.upscale_factor : undefined) ??
    (typeof upscaleOptions[0]?.value === 'string' ? upscaleOptions[0].value : undefined) ??
    'x2';
  const defaultAspectRatio =
    (typeof defaults.aspect_ratio === 'string' ? defaults.aspect_ratio : undefined) ??
    availableRatios[0]?.value ??
    '1:1';
  const defaultImageCount =
    (typeof defaults.number_of_images === 'number' ? defaults.number_of_images : undefined) ??
    numberOfImageOptions[0] ??
    1;
  const defaultOutputMimeType =
    (typeof defaults.output_mime_type === 'string' ? defaults.output_mime_type : undefined) ??
    (typeof outputMimeOptions[0]?.value === 'string' ? outputMimeOptions[0].value : undefined) ??
    'image/png';
  const defaultCompressionQuality =
    typeof defaults.output_compression_quality === 'number' ? defaults.output_compression_quality : 80;
  const defaultSeed = typeof defaults.seed === 'number' ? defaults.seed : -1;

  // 优先使用 controls 对象，fallback 到单独 props
  const showAdvanced = controls?.showAdvanced ?? propShowAdvanced ?? false;
  const setShowAdvanced = controls?.setShowAdvanced ?? propSetShowAdvanced ?? (() => {});

  const outpaintMode: OutpaintMode = controls?.outpaintMode ?? defaultOutpaintMode;
  const setOutpaintMode = controls?.setOutpaintMode ?? (() => {});

  const xScale = controls?.xScale ?? defaultXScale;
  const setXScale = controls?.setXScale ?? (() => {});
  const yScale = controls?.yScale ?? defaultYScale;
  const setYScale = controls?.setYScale ?? (() => {});

  const offsetPixels = controls?.offsetPixels ?? { left: 0, right: 0, top: 0, bottom: 0 };
  const setOffsetPixels = controls?.setOffsetPixels ?? (() => {});

  const updateOffset = (key: 'left' | 'right' | 'top' | 'bottom', value: number) => {
    setOffsetPixels((prev: typeof offsetPixels) => ({ ...prev, [key]: value }));
  };

  const upscaleFactor = controls?.upscaleFactor ?? defaultUpscaleFactor;
  const setUpscaleFactor = controls?.setUpscaleFactor ?? (() => {});

  const aspectRatio = controls?.aspectRatio ?? defaultAspectRatio;
  const setAspectRatio = controls?.setAspectRatio ?? (() => {});
  const numberOfImages = controls?.numberOfImages ?? defaultImageCount;
  const setNumberOfImages = controls?.setNumberOfImages ?? (() => {});

  const outputMimeType = controls?.outputMimeType ?? defaultOutputMimeType;
  const setOutputMimeType = controls?.setOutputMimeType ?? (() => {});
  const outputCompressionQuality = controls?.outputCompressionQuality ?? defaultCompressionQuality;
  const setOutputCompressionQuality = controls?.setOutputCompressionQuality ?? (() => {});
  const negativePrompt = controls?.negativePrompt ?? '';
  const setNegativePrompt = controls?.setNegativePrompt ?? (() => {});
  const seed = controls?.seed ?? defaultSeed;
  const setSeed = controls?.setSeed ?? (() => {});

  const totalOffset = useMemo(() => {
    return offsetPixels.left + offsetPixels.right + offsetPixels.top + offsetPixels.bottom;
  }, [offsetPixels]);

  useEffect(() => {
    const validModes = outpaintModeOptions.map((option) => option.value);
    if (validModes.length > 0 && !validModes.includes(outpaintMode)) {
      setOutpaintMode(validModes[0]);
    }
  }, [outpaintMode, outpaintModeOptions, setOutpaintMode]);

  useEffect(() => {
    const validRatios = availableRatios.map((ratio) => ratio.value);
    if (validRatios.length > 0 && !validRatios.includes(aspectRatio)) {
      setAspectRatio(validRatios[0]);
    }
  }, [aspectRatio, availableRatios, setAspectRatio]);

  useEffect(() => {
    if (numberOfImageOptions.length > 0 && !numberOfImageOptions.includes(numberOfImages)) {
      setNumberOfImages(numberOfImageOptions[0]);
    }
  }, [numberOfImages, numberOfImageOptions, setNumberOfImages]);

  useEffect(() => {
    const validUpscaleFactors = upscaleOptions
      .map((option) => option.value)
      .filter((value): value is string => typeof value === 'string');
    if (validUpscaleFactors.length > 0 && !validUpscaleFactors.includes(upscaleFactor)) {
      setUpscaleFactor(validUpscaleFactors[0] as 'x2' | 'x3' | 'x4');
    }
  }, [upscaleFactor, upscaleOptions, setUpscaleFactor]);

  useEffect(() => {
    const validMimeTypes = outputMimeOptions
      .map((option) => option.value)
      .filter((value): value is string => typeof value === 'string');
    if (validMimeTypes.length > 0 && !validMimeTypes.includes(outputMimeType)) {
      setOutputMimeType(validMimeTypes[0]);
    }
  }, [outputMimeType, outputMimeOptions, setOutputMimeType]);

  return (
    <div className="space-y-4">
      {!loading &&
        (error ||
          outpaintModeOptions.length === 0 ||
          (outpaintMode === 'ratio' && availableRatios.length === 0) ||
          numberOfImageOptions.length === 0) && (
          <div className="text-[10px] text-rose-400">
            扩图参数配置加载失败，请检查后端 `mode_controls_catalog.json`。
          </div>
        )}

      {/* ==================== 扩图模式选择 ==================== */}
      <div className="space-y-2">
        <span className="text-xs text-slate-300">扩图模式</span>
        <div className="grid grid-cols-2 gap-1.5">
          {outpaintModeOptions.map((mode) => {
            const modeValue = mode.value;
            const meta = MODE_META[modeValue] ?? {
              label: mode.label,
              icon: Ratio,
              description: mode.label,
            };
            const Icon = meta.icon;
            return (
              <button
                key={modeValue}
                onClick={() => setOutpaintMode(modeValue)}
                className={`py-2 px-2 text-[10px] font-medium rounded-lg transition-all flex flex-col items-center gap-1 ${
                  outpaintMode === modeValue
                    ? 'bg-orange-600 text-white'
                    : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                }`}
                title={meta.description}
              >
                <Icon size={14} />
                <span>{meta.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ==================== 按模式显示不同参数 ==================== */}
      {outpaintMode === 'ratio' && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Ratio size={12} className="text-orange-400" />
            <span className="text-xs text-slate-300">目标比例</span>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {availableRatios.map((ratio) => (
              <button
                key={ratio.value}
                onClick={() => setAspectRatio(ratio.value)}
                className={`py-1.5 text-[10px] font-medium rounded-lg transition-all ${
                  aspectRatio === ratio.value
                    ? 'bg-orange-600 text-white'
                    : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                }`}
              >
                {ratio.value}
              </button>
            ))}
          </div>
        </div>
      )}

      {outpaintMode === 'scale' && (
        <div className="space-y-3">
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-300">水平缩放</span>
              <span className="text-xs text-orange-400 font-mono">{xScale.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min={xScaleRange?.min ?? 1.1}
              max={xScaleRange?.max ?? 3.0}
              step={xScaleRange?.step ?? 0.1}
              value={xScale}
              onChange={(e) => setXScale(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-orange-500"
            />
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-300">垂直缩放</span>
              <span className="text-xs text-orange-400 font-mono">{yScale.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min={yScaleRange?.min ?? 1.1}
              max={yScaleRange?.max ?? 3.0}
              step={yScaleRange?.step ?? 0.1}
              value={yScale}
              onChange={(e) => setYScale(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-orange-500"
            />
          </div>

          <button
            onClick={() => setYScale(xScale)}
            className="w-full py-1.5 text-xs text-slate-400 hover:text-slate-200 border border-slate-600 rounded-lg transition-colors"
          >
            同步为 {xScale.toFixed(1)}x
          </button>
        </div>
      )}

      {outpaintMode === 'offset' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-300">像素偏移</span>
            <span className="text-[10px] text-orange-400 font-mono">总计 {totalOffset}px</span>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <div className="flex items-center gap-1">
                <ArrowUp size={10} className="text-blue-400" />
                <span className="text-[10px] text-slate-400">上</span>
              </div>
              <input
                type="number"
                min={topOffsetRange?.min ?? 0}
                max={topOffsetRange?.max ?? 1000}
                step={topOffsetRange?.step ?? 1}
                value={offsetPixels.top}
                onChange={(e) => updateOffset('top', Math.max(0, parseInt(e.target.value) || 0))}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200"
              />
            </div>

            <div className="space-y-1">
              <div className="flex items-center gap-1">
                <ArrowDown size={10} className="text-blue-400" />
                <span className="text-[10px] text-slate-400">下</span>
              </div>
              <input
                type="number"
                min={bottomOffsetRange?.min ?? 0}
                max={bottomOffsetRange?.max ?? 1000}
                step={bottomOffsetRange?.step ?? 1}
                value={offsetPixels.bottom}
                onChange={(e) => updateOffset('bottom', Math.max(0, parseInt(e.target.value) || 0))}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200"
              />
            </div>

            <div className="space-y-1">
              <div className="flex items-center gap-1">
                <ArrowLeft size={10} className="text-green-400" />
                <span className="text-[10px] text-slate-400">左</span>
              </div>
              <input
                type="number"
                min={leftOffsetRange?.min ?? 0}
                max={leftOffsetRange?.max ?? 1000}
                step={leftOffsetRange?.step ?? 1}
                value={offsetPixels.left}
                onChange={(e) => updateOffset('left', Math.max(0, parseInt(e.target.value) || 0))}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200"
              />
            </div>

            <div className="space-y-1">
              <div className="flex items-center gap-1">
                <ArrowRight size={10} className="text-green-400" />
                <span className="text-[10px] text-slate-400">右</span>
              </div>
              <input
                type="number"
                min={rightOffsetRange?.min ?? 0}
                max={rightOffsetRange?.max ?? 1000}
                step={rightOffsetRange?.step ?? 1}
                value={offsetPixels.right}
                onChange={(e) => updateOffset('right', Math.max(0, parseInt(e.target.value) || 0))}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200"
              />
            </div>
          </div>

          <div className="flex gap-1.5">
            {[100, 200, 300].map((val) => (
              <button
                key={val}
                onClick={() => {
                  setOffsetPixels({ left: val, right: val, top: val, bottom: val });
                }}
                className="flex-1 py-1.5 text-[10px] bg-slate-700 text-slate-400 hover:bg-slate-600 rounded-lg transition-colors"
              >
                全部 {val}px
              </button>
            ))}
          </div>
        </div>
      )}

      {outpaintMode === 'upscale' && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <ZoomIn size={12} className="text-purple-400" />
            <span className="text-xs text-slate-300">放大倍数</span>
          </div>
          <div className="flex gap-2">
            {upscaleOptions.map((factor) => {
              const value = String(factor.value);
              return (
                <button
                  key={value}
                  onClick={() => setUpscaleFactor(value as 'x2' | 'x3' | 'x4')}
                  className={`flex-1 py-2 text-sm font-bold rounded-lg transition-all ${
                    upscaleFactor === value
                      ? 'bg-purple-600 text-white'
                      : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                  }`}
                  title={factor.label}
                >
                  {UPSCALE_LABELS[value] ?? value}
                </button>
              );
            })}
          </div>
          <div className="text-[10px] text-slate-500 text-center">最大输出: 17MP (约 4K)</div>
        </div>
      )}

      {outpaintMode !== 'upscale' && maxImageCount > 1 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Layers size={12} className="text-blue-400" />
            <span className="text-xs text-slate-300">生成数量</span>
          </div>
          <div className="flex gap-2">
            {numberOfImageOptions.filter((n) => n <= maxImageCount).map((num) => (
              <button
                key={num}
                onClick={() => setNumberOfImages(num)}
                className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                  numberOfImages === num
                    ? 'bg-orange-600 text-white'
                    : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                }`}
              >
                {num}
              </button>
            ))}
          </div>
        </div>
      )}

      {controls && outpaintMode !== 'upscale' && (
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

              {outputMimeType === 'image/jpeg' && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-300">压缩质量</span>
                    <span className="text-xs text-orange-400 font-mono">{outputCompressionQuality}%</span>
                  </div>
                  <input
                    type="range"
                    min={compressionRange?.min ?? 1}
                    max={compressionRange?.max ?? 100}
                    step={compressionRange?.step ?? 1}
                    value={outputCompressionQuality}
                    onChange={(e) => setOutputCompressionQuality(parseInt(e.target.value))}
                    className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-orange-500"
                  />
                </div>
              )}

              <div className="space-y-2">
                <span className="text-xs text-slate-300">负面提示词</span>
                <textarea
                  value={negativePrompt || ''}
                  onChange={(e) => setNegativePrompt(e.target.value)}
                  placeholder="不想出现的元素..."
                  className="w-full h-16 bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-orange-500/50"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-300">Seed</span>
                  <button
                    onClick={() => setSeed(Math.floor(Math.random() * 2147483647))}
                    className="text-xs text-orange-400 hover:text-orange-300"
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
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-orange-500/50"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ImageOutpaintControls;
