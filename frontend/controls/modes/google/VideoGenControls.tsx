/**
 * Google 视频生成模式参数控件（仅 Panel 模式）
 * 
 * 用于右侧参数面板，通过 ModeControlsCoordinator 分发
 */
import React, { useEffect } from 'react';
import { Film, Maximize2 } from 'lucide-react';
import { VideoGenControlsProps } from '../../types';
import { VIDEO_ASPECT_RATIOS, VIDEO_RESOLUTIONS, DEFAULT_CONTROLS } from '../../constants/index';

export const VideoGenControls: React.FC<VideoGenControlsProps> = ({
  controls,
  aspectRatio: propAspectRatio, setAspectRatio: propSetAspectRatio,
  resolution: propResolution, setResolution: propSetResolution,
}) => {
  // 优先使用 controls 对象，fallback 到单独 props
  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? DEFAULT_CONTROLS.aspectRatio;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? (() => {});
  const resolution = controls?.resolution ?? propResolution ?? DEFAULT_CONTROLS.resolution;
  const setResolution = controls?.setResolution ?? propSetResolution ?? (() => {});

  // Video-gen only supports 16:9 and 9:16 aspect ratios
  useEffect(() => {
    if (aspectRatio !== '16:9' && aspectRatio !== '9:16') {
      setAspectRatio('16:9');
    }
  }, [aspectRatio, setAspectRatio]);

  return (
    <div className="space-y-4">
      {/* 视频比例 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Film size={12} className="text-indigo-400" />
          <span className="text-xs text-slate-300">视频比例</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {VIDEO_ASPECT_RATIOS.map((ratio) => (
            <button
              key={ratio.value}
              onClick={() => setAspectRatio(ratio.value)}
              className={`py-2 text-xs font-medium rounded-lg transition-all ${
                aspectRatio === ratio.value
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {ratio.label}
            </button>
          ))}
        </div>
      </div>

      {/* 分辨率 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Maximize2 size={12} className="text-emerald-400" />
          <span className="text-xs text-slate-300">分辨率</span>
        </div>
        <div className="flex gap-2">
          {VIDEO_RESOLUTIONS.map((res) => (
            <button
              key={res.value}
              onClick={() => setResolution(res.value)}
              className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
                resolution === res.value
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {res.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default VideoGenControls;
