import React, { useState, useEffect } from 'react';
import { Ratio, Maximize2 } from 'lucide-react';
import { VideoGenControlsProps } from '../types';
import { VIDEO_ASPECT_RATIOS } from '../constants';

export const VideoGenControls: React.FC<VideoGenControlsProps> = ({
  providerId,
  aspectRatio, setAspectRatio,
  resolution, setResolution,
}) => {
  const [showAspectMenu, setShowAspectMenu] = useState(false);
  const [showResMenu, setShowResMenu] = useState(false);

  const isGoogle = providerId === 'google' || providerId === 'google-custom';
  const showResolution = isGoogle;

  // Video-gen only supports 16:9 and 9:16 aspect ratios
  useEffect(() => {
    if (aspectRatio !== '16:9' && aspectRatio !== '9:16') {
      setAspectRatio('16:9');
    }
  }, [aspectRatio, setAspectRatio]);

  const getResolutionLabel = (res: string) => {
    if (res === '1K') return '720p (HD)';
    if (res === '2K') return '1080p (FHD)';
    return res;
  };

  return (
    <>
      <div className="relative">
        <button onClick={() => setShowAspectMenu(!showAspectMenu)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all">
          <Ratio size={14} className="text-slate-400" />
          {VIDEO_ASPECT_RATIOS.find(r => r.value === aspectRatio)?.label.split(' ')[0] || aspectRatio}
        </button>
        {showAspectMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowAspectMenu(false)} />
            <div className="absolute bottom-full right-0 mb-2 w-48 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out]">
              <div className="p-1">
                {VIDEO_ASPECT_RATIOS.map((ratio) => (
                  <button key={ratio.value} onClick={() => { setAspectRatio(ratio.value); setShowAspectMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs ${aspectRatio === ratio.value ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
                    {ratio.label}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {showResolution && (
        <div className="relative">
          <button onClick={() => setShowResMenu(!showResMenu)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all">
            <Maximize2 size={14} className="text-emerald-400" />
            {getResolutionLabel(resolution)}
          </button>
          {showResMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowResMenu(false)} />
              <div className="absolute bottom-full right-0 mb-2 w-40 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out]">
                <div className="p-1">
                  <button onClick={() => { setResolution("1K"); setShowResMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs ${resolution === "1K" ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>{getResolutionLabel("1K")}</button>
                  <button onClick={() => { setResolution("2K"); setShowResMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs ${resolution === "2K" ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>{getResolutionLabel("2K")}</button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
};

export default VideoGenControls;
