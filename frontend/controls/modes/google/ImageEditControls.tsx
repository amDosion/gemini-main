/**
 * Google 图像编辑控件（仅 Panel 模式）
 * 
 * 用于右侧参数面板，通过 ModeControlsCoordinator 分发
 */
import React, { useMemo } from 'react';
import { Ratio, ChevronUp, ChevronDown, FileImage, Dices } from 'lucide-react';
import { ImageEditControlsProps } from '../../types';
import { 
  GOOGLE_EDIT_ASPECT_RATIOS, 
  GOOGLE_EDIT_RESOLUTION_TIERS, 
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

  const availableRatios = GOOGLE_EDIT_ASPECT_RATIOS;
  const availableResolutionTiers = GOOGLE_EDIT_RESOLUTION_TIERS;
  
  // 计算当前像素分辨率
  const currentPixelResolution = useMemo(() => {
    return getPixelResolution(aspectRatio, resolution, 'google').replace('*', '×');
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

      {/* 分辨率档位（编辑模式支持 4K） */}
      {availableResolutionTiers.length > 0 && (
        <div className="space-y-2">
          <span className="text-xs text-slate-300">分辨率</span>
          <div className="flex gap-2">
            {availableResolutionTiers.map((tier) => {
              const tierPixelRes = getPixelResolution(aspectRatio, tier.value, 'google').replace('*', '×');
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
                  {[{ value: 'image/png', label: 'PNG' }, { value: 'image/jpeg', label: 'JPEG' }].map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => controls.setOutputMimeType(opt.value)}
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
                    min="1"
                    max="100"
                    step="5"
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
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-pink-500/50"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ImageEditControls;
