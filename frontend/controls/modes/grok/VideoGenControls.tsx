/**
 * Grok 视频生成专用控件（仅 Panel 模式）
 *
 * Grok 特点：
 * - 时长：6-30 秒（滑块）
 * - 质量：标清 480p / 高清 720p（按钮组）
 * - 尺寸/比例：5 种固定尺寸
 */
import React, { useEffect, useMemo } from 'react';
import { Clock3, Film, Maximize2 } from 'lucide-react';
import { VideoGenControlsProps } from '../../types';
import { useModeControlsSchema } from '../../../hooks/useModeControlsSchema';

const GROK_SIZE_OPTIONS = [
  { label: '1:1 (1024\u00d71024)', value: '1024x1024' },
  { label: '16:9 (1280\u00d7720)', value: '1280x720' },
  { label: '9:16 (720\u00d71280)', value: '720x1280' },
  { label: '3:2 (1792\u00d71024)', value: '1792x1024' },
  { label: '2:3 (1024\u00d71792)', value: '1024x1792' },
];

const GROK_QUALITY_OPTIONS = [
  { label: '标清 480p', value: '480p' },
  { label: '高清 720p', value: '720p' },
];

const DEFAULT_SIZE = '1280x720';
const DEFAULT_QUALITY = '720p';
const DEFAULT_DURATION = '10';
const MIN_DURATION = 6;
const MAX_DURATION = 30;

export const VideoGenControls: React.FC<VideoGenControlsProps> = (props) => {
  const {
    providerId = 'grok',
    currentModel,
    controls,
    // 单独 props（向后兼容）
    aspectRatio: propAspectRatio,
    setAspectRatio: propSetAspectRatio,
    resolution: propResolution,
    setResolution: propSetResolution,
    videoSeconds: propVideoSeconds,
    setVideoSeconds: propSetVideoSeconds,
  } = props;

  const { schema, loading, error } = useModeControlsSchema(providerId, 'video-gen', currentModel?.id);

  const availableSizes = useMemo(() => {
    const schemaRatios = schema?.aspectRatios;
    if (schemaRatios && schemaRatios.length > 0) return schemaRatios;
    return GROK_SIZE_OPTIONS;
  }, [schema]);

  const availableQualities = useMemo(() => {
    const schemaTiers = schema?.resolutionTiers;
    if (schemaTiers && schemaTiers.length > 0) {
      return schemaTiers.map((t) => ({ label: t.label, value: t.value }));
    }
    return GROK_QUALITY_OPTIONS;
  }, [schema]);

  const defaults = schema?.defaults ?? {};
  const durationRange = schema?.numericRanges?.seconds;
  const minDuration = durationRange?.min ?? MIN_DURATION;
  const maxDuration = durationRange?.max ?? MAX_DURATION;

  const defaultSize =
    (typeof defaults.aspect_ratio === 'string' ? defaults.aspect_ratio : undefined) ??
    (typeof defaults.size === 'string' ? defaults.size : undefined) ??
    availableSizes.find((s) => s.value === DEFAULT_SIZE)?.value ??
    availableSizes[0]?.value ??
    DEFAULT_SIZE;

  const defaultQuality =
    (typeof defaults.resolution === 'string' ? defaults.resolution : undefined) ??
    availableQualities[0]?.value ??
    DEFAULT_QUALITY;

  const defaultDuration =
    (typeof defaults.seconds === 'string' ? defaults.seconds : undefined) ??
    (typeof defaults.seconds === 'number' ? String(defaults.seconds) : undefined) ??
    DEFAULT_DURATION;

  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? defaultSize;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? (() => {});
  const resolution = controls?.resolution ?? propResolution ?? defaultQuality;
  const setResolution = controls?.setResolution ?? propSetResolution ?? (() => {});
  const videoSeconds = controls?.videoSeconds ?? propVideoSeconds ?? defaultDuration;
  const setVideoSeconds = controls?.setVideoSeconds ?? propSetVideoSeconds ?? (() => {});

  // 校验当前尺寸
  useEffect(() => {
    const validSizes = availableSizes.map((s) => s.value);
    if (validSizes.length > 0 && !validSizes.includes(aspectRatio)) {
      setAspectRatio(validSizes[0]);
    }
  }, [availableSizes, aspectRatio, setAspectRatio]);

  // 校验当前质量
  useEffect(() => {
    const validQualities = availableQualities.map((q) => q.value);
    if (validQualities.length > 0 && !validQualities.includes(resolution)) {
      setResolution(validQualities[0]);
    }
  }, [availableQualities, resolution, setResolution]);

  // 校验时长范围
  useEffect(() => {
    const sec = parseInt(videoSeconds);
    if (!isNaN(sec)) {
      if (sec < minDuration) setVideoSeconds(String(minDuration));
      else if (sec > maxDuration) setVideoSeconds(String(maxDuration));
    }
  }, [videoSeconds, minDuration, maxDuration, setVideoSeconds]);

  const currentDuration = parseInt(videoSeconds) || minDuration;

  return (
    <div className="space-y-4">
      {!loading && (error || availableSizes.length === 0) && (
        <div className="text-[10px] text-rose-400">
          Grok 视频参数配置加载失败，请检查后端 mode_controls_catalog.json。
        </div>
      )}

      {/* 视频尺寸 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Film size={12} className="text-orange-400" />
          <span className="text-xs text-slate-300">视频尺寸</span>
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

      {/* 画质 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Maximize2 size={12} className="text-emerald-400" />
          <span className="text-xs text-slate-300">画质</span>
        </div>
        <div className="flex gap-2">
          {availableQualities.map((quality) => (
            <button
              key={quality.value}
              onClick={() => setResolution(quality.value)}
              className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
                resolution === quality.value
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {quality.label}
            </button>
          ))}
        </div>
      </div>

      {/* 时长 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock3 size={12} className="text-amber-400" />
            <span className="text-xs text-slate-300">时长</span>
          </div>
          <span className="text-xs text-amber-400 font-mono font-bold">{currentDuration}s</span>
        </div>
        <input
          type="range"
          min={minDuration}
          max={maxDuration}
          step={1}
          value={currentDuration}
          onChange={(e) => setVideoSeconds(e.target.value)}
          className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-amber-500"
        />
        <div className="flex justify-between text-[10px] text-slate-500 px-0.5">
          <span>{minDuration}s</span>
          <span>{maxDuration}s</span>
        </div>
      </div>

      {/* Grok 信息提示 */}
      <div className="text-[10px] text-slate-500 italic">
        Grok：视频时长 {minDuration}-{maxDuration} 秒
      </div>
    </div>
  );
};

export default VideoGenControls;
