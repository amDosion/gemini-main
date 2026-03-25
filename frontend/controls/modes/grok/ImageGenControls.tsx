/**
 * Grok 图像生成专用控件（仅 Panel 模式）
 *
 * Grok 特点：
 * - 尺寸选择：5 种固定尺寸（以像素格式传递，如 1024x1024）
 * - 图片数量：1-10 张（滑块）
 */
import React, { useEffect, useMemo } from 'react';
import { Ratio, Layers } from 'lucide-react';
import { ImageGenControlsProps } from '../../types';
import { useModeControlsSchema } from '../../../hooks/useModeControlsSchema';

const GROK_SIZE_OPTIONS = [
  { label: '1:1 (1024\u00d71024)', value: '1024x1024' },
  { label: '16:9 (1280\u00d7720)', value: '1280x720' },
  { label: '9:16 (720\u00d71280)', value: '720x1280' },
  { label: '3:2 (1792\u00d71024)', value: '1792x1024' },
  { label: '2:3 (1024\u00d71792)', value: '1024x1792' },
];

const DEFAULT_SIZE = '1024x1024';
const DEFAULT_IMAGE_COUNT = 1;
const MAX_IMAGE_COUNT = 10;

export const ImageGenControls: React.FC<ImageGenControlsProps> = (props) => {
  const {
    providerId = 'grok',
    currentModel,
    controls,
    // 单独 props（向后兼容）
    aspectRatio: propAspectRatio,
    setAspectRatio: propSetAspectRatio,
    numberOfImages: propNumberOfImages,
    setNumberOfImages: propSetNumberOfImages,
  } = props;

  const { schema, loading, error } = useModeControlsSchema(providerId, 'image-gen', currentModel?.id);

  const availableSizes = useMemo(() => {
    const schemaRatios = schema?.aspectRatios;
    if (schemaRatios && schemaRatios.length > 0) return schemaRatios;
    return GROK_SIZE_OPTIONS;
  }, [schema]);

  const defaults = schema?.defaults ?? {};
  const defaultSize =
    (typeof defaults.aspect_ratio === 'string' ? defaults.aspect_ratio : undefined) ??
    (typeof defaults.size === 'string' ? defaults.size : undefined) ??
    availableSizes[0]?.value ??
    DEFAULT_SIZE;

  const maxCount = useMemo(() => {
    const range = schema?.numericRanges?.number_of_images;
    return range?.max ?? MAX_IMAGE_COUNT;
  }, [schema]);

  const defaultImageCount = useMemo(() => {
    const d = defaults.number_of_images;
    if (typeof d === 'number') return d;
    return DEFAULT_IMAGE_COUNT;
  }, [defaults]);

  // 优先使用 controls 对象，fallback 到单独 props
  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? defaultSize;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? (() => {});
  const numberOfImages = controls?.numberOfImages ?? propNumberOfImages ?? defaultImageCount;
  const setNumberOfImages = controls?.setNumberOfImages ?? propSetNumberOfImages ?? (() => {});

  // 校验当前尺寸是否在可用选项中
  useEffect(() => {
    const validSizes = availableSizes.map((s) => s.value);
    if (validSizes.length > 0 && !validSizes.includes(aspectRatio)) {
      setAspectRatio(validSizes[0]);
    }
  }, [availableSizes, aspectRatio, setAspectRatio]);

  // 校验图片数量范围
  useEffect(() => {
    if (numberOfImages > maxCount) {
      setNumberOfImages(maxCount);
    } else if (numberOfImages < 1) {
      setNumberOfImages(1);
    }
  }, [numberOfImages, maxCount, setNumberOfImages]);

  return (
    <div className="space-y-4">
      {!loading && (error || availableSizes.length === 0) && (
        <div className="text-[10px] text-rose-400">
          尺寸配置加载失败，请检查后端 mode_controls_catalog.json。
        </div>
      )}

      {/* 图片尺寸 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Ratio size={12} className="text-orange-400" />
          <span className="text-xs text-slate-300">图片尺寸</span>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {availableSizes.map((size) => (
            <button
              key={size.value}
              onClick={() => setAspectRatio(size.value)}
              className={`py-1.5 text-[10px] font-medium rounded-lg transition-all ${
                aspectRatio === size.value
                  ? 'bg-orange-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {size.label}
            </button>
          ))}
        </div>
      </div>

      {/* 生成数量 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers size={12} className="text-blue-400" />
            <span className="text-xs text-slate-300">生成数量</span>
          </div>
          <span className="text-xs text-blue-400 font-mono font-bold">{numberOfImages}</span>
        </div>
        <input
          type="range"
          min={1}
          max={maxCount}
          step={1}
          value={numberOfImages}
          onChange={(e) => setNumberOfImages(parseInt(e.target.value))}
          className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-blue-500"
        />
        <div className="flex justify-between text-[10px] text-slate-500 px-0.5">
          <span>1</span>
          <span>{maxCount}</span>
        </div>
      </div>

      {/* Grok 信息提示 */}
      <div className="text-[10px] text-slate-500 italic">
        Grok：支持生成 1-{maxCount} 张图片
      </div>
    </div>
  );
};

export default ImageGenControls;
