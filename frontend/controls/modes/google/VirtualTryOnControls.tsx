/**
 * Google 虚拟试衣模式参数控件（仅 Panel 模式）
 *
 * 用于右侧参数面板，通过 ModeControlsCoordinator 分发
 *
 * 官方支持的参数（来源: docs/virtual_try_on_sdk_usage_zh.md）:
 * - base_steps: 质量步数（数值越高质量越好）- 滑块控件
 * - number_of_images: 生成数量 - 用户可选
 * - output_mime_type: 固定 image/jpeg（不提供 UI）
 * - output_compression_quality: 固定 100（不提供 UI）
 * 
 * 注意: 服装类型（上装/下装/全身）不是官方 API 支持的参数
 */
import React, { useEffect, useMemo } from 'react';
import { Sparkles, Layers } from 'lucide-react';
import { VirtualTryOnControlsProps } from '../../types';
import { useModeControlsSchema } from '../../../hooks/useModeControlsSchema';

export const VirtualTryOnControls: React.FC<VirtualTryOnControlsProps> = ({
  providerId = 'google',
  controls,
  baseSteps: propBaseSteps,
  setBaseSteps: propSetBaseSteps,
  numberOfImages: propNumberOfImages,
  setNumberOfImages: propSetNumberOfImages,
}) => {
  const { schema, loading, error } = useModeControlsSchema(providerId, 'virtual-try-on');
  const defaults = schema?.defaults ?? {};
  const numberOfImageOptions = useMemo(
    () =>
      (schema?.paramOptions?.number_of_images ?? [])
        .map((option) => option.value)
        .filter((value): value is number => typeof value === 'number'),
    [schema]
  );
  const baseStepsRange = schema?.numericRanges?.base_steps;

  const minBaseSteps = baseStepsRange?.min ?? 8;
  const maxBaseSteps = baseStepsRange?.max ?? 48;
  const stepBaseSteps = baseStepsRange?.step ?? 8;
  const defaultBaseSteps =
    (typeof defaults.base_steps === 'number' ? defaults.base_steps : undefined) ?? minBaseSteps;
  const defaultImageCount =
    (typeof defaults.number_of_images === 'number' ? defaults.number_of_images : undefined) ??
    numberOfImageOptions[0] ??
    1;

  const baseSteps = controls?.baseSteps ?? propBaseSteps ?? defaultBaseSteps;
  const setBaseSteps = controls?.setBaseSteps ?? propSetBaseSteps ?? (() => {});
  const numberOfImages = controls?.numberOfImages ?? propNumberOfImages ?? defaultImageCount;
  const setNumberOfImages = controls?.setNumberOfImages ?? propSetNumberOfImages ?? (() => {});

  useEffect(() => {
    if (baseSteps < minBaseSteps) {
      setBaseSteps(minBaseSteps);
      return;
    }
    if (baseSteps > maxBaseSteps) {
      setBaseSteps(maxBaseSteps);
      return;
    }
    const offset = (baseSteps - minBaseSteps) / stepBaseSteps;
    if (Math.abs(offset - Math.round(offset)) > 1e-6) {
      setBaseSteps(defaultBaseSteps);
    }
  }, [baseSteps, minBaseSteps, maxBaseSteps, stepBaseSteps, defaultBaseSteps, setBaseSteps]);

  useEffect(() => {
    if (numberOfImageOptions.length > 0 && !numberOfImageOptions.includes(numberOfImages)) {
      setNumberOfImages(numberOfImageOptions[0]);
    }
  }, [numberOfImages, numberOfImageOptions, setNumberOfImages]);

  return (
    <div className="space-y-4">
      {!loading && (error || numberOfImageOptions.length === 0) && (
        <div className="text-[10px] text-rose-400">
          试衣参数配置加载失败，请检查后端 `mode_controls_catalog.json`。
        </div>
      )}
      {/* 质量步数 - 滑块 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles size={12} className="text-rose-400" />
            <span className="text-xs text-slate-300">质量步数</span>
          </div>
          <span className="text-xs text-rose-400 font-mono">{baseSteps} 步</span>
        </div>
        <input
          type="range"
          min={minBaseSteps}
          max={maxBaseSteps}
          step={stepBaseSteps}
          value={baseSteps}
          onChange={(e) => setBaseSteps(Number(e.target.value))}
          className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-rose-500"
        />
        <div className="flex justify-between text-[10px] text-slate-500">
          <span>快速 ({minBaseSteps})</span>
          <span>高质量 ({maxBaseSteps})</span>
        </div>
      </div>

      {/* 生成数量 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Layers size={12} className="text-blue-400" />
          <span className="text-xs text-slate-300">生成数量</span>
        </div>
        <div className="flex gap-2">
          {numberOfImageOptions.map((n) => (
            <button
              key={n}
              onClick={() => setNumberOfImages(n)}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                numberOfImages === n
                  ? 'bg-rose-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default VirtualTryOnControls;
