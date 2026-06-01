import React from 'react';
import { Clapperboard } from 'lucide-react';
import type { VideoContractExtensionOption } from '../../hooks/useModeControlsSchema';

interface VideoExtensionControlProps {
  extensionOptions?: VideoContractExtensionOption[];
  extensionCount: number;
  onExtensionCountChange: (count: number) => void;
  enabled?: boolean;
  onEnabledChange?: (enabled: boolean) => void;
  addedSeconds?: number | null;
  maxOutputVideoSeconds?: number | null;
  baseDurationSeconds?: number;
  storyboardSegments?: string[];
  onStoryboardSegmentsChange?: (segments: string[]) => void;
  showStoryboard?: boolean;
}

const selectClassName =
  'w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 focus:border-cyan-500 focus:outline-none';

export const VideoExtensionControl: React.FC<VideoExtensionControlProps> = ({
  extensionOptions = [],
  extensionCount,
  onExtensionCountChange,
  enabled: enabledProp,
  onEnabledChange,
  addedSeconds,
  maxOutputVideoSeconds,
  baseDurationSeconds,
  storyboardSegments = [],
  onStoryboardSegmentsChange,
  showStoryboard = false,
}) => {
  const positiveExtensionOptions = extensionOptions.filter((option) => option.count > 0);
  const hasExtensionMatrix = positiveExtensionOptions.length > 0;

  if (!hasExtensionMatrix) {
    return null;
  }
  const enabled = enabledProp ?? extensionCount > 0;
  const selectedExtensionCount =
    extensionCount > 0 ? extensionCount : positiveExtensionOptions[0]?.count ?? 0;
  const handleEnabledChange = () => {
    const nextEnabled = !enabled;
    if (onEnabledChange) {
      onEnabledChange(nextEnabled);
      return;
    }
    onExtensionCountChange(nextEnabled ? positiveExtensionOptions[0]?.count ?? 1 : 0);
  };
  const segmentSeconds =
    typeof addedSeconds === 'number' && addedSeconds > 0
      ? addedSeconds
      : typeof baseDurationSeconds === 'number' && baseDurationSeconds > 0
        ? baseDurationSeconds
        : 0;

  const updateStoryboardSegment = (index: number, value: string) => {
    if (!onStoryboardSegmentsChange) return;
    const next = [...storyboardSegments];
    while (next.length <= index) {
      next.push('');
    }
    next[index] = value;
    onStoryboardSegmentsChange(next);
  };

  return (
    <div className="space-y-2 rounded-xl border border-slate-700/60 bg-slate-900/60 p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Clapperboard size={12} className="text-cyan-400" />
          <span className="text-xs text-slate-300">视频延长</span>
        </div>
        {hasExtensionMatrix && addedSeconds && maxOutputVideoSeconds ? (
          <span className="text-[10px] text-cyan-300">
            每次 +{addedSeconds}s，最长 {maxOutputVideoSeconds}s
          </span>
        ) : (
          <span className="text-[10px] text-cyan-300">按源视频续写</span>
        )}
        <button
          type="button"
          role="switch"
          aria-label="延长视频"
          aria-checked={enabled}
          onClick={handleEnabledChange}
          className={`h-6 w-10 rounded-full p-1 transition-colors ${
            enabled ? 'bg-cyan-600' : 'bg-slate-700'
          }`}
        >
          <span
            className={`block h-4 w-4 rounded-full bg-white shadow transition-transform ${
              enabled ? 'translate-x-4' : 'translate-x-0'
            }`}
          />
        </button>
      </div>

      {enabled && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <label className="space-y-1">
              <span className="text-[11px] text-slate-400">延长次数</span>
              <select
                aria-label="延长次数"
                value={String(selectedExtensionCount)}
                onChange={(event) => onExtensionCountChange(parseInt(event.target.value, 10) || 0)}
                className={selectClassName}
              >
                {positiveExtensionOptions.map((option) => (
                  <option key={option.count} value={option.count}>
                    {option.count} 次
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1">
              <span className="text-[11px] text-slate-400">延长后总时长</span>
              <select
                aria-label="延长后总时长"
                value={String(selectedExtensionCount)}
                onChange={(event) => onExtensionCountChange(parseInt(event.target.value, 10) || 0)}
                className={selectClassName}
              >
                {positiveExtensionOptions.map((option) => (
                  <option key={option.count} value={option.count}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {showStoryboard && selectedExtensionCount > 0 && onStoryboardSegmentsChange && (
            <div className="space-y-2 pt-1">
              {Array.from({ length: selectedExtensionCount }, (_, index) => {
                const start = segmentSeconds > 0 ? index * segmentSeconds : 0;
                const end = segmentSeconds > 0 ? start + segmentSeconds : 0;
                return (
                  <label key={index} className="block space-y-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-[11px] text-slate-400">延长 {index + 1} 分镜</span>
                      {segmentSeconds > 0 && <span className="text-[10px] text-cyan-300">{start}-{end}s</span>}
                    </span>
                    <textarea
                      aria-label={`延长 ${index + 1} 分镜提示词`}
                      value={storyboardSegments[index] ?? ''}
                      onChange={(event) => updateStoryboardSegment(index, event.target.value)}
                      placeholder="可选：只描述这一段延长里的动作、镜头、构图、口播或情绪变化。"
                      className="h-20 w-full resize-none rounded-lg border border-slate-700 bg-slate-800 p-2 text-xs text-slate-300 placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
                    />
                  </label>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default VideoExtensionControl;
