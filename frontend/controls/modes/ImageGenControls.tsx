import React, { useState, useMemo, useEffect } from 'react';
import { Palette, Layers, Ratio, Maximize2 } from 'lucide-react';
import { ImageGenControlsProps } from '../types';
import { AdvancedToggle } from '../shared';
import { GEN_ASPECT_RATIOS, OPENAI_ASPECT_RATIOS, STYLES } from '../constants';

export const ImageGenControls: React.FC<ImageGenControlsProps> = ({
  providerId,
  style, setStyle,
  numberOfImages, setNumberOfImages,
  aspectRatio, setAspectRatio,
  resolution, setResolution,
  showAdvanced, setShowAdvanced,
}) => {
  const [showStyleMenu, setShowStyleMenu] = useState(false);
  const [showCountMenu, setShowCountMenu] = useState(false);
  const [showAspectMenu, setShowAspectMenu] = useState(false);
  const [showResMenu, setShowResMenu] = useState(false);

  const isOpenAI = providerId === 'openai';
  const isTongYi = providerId === 'tongyi';
  const isGoogle = providerId === 'google' || providerId === 'google-custom';

  const availableRatios = useMemo(() => {
    if (isOpenAI) return OPENAI_ASPECT_RATIOS;
    return GEN_ASPECT_RATIOS;
  }, [isOpenAI]);

  const canChangeCount = !isOpenAI;
  const showStyles = isTongYi || isGoogle;
  const showResolution = !isOpenAI;

  // OpenAI only supports 1 image at a time
  useEffect(() => {
    if (isOpenAI && numberOfImages !== 1) {
      setNumberOfImages(1);
    }
  }, [isOpenAI, numberOfImages, setNumberOfImages]);

  const getResolutionLabel = (res: string) => {
    if (res === '1K') return '1K Standard';
    if (res === '2K') return '2K High';
    if (res === '4K') return '4K Ultra';
    return res;
  };


  return (
    <>
      <AdvancedToggle showAdvanced={showAdvanced} setShowAdvanced={setShowAdvanced} />

      {showStyles && (
        <div className="relative">
          <button onClick={() => setShowStyleMenu(!showStyleMenu)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all">
            <Palette size={14} className="text-pink-400" />
            {style === "None" ? "Style" : style}
          </button>
          {showStyleMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowStyleMenu(false)} />
              <div className="absolute bottom-full right-0 mb-2 w-48 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out]">
                <div className="p-1 max-h-48 overflow-y-auto custom-scrollbar">
                  {STYLES.map((s) => (
                    <button key={s.value} onClick={() => { setStyle(s.value); setShowStyleMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between ${style === s.value ? 'bg-pink-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {canChangeCount && (
        <div className="relative">
          <button onClick={() => setShowCountMenu(!showCountMenu)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all">
            <Layers size={14} className="text-blue-400" />
            {numberOfImages} Img
          </button>
          {showCountMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowCountMenu(false)} />
              <div className="absolute bottom-full right-0 mb-2 w-32 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out]">
                <div className="p-1">
                  {[1, 2, 3, 4].map((n) => (
                    <button key={n} onClick={() => { setNumberOfImages(n); setShowCountMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between ${numberOfImages === n ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
                      {n} Image{n > 1 ? 's' : ''}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}


      <div className="relative">
        <button onClick={() => setShowAspectMenu(!showAspectMenu)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all">
          <Ratio size={14} className="text-slate-400" />
          {availableRatios.find(r => r.value === aspectRatio)?.label.split(' ')[0] || aspectRatio}
        </button>
        {showAspectMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowAspectMenu(false)} />
            <div className="absolute bottom-full right-0 mb-2 w-48 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out] max-h-64 overflow-y-auto custom-scrollbar">
              <div className="p-1">
                {availableRatios.map((ratio) => (
                  <button key={ratio.value} onClick={() => { setAspectRatio(ratio.value); setShowAspectMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between ${aspectRatio === ratio.value ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
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

export default ImageGenControls;
