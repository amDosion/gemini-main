/**
 * Google 掩码编辑控件（仅 Panel 模式）
 * 
 * 用于右侧参数面板，专门用于 image-mask-edit 模式
 * 基于后端 mask_edit_service.py 的参数设计
 */
import React, { useMemo } from 'react';
import { 
  ChevronUp, ChevronDown, FileImage, Layers, 
  SlidersHorizontal, Sparkles, X
} from 'lucide-react';
import { ImageMaskEditControlsProps } from '../../types';
import { DEFAULT_CONTROLS, IMAGE_COUNTS, OUTPUT_MIME_OPTIONS } from '../../constants/index';

// 编辑模式选项（对应后端 mask_edit_service.py 的 EDIT_MODES）
const EDIT_MODES = [
  { value: 'EDIT_MODE_INPAINT_INSERTION', label: '插入内容' },
  { value: 'EDIT_MODE_INPAINT_REMOVAL', label: '移除内容' },
  { value: 'EDIT_MODE_OUTPAINT', label: '扩展图像' },
  { value: 'EDIT_MODE_BGSWAP', label: '背景替换' },
] as const;

export const ImageMaskEditControls: React.FC<ImageMaskEditControlsProps> = ({
  controls,
  // 单独 props（向后兼容）
  editMode: propEditMode,
  setEditMode: propSetEditMode,
  maskDilation: propMaskDilation,
  setMaskDilation: propSetMaskDilation,
  guidanceScale: propGuidanceScale,
  setGuidanceScale: propSetGuidanceScale,
  numberOfImages: propNumberOfImages,
  setNumberOfImages: propSetNumberOfImages,
  negativePrompt: propNegativePrompt,
  setNegativePrompt: propSetNegativePrompt,
  outputMimeType: propOutputMimeType,
  setOutputMimeType: propSetOutputMimeType,
  outputCompressionQuality: propOutputCompressionQuality,
  setOutputCompressionQuality: propSetOutputCompressionQuality,
  showAdvanced: propShowAdvanced,
  setShowAdvanced: propSetShowAdvanced,
}) => {
  // 优先使用 controls 对象，fallback 到单独 props
  const editMode = controls?.editMode ?? propEditMode ?? DEFAULT_CONTROLS.editMode;
  const setEditMode = controls?.setEditMode ?? propSetEditMode ?? (() => {});
  const maskDilation = controls?.maskDilation ?? propMaskDilation ?? DEFAULT_CONTROLS.maskDilation;
  const setMaskDilation = controls?.setMaskDilation ?? propSetMaskDilation ?? (() => {});
  const guidanceScale = controls?.guidanceScale ?? propGuidanceScale ?? DEFAULT_CONTROLS.guidanceScale;
  const setGuidanceScale = controls?.setGuidanceScale ?? propSetGuidanceScale ?? (() => {});
  const numberOfImages = controls?.numberOfImages ?? propNumberOfImages ?? DEFAULT_CONTROLS.numberOfImages;
  const setNumberOfImages = controls?.setNumberOfImages ?? propSetNumberOfImages ?? (() => {});
  const negativePrompt = controls?.negativePrompt ?? propNegativePrompt ?? '';
  const setNegativePrompt = controls?.setNegativePrompt ?? propSetNegativePrompt ?? (() => {});
  const outputMimeType = controls?.outputMimeType ?? propOutputMimeType ?? DEFAULT_CONTROLS.outputMimeType;
  const setOutputMimeType = controls?.setOutputMimeType ?? propSetOutputMimeType ?? (() => {});
  const outputCompressionQuality = controls?.outputCompressionQuality ?? propOutputCompressionQuality ?? DEFAULT_CONTROLS.outputCompressionQuality;
  const setOutputCompressionQuality = controls?.setOutputCompressionQuality ?? propSetOutputCompressionQuality ?? (() => {});
  const showAdvanced = controls?.showAdvanced ?? propShowAdvanced ?? false;
  const setShowAdvanced = controls?.setShowAdvanced ?? propSetShowAdvanced ?? (() => {});

  return (
    <div className="space-y-4">
      {/* ==================== 基础参数 ==================== */}
      
      {/* 编辑模式 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={12} className="text-pink-400" />
          <span className="text-xs text-slate-300">编辑模式</span>
        </div>
        <select
          value={editMode}
          onChange={(e) => setEditMode(e.target.value)}
          className="w-full px-3 py-2 text-xs bg-slate-800 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-pink-500"
        >
          {EDIT_MODES.map((mode) => (
            <option key={mode.value} value={mode.value}>{mode.label}</option>
          ))}
        </select>
      </div>

      {/* 生成数量 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Layers size={12} className="text-emerald-400" />
          <span className="text-xs text-slate-300">生成数量</span>
        </div>
        <div className="flex gap-2">
          {IMAGE_COUNTS.map((count) => (
            <button
              key={count}
              onClick={() => setNumberOfImages(count)}
              className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
                numberOfImages === count
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {count}
            </button>
          ))}
        </div>
      </div>

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
              {/* 掩码膨胀系数 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-300">掩码膨胀系数</span>
                  <span className="text-xs text-pink-400 font-mono">{maskDilation.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={maskDilation}
                  onChange={(e) => setMaskDilation(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-pink-500"
                />
                <p className="text-[10px] text-slate-500">控制掩码边缘的扩展范围 (0.0-1.0)</p>
              </div>

              {/* 引导比例 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-300">引导比例</span>
                  <span className="text-xs text-pink-400 font-mono">{guidanceScale.toFixed(1)}</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="20"
                  step="0.5"
                  value={guidanceScale}
                  onChange={(e) => setGuidanceScale(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-pink-500"
                />
                <p className="text-[10px] text-slate-500">控制生成结果与提示词的匹配程度 (1.0-20.0)</p>
              </div>

              {/* 输出格式 */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <FileImage size={12} className="text-cyan-400" />
                  <span className="text-xs text-slate-300">输出格式</span>
                </div>
                <div className="flex gap-2">
                  {OUTPUT_MIME_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setOutputMimeType(opt.value)}
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
                    <span className="text-xs text-pink-400 font-mono">{outputCompressionQuality}%</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="100"
                    step="1"
                    value={outputCompressionQuality}
                    onChange={(e) => setOutputCompressionQuality(parseInt(e.target.value))}
                    className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-pink-500"
                  />
                </div>
              )}

              {/* 负面提示词 */}
              <div className="space-y-2">
                <span className="text-xs text-slate-300">负面提示词</span>
                <textarea
                  value={negativePrompt || ''}
                  onChange={(e) => setNegativePrompt(e.target.value)}
                  placeholder="不想出现的元素..."
                  className="w-full h-16 bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-pink-500/50"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ImageMaskEditControls;
