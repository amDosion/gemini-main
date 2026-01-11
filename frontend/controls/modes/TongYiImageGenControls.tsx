/**
 * 通义图像生成专用控件
 * 支持 wan2.x-t2i / z-image-turbo / wan2.6-image 系列模型
 * 
 * 显示逻辑：
 * - 风格选择
 * - 图片数量（z-image-turbo 只支持 1 张）
 * - 比例选择（仅显示比例标签，如 "1:1 Square"）
 * - 分辨率档位选择（根据模型动态显示）
 * - 实际像素分辨率显示（比例 + 档位的联动结果）
 * - 高级选项（Seed、Negative Prompt）
 * 
 * 模型支持：
 * - wan2.x-t2i: 8 比例 × 3 档位 (1K/1.25K/1.5K)
 * - z-image-turbo: 11 比例 × 4 档位 (1K/1.25K/1.5K/2K)
 * - wan2.6-image: 10 比例 × 单档位
 */
import React, { useState, useEffect, useMemo } from 'react';
import { Palette, Layers, Ratio, Maximize2 } from 'lucide-react';
import { AdvancedToggle } from '../shared';
import { 
  STYLES, 
  getAvailableAspectRatios, 
  getAvailableResolutionTiers,
  getPixelResolution
} from '../constants';

export interface TongYiImageGenControlsProps {
  currentModel?: { id: string; name?: string };
  style: string;
  setStyle: (v: string) => void;
  numberOfImages: number;
  setNumberOfImages: (v: number) => void;
  aspectRatio: string;
  setAspectRatio: (v: string) => void;
  resolution: string;
  setResolution: (v: string) => void;
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
}

export const TongYiImageGenControls: React.FC<TongYiImageGenControlsProps> = ({
  currentModel,
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

  // 检测模型类型
  const modelId = currentModel?.id || '';
  const isZImageTurbo = modelId.toLowerCase() === 'z-image-turbo';

  // 图片数量限制：z-image-turbo 只支持 1 张，其他支持 4 张
  const maxImageCount = isZImageTurbo ? 1 : 4;

  // 动态获取可用比例和分辨率档位
  const availableAspectRatios = useMemo(() => 
    getAvailableAspectRatios('tongyi', modelId), [modelId]);
  
  const availableResolutionTiers = useMemo(() => 
    getAvailableResolutionTiers('tongyi', modelId), [modelId]);

  // 是否显示分辨率档位选择器（wan2.6-image 不显示）
  const showResolutionTier = availableResolutionTiers.length > 0;

  // z-image-turbo 只支持 1 张图片
  useEffect(() => {
    if (isZImageTurbo && numberOfImages !== 1) {
      setNumberOfImages(1);
    } else if (numberOfImages > maxImageCount) {
      setNumberOfImages(maxImageCount);
    }
  }, [isZImageTurbo, numberOfImages, maxImageCount, setNumberOfImages]);

  // 当模型变化时，验证当前比例是否有效
  useEffect(() => {
    const validRatios = availableAspectRatios.map(r => r.value);
    if (!validRatios.includes(aspectRatio)) {
      setAspectRatio(validRatios[0] || '1:1');
    }
  }, [modelId, availableAspectRatios, aspectRatio, setAspectRatio]);

  // 当模型变化时，验证当前分辨率档位是否有效
  useEffect(() => {
    if (availableResolutionTiers.length > 0) {
      const validTiers = availableResolutionTiers.map(t => t.value);
      if (!validTiers.includes(resolution)) {
        setResolution(validTiers[0] || '1K');
      }
    }
  }, [modelId, availableResolutionTiers, resolution, setResolution]);

  // 计算当前选择组合的实际像素分辨率
  const currentPixelResolution = useMemo(() => {
    const pixelRes = getPixelResolution(aspectRatio, resolution, 'tongyi', modelId);
    return pixelRes.replace('*', '×');
  }, [aspectRatio, resolution, modelId]);

  return (
    <>
      <AdvancedToggle 
        showAdvanced={showAdvanced} 
        setShowAdvanced={setShowAdvanced}
        title="Advanced: Seed, Negative Prompt"
      />

      {/* 风格选择 */}
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

      {/* 图片数量（z-image-turbo 只支持 1 张） */}
      {maxImageCount > 1 && (
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
                  {Array.from({ length: maxImageCount }, (_, i) => i + 1).map((n) => (
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

      {/* 比例选择（仅显示比例标签） */}
      <div className="relative">
        <button onClick={() => setShowAspectMenu(!showAspectMenu)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all">
          <Ratio size={14} className="text-slate-400" />
          {aspectRatio}
        </button>
        {showAspectMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowAspectMenu(false)} />
            <div className="absolute bottom-full right-0 mb-2 w-48 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out] max-h-64 overflow-y-auto custom-scrollbar">
              <div className="p-1">
                {availableAspectRatios.map((ratio) => (
                  <button 
                    key={ratio.value} 
                    onClick={() => { setAspectRatio(ratio.value); setShowAspectMenu(false); }} 
                    className={`w-full text-left px-2 py-1.5 rounded-lg text-xs ${aspectRatio === ratio.value ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}
                  >
                    {ratio.label}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* 分辨率档位选择（显示当前比例+档位的实际像素分辨率） */}
      {showResolutionTier && (
        <div className="relative">
          <button onClick={() => setShowResMenu(!showResMenu)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all">
            <Maximize2 size={14} className="text-emerald-400" />
            {currentPixelResolution}
          </button>
          {showResMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowResMenu(false)} />
              <div className="absolute bottom-full right-0 mb-2 w-44 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out]">
                <div className="p-1">
                  {availableResolutionTiers.map((tier) => {
                    const tierPixelRes = getPixelResolution(aspectRatio, tier.value, 'tongyi', modelId).replace('*', '×');
                    return (
                      <button 
                        key={tier.value} 
                        onClick={() => { setResolution(tier.value); setShowResMenu(false); }} 
                        className={`w-full text-left px-2 py-1.5 rounded-lg text-xs ${resolution === tier.value ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}
                      >
                        {tierPixelRes}
                      </button>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
};

export default TongYiImageGenControls;
