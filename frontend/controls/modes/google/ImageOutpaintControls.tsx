/**
 * Google 图像扩展控件（仅 Panel 模式）
 * 
 * 用于右侧参数面板，通过 ModeControlsCoordinator 分发
 */
import React from 'react';
import { Expand, ChevronUp, ChevronDown, FileImage, Dices } from 'lucide-react';
import { ImageOutpaintControlsProps } from '../../types';

export const ImageOutpaintControls: React.FC<ImageOutpaintControlsProps> = ({
  controls,
  // 单独 props（向后兼容）
  outPaintingMode: propOutPaintingMode,
  setOutPaintingMode: propSetOutPaintingMode,
  scaleFactor: propScaleFactor,
  setScaleFactor: propSetScaleFactor,
  offsetPixels: propOffsetPixels,
  setOffsetPixels: propSetOffsetPixels,
  showAdvanced: propShowAdvanced,
  setShowAdvanced: propSetShowAdvanced,
}) => {
  // 优先使用 controls 对象，fallback 到单独 props
  const outPaintingMode = controls?.outPaintingMode ?? propOutPaintingMode ?? 'scale';
  const setOutPaintingMode = controls?.setOutPaintingMode ?? propSetOutPaintingMode ?? (() => {});
  const scaleFactor = controls?.scaleFactor ?? propScaleFactor ?? 1.5;
  const setScaleFactor = controls?.setScaleFactor ?? propSetScaleFactor ?? (() => {});
  const offsetPixels = controls?.offsetPixels ?? propOffsetPixels ?? { top: 0, bottom: 0, left: 0, right: 0 };
  const setOffsetPixels = controls?.setOffsetPixels ?? propSetOffsetPixels ?? (() => {});
  const showAdvanced = controls?.showAdvanced ?? propShowAdvanced ?? false;
  const setShowAdvanced = controls?.setShowAdvanced ?? propSetShowAdvanced ?? (() => {});

  return (
    <div className="space-y-4">
      {/* ==================== 基础参数 ==================== */}
      
      {/* 扩展模式选择 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Expand size={12} className="text-orange-400" />
          <span className="text-xs text-slate-300">扩展模式</span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setOutPaintingMode('scale')}
            className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
              outPaintingMode === 'scale'
                ? 'bg-orange-600 text-white'
                : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
            }`}
          >
            等比缩放
          </button>
          <button
            onClick={() => setOutPaintingMode('offset')}
            className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
              outPaintingMode === 'offset'
                ? 'bg-orange-600 text-white'
                : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
            }`}
          >
            自定义偏移
          </button>
        </div>
      </div>

      {/* 缩放因子（Scale 模式） */}
      {outPaintingMode === 'scale' && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-300">缩放因子</span>
            <span className="text-xs text-orange-400 font-mono">{scaleFactor.toFixed(1)}x</span>
          </div>
          <input
            type="range"
            min="1.0"
            max="4.0"
            step="0.1"
            value={scaleFactor}
            onChange={(e) => setScaleFactor(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-orange-500"
          />
          <div className="flex justify-between text-[10px] text-slate-500">
            <span>1.0x</span>
            <span>2.0x</span>
            <span>3.0x</span>
            <span>4.0x</span>
          </div>
        </div>
      )}

      {/* 偏移像素（Offset 模式） */}
      {outPaintingMode === 'offset' && (
        <div className="space-y-3">
          <span className="text-xs text-slate-300">偏移像素</span>
          <div className="grid grid-cols-2 gap-2">
            {(['top', 'bottom', 'left', 'right'] as const).map((dir) => (
              <div key={dir} className="space-y-1">
                <label className="text-[10px] text-slate-500 uppercase">{
                  dir === 'top' ? '上' : dir === 'bottom' ? '下' : dir === 'left' ? '左' : '右'
                }</label>
                <input
                  type="number"
                  min="0"
                  max="2000"
                  step="64"
                  value={offsetPixels[dir]}
                  onChange={(e) => setOffsetPixels((prev: typeof offsetPixels) => ({ 
                    ...prev, 
                    [dir]: parseInt(e.target.value) || 0 
                  }))}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-orange-500/50"
                />
              </div>
            ))}
          </div>
          {/* 快捷预设 */}
          <div className="flex gap-2">
            {[64, 128, 256, 512].map((val) => (
              <button
                key={val}
                onClick={() => setOffsetPixels({ top: val, bottom: val, left: val, right: val })}
                className="flex-1 py-1 text-[10px] font-medium rounded bg-slate-800 text-slate-400 hover:bg-slate-700 transition-colors"
              >
                {val}px
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
                    step="5"
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
