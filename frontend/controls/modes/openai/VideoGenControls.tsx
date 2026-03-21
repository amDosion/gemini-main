/**
 * OpenAI (Sora) 视频生成专用控件（仅 Panel 模式）
 *
 * OpenAI 特点：
 * - 需要基于 model schema 选择合法的分辨率
 * - 时长必须显式传递为 seconds
 */
import React, { useEffect, useMemo } from 'react';
import { Clock3, Film, Maximize2 } from 'lucide-react';
import { VideoGenControlsProps } from '../../types';
import { useModeControlsSchema } from '../../../hooks/useModeControlsSchema';

type VideoGenControlsBodyProps = VideoGenControlsProps & {
  schemaLoading: boolean;
  schemaError: string | null;
};

const VideoGenControlsBody: React.FC<VideoGenControlsBodyProps> = ({
  controls,
  controlsSchema,
  schemaLoading,
  schemaError,
  aspectRatio: propAspectRatio, setAspectRatio: propSetAspectRatio,
  resolution: propResolution, setResolution: propSetResolution,
  videoSeconds: propVideoSeconds, setVideoSeconds: propSetVideoSeconds,
}) => {
  const schema = controlsSchema;
  const availableRatios = useMemo(() => schema?.aspectRatios ?? [], [schema]);
  const availableResolutionTiers = useMemo(() => schema?.resolutionTiers ?? [], [schema]);
  const availableSeconds = useMemo(() => schema?.paramOptions?.seconds ?? [], [schema]);
  const defaults = schema?.defaults ?? {};

  const defaultAspectRatio =
    (typeof defaults.aspect_ratio === 'string' ? defaults.aspect_ratio : undefined) ??
    availableRatios[0]?.value ??
    '16:9';
  const defaultResolution =
    (typeof defaults.resolution === 'string' ? defaults.resolution : undefined) ??
    availableResolutionTiers[0]?.value ??
    '1K';
  const defaultVideoSeconds =
    (typeof defaults.seconds === 'string' ? defaults.seconds : undefined) ??
    (typeof defaults.seconds === 'number' ? String(defaults.seconds) : undefined) ??
    (availableSeconds[0]?.value !== undefined ? String(availableSeconds[0].value) : undefined) ??
    '4';

  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? defaultAspectRatio;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? (() => {});
  const resolution = controls?.resolution ?? propResolution ?? defaultResolution;
  const setResolution = controls?.setResolution ?? propSetResolution ?? (() => {});
  const videoSeconds = controls?.videoSeconds ?? propVideoSeconds ?? defaultVideoSeconds;
  const setVideoSeconds = controls?.setVideoSeconds ?? propSetVideoSeconds ?? (() => {});

  useEffect(() => {
    const validRatios = availableRatios.map((option) => option.value);
    if (validRatios.length > 0 && !validRatios.includes(aspectRatio)) {
      setAspectRatio(validRatios[0]);
    }
  }, [aspectRatio, availableRatios, setAspectRatio]);

  useEffect(() => {
    const validTiers = availableResolutionTiers.map((option) => option.value);
    if (validTiers.length > 0 && !validTiers.includes(resolution)) {
      setResolution(validTiers[0]);
    }
  }, [availableResolutionTiers, resolution, setResolution]);

  useEffect(() => {
    const validSeconds = availableSeconds.map((option) => String(option.value));
    if (validSeconds.length > 0 && !validSeconds.includes(videoSeconds)) {
      setVideoSeconds(validSeconds[0]);
    }
  }, [availableSeconds, setVideoSeconds, videoSeconds]);

  return (
    <div className="space-y-4">
      {!schemaLoading && (schemaError || availableRatios.length === 0 || availableResolutionTiers.length === 0) && (
        <div className="text-[10px] text-rose-400">
          OpenAI 视频参数配置加载失败，请检查后端 `mode_controls_catalog.json`。
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Film size={12} className="text-sky-400" />
          <span className="text-xs text-slate-300">视频比例</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {availableRatios.map((ratio) => (
            <button
              key={ratio.value}
              onClick={() => setAspectRatio(ratio.value)}
              className={`py-2 text-xs font-medium rounded-lg transition-all ${
                aspectRatio === ratio.value
                  ? 'bg-sky-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {ratio.label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Maximize2 size={12} className="text-emerald-400" />
          <span className="text-xs text-slate-300">分辨率</span>
        </div>
        <div className="flex gap-2">
          {availableResolutionTiers.map((tier) => (
            <button
              key={tier.value}
              onClick={() => setResolution(tier.value)}
              className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
                resolution === tier.value
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {tier.label}
            </button>
          ))}
        </div>
      </div>

      {availableSeconds.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Clock3 size={12} className="text-amber-400" />
            <span className="text-xs text-slate-300">时长</span>
          </div>
          <div className="flex gap-2">
            {availableSeconds.map((option) => {
              const value = String(option.value);
              return (
                <button
                  key={value}
                  onClick={() => setVideoSeconds(value)}
                  className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
                    videoSeconds === value
                      ? 'bg-amber-600 text-white'
                      : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                  }`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="text-[10px] text-slate-500 italic">
        OpenAI Sora：不同模型支持的尺寸由后端 schema 决定
      </div>
    </div>
  );
};

const VideoGenControlsFromApi: React.FC<VideoGenControlsProps> = (props) => {
  const { providerId = 'openai', currentModel } = props;
  const { schema, loading, error } = useModeControlsSchema(providerId, 'video-gen', currentModel?.id);

  return (
    <VideoGenControlsBody
      {...props}
      controlsSchema={schema}
      schemaLoading={loading}
      schemaError={error}
    />
  );
};

export const VideoGenControls: React.FC<VideoGenControlsProps> = (props) => {
  if ('controlsSchema' in props || 'controlsSchemaLoading' in props || 'controlsSchemaError' in props) {
    return (
      <VideoGenControlsBody
        {...props}
        schemaLoading={Boolean(props.controlsSchemaLoading)}
        schemaError={props.controlsSchemaError ?? null}
      />
    );
  }

  return <VideoGenControlsFromApi {...props} />;
};

export default VideoGenControls;
