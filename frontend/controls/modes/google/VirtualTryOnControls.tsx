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
import React from 'react';
import { Sparkles, Layers } from 'lucide-react';
import { VirtualTryOnControlsProps } from '../../types';
import { IMAGE_COUNTS } from '../../constants/defaults';
import { BASE_STEPS_CONFIG, TRYON_DEFAULTS } from '../../constants/tryon';

export const VirtualTryOnControls: React.FC<VirtualTryOnControlsProps> = ({
  controls,
  baseSteps: propBaseSteps,
  setBaseSteps: propSetBaseSteps,
  numberOfImages: propNumberOfImages,
  setNumberOfImages: propSetNumberOfImages,
}) => {
  // 优先使用 controls 对象，fallback 到单独 props
  const baseSteps = controls?.baseSteps ?? propBaseSteps ?? TRYON_DEFAULTS.baseSteps;
  const setBaseSteps = controls?.setBaseSteps ?? propSetBaseSteps ?? (() => {});
  const numberOfImages = controls?.numberOfImages ?? propNumberOfImages ?? 1;
  const setNumberOfImages = controls?.setNumberOfImages ?? propSetNumberOfImages ?? (() => {});

  return (
    <div className="space-y-4">
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
          min={BASE_STEPS_CONFIG.min}
          max={BASE_STEPS_CONFIG.max}
          step={BASE_STEPS_CONFIG.step}
          value={baseSteps}
          onChange={(e) => setBaseSteps(Number(e.target.value))}
          className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-rose-500"
        />
        <div className="flex justify-between text-[10px] text-slate-500">
          <span>快速 ({BASE_STEPS_CONFIG.min})</span>
          <span>高质量 ({BASE_STEPS_CONFIG.max})</span>
        </div>
      </div>

      {/* 生成数量 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Layers size={12} className="text-blue-400" />
          <span className="text-xs text-slate-300">生成数量</span>
        </div>
        <div className="flex gap-2">
          {IMAGE_COUNTS.map((n) => (
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
