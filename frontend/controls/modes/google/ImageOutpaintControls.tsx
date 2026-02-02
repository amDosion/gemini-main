/**
 * Google 图像扩展控件（仅 Panel 模式）
 *
 * 支持多种扩图模式：
 * - ratio: 按目标比例扩图
 * - scale: 按缩放因子扩图
 * - offset: 按像素偏移扩图
 * - upscale: 图片放大 (x2/x3/x4)
 */
import React, { useMemo } from 'react';
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
import {
  GOOGLE_EDIT_ASPECT_RATIOS,
  IMAGE_COUNTS,
} from '../../constants/index';

// 扩图模式选项
const OUTPAINT_MODES = [
  { value: 'ratio', label: '按比例', icon: Ratio, description: '扩展到目标宽高比' },
  { value: 'scale', label: '等比缩放', icon: Maximize2, description: '按倍数扩展画布' },
  { value: 'offset', label: '像素偏移', icon: Move, description: '精确控制各方向扩展' },
  { value: 'upscale', label: '图片放大', icon: ZoomIn, description: '提高分辨率 (x2/x3/x4)' },
];

// 放大倍数选项
const UPSCALE_FACTORS = [
  { value: 'x2', label: '2x', description: '2倍放大' },
  { value: 'x3', label: '3x', description: '3倍放大' },
  { value: 'x4', label: '4x', description: '4倍放大' },
];

export const ImageOutpaintControls: React.FC<ImageOutpaintControlsProps> = ({
  controls,
  maxImageCount = 4,
  // 单独 props（向后兼容）
  showAdvanced: propShowAdvanced,
  setShowAdvanced: propSetShowAdvanced,
}) => {
  // 优先使用 controls 对象，fallback 到单独 props
  const showAdvanced = controls?.showAdvanced ?? propShowAdvanced ?? false;
  const setShowAdvanced = controls?.setShowAdvanced ?? propSetShowAdvanced ?? (() => {});

  // 扩图模式状态 - 优先使用 controls
  const outpaintMode = controls?.outpaintMode ?? 'ratio';
  const setOutpaintMode = controls?.setOutpaintMode ?? (() => {});

  // Scale 模式参数 - 优先使用 controls
  const xScale = controls?.xScale ?? 1.5;
  const setXScale = controls?.setXScale ?? (() => {});
  const yScale = controls?.yScale ?? 1.5;
  const setYScale = controls?.setYScale ?? (() => {});

  // Offset 模式参数 - 使用 controls.offsetPixels
  const offsetPixels = controls?.offsetPixels ?? { left: 0, right: 0, top: 0, bottom: 0 };
  const setOffsetPixels = controls?.setOffsetPixels ?? (() => {});

  // 辅助函数：更新单个偏移值
  const updateOffset = (key: 'left' | 'right' | 'top' | 'bottom', value: number) => {
    setOffsetPixels((prev: typeof offsetPixels) => ({ ...prev, [key]: value }));
  };

  // Upscale 模式参数 - 优先使用 controls
  const upscaleFactor = controls?.upscaleFactor ?? 'x2';
  const setUpscaleFactor = controls?.setUpscaleFactor ?? (() => {});

  // 从 controls 获取共享参数
  const aspectRatio = controls?.aspectRatio ?? '1:1';
  const setAspectRatio = controls?.setAspectRatio ?? (() => {});
  const numberOfImages = controls?.numberOfImages ?? 1;
  const setNumberOfImages = controls?.setNumberOfImages ?? (() => {});

  const availableRatios = GOOGLE_EDIT_ASPECT_RATIOS;

  // 计算总偏移
  const totalOffset = useMemo(() => {
    return offsetPixels.left + offsetPixels.right + offsetPixels.top + offsetPixels.bottom;
  }, [offsetPixels]);

  return (
    <div className="space-y-4">
      {/* ==================== 扩图模式选择 ==================== */}
      <div className="space-y-2">
        <span className="text-xs text-slate-300">扩图模式</span>
        <div className="grid grid-cols-2 gap-1.5">
          {OUTPAINT_MODES.map((mode) => {
            const Icon = mode.icon;
            return (
              <button
                key={mode.value}
                onClick={() => setOutpaintMode(mode.value as typeof outpaintMode)}
                className={`py-2 px-2 text-[10px] font-medium rounded-lg transition-all flex flex-col items-center gap-1 ${
                  outpaintMode === mode.value
                    ? 'bg-orange-600 text-white'
                    : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                }`}
                title={mode.description}
              >
                <Icon size={14} />
                <span>{mode.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ==================== 按模式显示不同参数 ==================== */}

      {/* Ratio 模式：目标比例 */}
      {outpaintMode === 'ratio' && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Ratio size={12} className="text-orange-400" />
            <span className="text-xs text-slate-300">目标比例</span>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {availableRatios.slice(0, 10).map((ratio) => (
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

      {/* Scale 模式：缩放因子 */}
      {outpaintMode === 'scale' && (
        <div className="space-y-3">
          {/* X Scale */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-300">水平缩放</span>
              <span className="text-xs text-orange-400 font-mono">{xScale.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="1.1"
              max="3.0"
              step="0.1"
              value={xScale}
              onChange={(e) => setXScale(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-orange-500"
            />
          </div>

          {/* Y Scale */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-300">垂直缩放</span>
              <span className="text-xs text-orange-400 font-mono">{yScale.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="1.1"
              max="3.0"
              step="0.1"
              value={yScale}
              onChange={(e) => setYScale(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-orange-500"
            />
          </div>

          {/* 锁定比例按钮 */}
          <button
            onClick={() => setYScale(xScale)}
            className="w-full py-1.5 text-xs text-slate-400 hover:text-slate-200 border border-slate-600 rounded-lg transition-colors"
          >
            同步为 {xScale.toFixed(1)}x
          </button>
        </div>
      )}

      {/* Offset 模式：像素偏移 */}
      {outpaintMode === 'offset' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-300">像素偏移</span>
            <span className="text-[10px] text-orange-400 font-mono">总计 {totalOffset}px</span>
          </div>

          {/* 2列2行布局 */}
          <div className="grid grid-cols-2 gap-2">
            {/* 上 */}
            <div className="space-y-1">
              <div className="flex items-center gap-1">
                <ArrowUp size={10} className="text-blue-400" />
                <span className="text-[10px] text-slate-400">上</span>
              </div>
              <input
                type="number"
                min="0"
                max="1000"
                value={offsetPixels.top}
                onChange={(e) => updateOffset('top', Math.max(0, parseInt(e.target.value) || 0))}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200"
              />
            </div>

            {/* 下 */}
            <div className="space-y-1">
              <div className="flex items-center gap-1">
                <ArrowDown size={10} className="text-blue-400" />
                <span className="text-[10px] text-slate-400">下</span>
              </div>
              <input
                type="number"
                min="0"
                max="1000"
                value={offsetPixels.bottom}
                onChange={(e) => updateOffset('bottom', Math.max(0, parseInt(e.target.value) || 0))}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200"
              />
            </div>

            {/* 左 */}
            <div className="space-y-1">
              <div className="flex items-center gap-1">
                <ArrowLeft size={10} className="text-green-400" />
                <span className="text-[10px] text-slate-400">左</span>
              </div>
              <input
                type="number"
                min="0"
                max="1000"
                value={offsetPixels.left}
                onChange={(e) => updateOffset('left', Math.max(0, parseInt(e.target.value) || 0))}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200"
              />
            </div>

            {/* 右 */}
            <div className="space-y-1">
              <div className="flex items-center gap-1">
                <ArrowRight size={10} className="text-green-400" />
                <span className="text-[10px] text-slate-400">右</span>
              </div>
              <input
                type="number"
                min="0"
                max="1000"
                value={offsetPixels.right}
                onChange={(e) => updateOffset('right', Math.max(0, parseInt(e.target.value) || 0))}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200"
              />
            </div>
          </div>

          {/* 快捷预设 */}
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

      {/* Upscale 模式：放大倍数 */}
      {outpaintMode === 'upscale' && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <ZoomIn size={12} className="text-purple-400" />
            <span className="text-xs text-slate-300">放大倍数</span>
          </div>
          <div className="flex gap-2">
            {UPSCALE_FACTORS.map((factor) => (
              <button
                key={factor.value}
                onClick={() => setUpscaleFactor(factor.value as 'x2' | 'x3' | 'x4')}
                className={`flex-1 py-2 text-sm font-bold rounded-lg transition-all ${
                  upscaleFactor === factor.value
                    ? 'bg-purple-600 text-white'
                    : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                }`}
                title={factor.description}
              >
                {factor.label}
              </button>
            ))}
          </div>
          <div className="text-[10px] text-slate-500 text-center">
            最大输出: 17MP (约 4K)
          </div>
        </div>
      )}

      {/* ==================== 生成数量（非 upscale 模式） ==================== */}
      {outpaintMode !== 'upscale' && maxImageCount > 1 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Layers size={12} className="text-blue-400" />
            <span className="text-xs text-slate-300">生成数量</span>
          </div>
          <div className="flex gap-2">
            {IMAGE_COUNTS.filter(n => n <= maxImageCount).map((num) => (
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

      {/* ==================== 高级参数折叠区 ==================== */}
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
                      onClick={() => controls.setOutputMimeType?.(opt.value)}
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
                    <span className="text-xs text-orange-400 font-mono">{controls.outputCompressionQuality}%</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="100"
                    step="1"
                    value={controls.outputCompressionQuality}
                    onChange={(e) => controls.setOutputCompressionQuality?.(parseInt(e.target.value))}
                    className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-orange-500"
                  />
                </div>
              )}

              {/* 负面提示词 */}
              <div className="space-y-2">
                <span className="text-xs text-slate-300">负面提示词</span>
                <textarea
                  value={controls.negativePrompt || ''}
                  onChange={(e) => controls.setNegativePrompt?.(e.target.value)}
                  placeholder="不想出现的元素..."
                  className="w-full h-16 bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-orange-500/50"
                />
              </div>

              {/* Seed */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-300">Seed</span>
                  <button
                    onClick={() => controls.setSeed?.(Math.floor(Math.random() * 2147483647))}
                    className="text-xs text-orange-400 hover:text-orange-300"
                    title="随机种子"
                  >
                    <Dices size={14} />
                  </button>
                </div>
                <input
                  type="number"
                  value={controls.seed === -1 ? '' : controls.seed}
                  onChange={(e) => controls.setSeed?.(e.target.value ? parseInt(e.target.value) : -1)}
                  placeholder="随机 (-1)"
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
