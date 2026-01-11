import React, { useState, useMemo } from 'react';
import { Ratio, Maximize2 } from 'lucide-react';
import { ImageEditControlsProps } from '../types';
import { AdvancedToggle } from '../shared';
import { GEN_ASPECT_RATIOS, GOOGLE_EDIT_ASPECT_RATIOS, OPENAI_ASPECT_RATIOS, TONGYI_EDIT_ASPECT_RATIOS, TONGYI_GEN_RESOLUTIONS } from '../constants';

export const ImageEditControls: React.FC<ImageEditControlsProps> = ({
  providerId,
  aspectRatio, setAspectRatio,
  resolution, setResolution,
  showAdvanced, setShowAdvanced,
}) => {
  const [showAspectMenu, setShowAspectMenu] = useState(false);
  const [showResMenu, setShowResMenu] = useState(false);

  const isOpenAI = providerId === 'openai';
  const isTongYi = providerId === 'tongyi';
  const isGoogle = providerId === 'google' || providerId === 'google-custom';

  const availableRatios = useMemo(() => {
    if (isOpenAI) return OPENAI_ASPECT_RATIOS;
    if (isGoogle) return GOOGLE_EDIT_ASPECT_RATIOS;
    if (isTongYi) return TONGYI_EDIT_ASPECT_RATIOS;
    return GEN_ASPECT_RATIOS;
  }, [isOpenAI, isGoogle, isTongYi]);

  // 显示逻辑：
  // - 通义（Qwen/Wan）: 显示比例选择和分辨率（1K/1.25K/1.5K）
  // - Google: 显示比例和分辨率 (1K/2K/4K)
  // - OpenAI: 显示比例，不显示分辨率
  const showAspectRatio = true;                    // 所有提供商都显示比例选择
  const showResolution = isGoogle || isTongYi;     // 谷歌和通义显示分辨率
  const allow4K = isGoogle;                        // 只有谷歌支持 4K

  const getResolutionLabel = (res: string) => {
    if (res === '1K') return '1K Standard';
    if (res === '2K') return '2K High';
    if (res === '4K') return '4K Ultra';
    return res;
  };

  return (
    <>
      <AdvancedToggle
        showAdvanced={showAdvanced}
        setShowAdvanced={setShowAdvanced}
        title={isTongYi ? "Advanced: Seed, Negative, LoRA" : "Advanced: Seed, Negative Prompt"}
      />

      {/* 比例选择：所有提供商都显示 */}
      {showAspectRatio && (
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
                    <button key={ratio.value} onClick={() => { setAspectRatio(ratio.value); setShowAspectMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs ${aspectRatio === ratio.value ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
                      {ratio.label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {showResolution && (
        <div className="relative">
          <button onClick={() => setShowResMenu(!showResMenu)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all">
            <Maximize2 size={14} className="text-emerald-400" />
            {isTongYi 
              ? (TONGYI_GEN_RESOLUTIONS.find(r => r.value === resolution)?.label.split(' ')[0] || resolution)
              : getResolutionLabel(resolution)
            }
          </button>
          {showResMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowResMenu(false)} />
              <div className="absolute bottom-full right-0 mb-2 w-44 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out]">
                <div className="p-1">
                  {isTongYi ? (
                    // 通义分辨率选项：1K/1.25K/1.5K
                    TONGYI_GEN_RESOLUTIONS.map((res) => (
                      <button key={res.value} onClick={() => { setResolution(res.value); setShowResMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs ${resolution === res.value ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
                        {res.label}
                      </button>
                    ))
                  ) : (
                    // 谷歌分辨率选项：1K/2K/4K
                    <>
                      <button onClick={() => { setResolution("1K"); setShowResMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs ${resolution === "1K" ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>{getResolutionLabel("1K")}</button>
                      <button onClick={() => { setResolution("2K"); setShowResMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs ${resolution === "2K" ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>{getResolutionLabel("2K")}</button>
                      {allow4K && (
                        <button onClick={() => { setResolution("4K"); setShowResMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs ${resolution === "4K" ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>{getResolutionLabel("4K")}</button>
                      )}
                    </>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
};

export default ImageEditControls;
