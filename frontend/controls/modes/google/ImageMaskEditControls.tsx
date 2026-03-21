/**
 * Google 掩码编辑控件（仅 Panel 模式）
 *
 * 用于右侧参数面板，专门用于 image-mask-edit 模式
 * 基于后端 mask_edit_service.py 的参数设计
 */
import React, { useEffect, useMemo } from 'react';
import {
  ChevronUp, ChevronDown, FileImage, Layers,
  SlidersHorizontal, Sparkles, X
} from 'lucide-react';
import { ImageMaskEditControlsProps } from '../../types';
import { useModeControlsSchema } from '../../../hooks/useModeControlsSchema';

export const ImageMaskEditControls: React.FC<ImageMaskEditControlsProps> = ({
  providerId = 'google',
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
  const { schema, loading, error } = useModeControlsSchema(providerId, 'image-mask-edit');
  const defaults = schema?.defaults ?? {};
  const editModeOptions = useMemo(
    () =>
      (schema?.paramOptions?.edit_mode ?? []).filter(
        (option): option is { label: string; value: string } => typeof option.value === 'string'
      ),
    [schema]
  );
  const imageCountOptions = useMemo(
    () =>
      (schema?.paramOptions?.number_of_images ?? [])
        .map((option) => option.value)
        .filter((value): value is number => typeof value === 'number'),
    [schema]
  );
  const outputMimeOptions = useMemo(
    () =>
      (schema?.paramOptions?.output_mime_type ?? []).filter(
        (option): option is { label: string; value: string } => typeof option.value === 'string'
      ),
    [schema]
  );

  const maskDilationRange = schema?.numericRanges?.mask_dilation;
  const guidanceScaleRange = schema?.numericRanges?.guidance_scale;
  const compressionRange = schema?.numericRanges?.output_compression_quality;

  const defaultEditMode =
    (typeof defaults.edit_mode === 'string' ? defaults.edit_mode : undefined) ??
    (typeof editModeOptions[0]?.value === 'string' ? editModeOptions[0].value : undefined) ??
    'EDIT_MODE_INPAINT_INSERTION';
  const defaultMaskDilation =
    typeof defaults.mask_dilation === 'number' ? defaults.mask_dilation : 0.06;
  const defaultGuidanceScale =
    typeof defaults.guidance_scale === 'number' ? defaults.guidance_scale : 15.0;
  const defaultImageCount =
    (typeof defaults.number_of_images === 'number' ? defaults.number_of_images : undefined) ??
    imageCountOptions[0] ??
    1;
  const defaultOutputMimeType =
    (typeof defaults.output_mime_type === 'string' ? defaults.output_mime_type : undefined) ??
    (typeof outputMimeOptions[0]?.value === 'string' ? outputMimeOptions[0].value : undefined) ??
    'image/png';
  const defaultCompressionQuality =
    typeof defaults.output_compression_quality === 'number' ? defaults.output_compression_quality : 80;
  const defaultNegativePrompt = typeof defaults.negative_prompt === 'string' ? defaults.negative_prompt : '';

  // 优先使用 controls 对象，fallback 到单独 props
  const editMode = controls?.editMode ?? propEditMode ?? defaultEditMode;
  const setEditMode = controls?.setEditMode ?? propSetEditMode ?? (() => {});
  const maskDilation = controls?.maskDilation ?? propMaskDilation ?? defaultMaskDilation;
  const setMaskDilation = controls?.setMaskDilation ?? propSetMaskDilation ?? (() => {});
  const guidanceScale = controls?.guidanceScale ?? propGuidanceScale ?? defaultGuidanceScale;
  const setGuidanceScale = controls?.setGuidanceScale ?? propSetGuidanceScale ?? (() => {});
  const numberOfImages = controls?.numberOfImages ?? propNumberOfImages ?? defaultImageCount;
  const setNumberOfImages = controls?.setNumberOfImages ?? propSetNumberOfImages ?? (() => {});
  const negativePrompt = controls?.negativePrompt ?? propNegativePrompt ?? defaultNegativePrompt;
  const setNegativePrompt = controls?.setNegativePrompt ?? propSetNegativePrompt ?? (() => {});
  const outputMimeType = controls?.outputMimeType ?? propOutputMimeType ?? defaultOutputMimeType;
  const setOutputMimeType = controls?.setOutputMimeType ?? propSetOutputMimeType ?? (() => {});
  const outputCompressionQuality =
    controls?.outputCompressionQuality ?? propOutputCompressionQuality ?? defaultCompressionQuality;
  const setOutputCompressionQuality = controls?.setOutputCompressionQuality ?? propSetOutputCompressionQuality ?? (() => {});
  const showAdvanced = controls?.showAdvanced ?? propShowAdvanced ?? false;
  const setShowAdvanced = controls?.setShowAdvanced ?? propSetShowAdvanced ?? (() => {});

  const maskMin = maskDilationRange?.min ?? 0;
  const maskMax = maskDilationRange?.max ?? 1;
  const maskStep = maskDilationRange?.step ?? 0.01;
  const guidanceMin = guidanceScaleRange?.min ?? 1;
  const guidanceMax = guidanceScaleRange?.max ?? 20;
  const guidanceStep = guidanceScaleRange?.step ?? 0.5;
  const compressionMin = compressionRange?.min ?? 1;
  const compressionMax = compressionRange?.max ?? 100;
  const compressionStep = compressionRange?.step ?? 1;

  useEffect(() => {
    const validModes = editModeOptions
      .map((option) => option.value)
      .filter((value): value is string => typeof value === 'string');
    if (validModes.length > 0 && !validModes.includes(editMode)) {
      setEditMode(validModes[0]);
    }
  }, [editMode, editModeOptions, setEditMode]);

  useEffect(() => {
    if (imageCountOptions.length > 0 && !imageCountOptions.includes(numberOfImages)) {
      setNumberOfImages(imageCountOptions[0]);
    }
  }, [numberOfImages, imageCountOptions, setNumberOfImages]);

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
      {!loading && (error || editModeOptions.length === 0 || imageCountOptions.length === 0) && (
        <div className="text-[10px] text-rose-400">
          掩码编辑参数配置加载失败，请检查后端 `mode_controls_catalog.json`。
        </div>
      )}
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
          {editModeOptions.map((mode) => (
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
          {imageCountOptions.map((count) => (
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
                  min={maskMin}
                  max={maskMax}
                  step={maskStep}
                  value={maskDilation}
                  onChange={(e) => setMaskDilation(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-pink-500"
                />
                <p className="text-[10px] text-slate-500">控制掩码边缘的扩展范围</p>
              </div>

              {/* 引导比例 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-300">引导比例</span>
                  <span className="text-xs text-pink-400 font-mono">{guidanceScale.toFixed(1)}</span>
                </div>
                <input
                  type="range"
                  min={guidanceMin}
                  max={guidanceMax}
                  step={guidanceStep}
                  value={guidanceScale}
                  onChange={(e) => setGuidanceScale(parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-pink-500"
                />
                <p className="text-[10px] text-slate-500">控制生成结果与提示词的匹配程度</p>
              </div>

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

              {/* JPEG 压缩质量 */}
              {outputMimeType === 'image/jpeg' && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-300">压缩质量</span>
                    <span className="text-xs text-pink-400 font-mono">{outputCompressionQuality}%</span>
                  </div>
                  <input
                    type="range"
                    min={compressionMin}
                    max={compressionMax}
                    step={compressionStep}
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
