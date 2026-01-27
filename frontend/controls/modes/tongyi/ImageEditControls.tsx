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
import React, { useMemo } from 'react';
import { Ratio, ChevronUp, ChevronDown, Dices, Sparkles } from 'lucide-react';
import { ImageEditControlsProps } from '../../types';
import { 
  TONGYI_EDIT_ASPECT_RATIOS, 
  TONGYI_GEN_RESOLUTION_TIERS,
  getPixelResolution 
} from '../../constants/index';

export const ImageEditControls: React.FC<ImageEditControlsProps> = ({
  controls,
  // 单独 props（向后兼容）
  aspectRatio: propAspectRatio,
  setAspectRatio: propSetAspectRatio,
  resolution: propResolution,
  setResolution: propSetResolution,
  showAdvanced: propShowAdvanced,
  setShowAdvanced: propSetShowAdvanced,
}) => {
  // 优先使用 controls 对象，fallback 到单独 props
  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? '1:1';
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? (() => {});
  const resolution = controls?.resolution ?? propResolution ?? '1K';
  const setResolution = controls?.setResolution ?? propSetResolution ?? (() => {});
  const showAdvanced = controls?.showAdvanced ?? propShowAdvanced ?? false;
  const setShowAdvanced = controls?.setShowAdvanced ?? propSetShowAdvanced ?? (() => {});

  // TongYi 专用参数
  const negativePrompt = controls?.negativePrompt ?? '';
  const setNegativePrompt = controls?.setNegativePrompt ?? (() => {});
  const seed = controls?.seed ?? -1;
  const setSeed = controls?.setSeed ?? (() => {});
  const promptExtend = controls?.promptExtend ?? false;
  const setPromptExtend = controls?.setPromptExtend ?? (() => {});

  const availableRatios = TONGYI_EDIT_ASPECT_RATIOS;
  const availableResolutionTiers = TONGYI_GEN_RESOLUTION_TIERS;
  
  // 计算当前像素分辨率
  const currentPixelResolution = useMemo(() => {
    return getPixelResolution(aspectRatio, resolution, 'tongyi').replace('*', '×');
  }, [aspectRatio, resolution]);

  return (
    <div className="space-y-4">
      {/* ==================== 基础参数 ==================== */}
      
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
          {availableRatios.slice(0, 10).map((ratio) => (
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
              const tierPixelRes = getPixelResolution(aspectRatio, tier.value, 'tongyi').replace('*', '×');
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
            <div className="space-y-2">
              <span className="text-xs text-slate-300">负面提示词</span>
              <textarea
                value={negativePrompt}
                onChange={(e) => setNegativePrompt(e.target.value)}
                placeholder="不想出现的元素..."
                className="w-full h-16 bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-pink-500/50"
              />
            </div>

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
                min="0"
                max="2147483647"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-pink-500/50"
              />
            </div>

            {/* 增强提示词 - Switch 开关 */}
            <div className="flex items-center justify-between py-1">
              <div className="flex items-center gap-2">
                <Sparkles size={12} className="text-indigo-400" />
                <span className="text-xs text-slate-300">AI 增强提示词</span>
              </div>
              <div
                onClick={() => setPromptExtend(!promptExtend)}
                className={`w-10 h-6 flex items-center rounded-full p-1 cursor-pointer transition-colors duration-200 ${
                  promptExtend ? 'bg-indigo-600' : 'bg-slate-600'
                }`}
              >
                <div
                  className={`w-4 h-4 bg-white rounded-full shadow-md transform transition-transform duration-200 ${
                    promptExtend ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ImageEditControls;
