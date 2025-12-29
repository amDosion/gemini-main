/**
 * 图像生成控件协调器
 * 根据提供商选择对应的控件组件
 * 
 * 显示逻辑：
 * - 通义（TongYi）：风格、图片数量、比例、分辨率档位、实际像素分辨率、高级选项
 * - 谷歌（Google）：风格、图片数量、比例、分辨率档位（1K/2K/4K）、实际像素分辨率、高级选项
 * - OpenAI：比例、高级选项（不显示分辨率，图片数量固定为1）
 */
import React, { useState, useMemo, useEffect } from 'react';
import { Palette, Layers, Ratio, Maximize2 } from 'lucide-react';
import { ImageGenControlsProps } from '../types';
import { AdvancedToggle } from '../shared';
import { 
  OPENAI_ASPECT_RATIOS, 
  STYLES,
  getAvailableAspectRatios,
  getAvailableResolutionTiers,
  getPixelResolution
} from '../constants';
import { TongYiImageGenControls } from './TongYiImageGenControls';

export const ImageGenControls: React.FC<ImageGenControlsProps> = (props) => {
  const {
    providerId,
    currentModel,
    style, setStyle,
    numberOfImages, setNumberOfImages,
    aspectRatio, setAspectRatio,
    resolution, setResolution,
    showAdvanced, setShowAdvanced,
  } = props;

  // 检测提供商类型
  const isTongYi = providerId === 'tongyi';
  const isOpenAI = providerId === 'openai';
  const isGoogle = providerId === 'google' || providerId === 'google-custom';

  // 检测通义文生图模型
  const modelId = currentModel?.id?.toLowerCase() || '';
  const isWanT2I = modelId.includes('-t2i');
  const isZImage = modelId.startsWith('z-image');
  const isWan26Image = modelId === 'wan2.6-image';
  const isTongYiT2IModel = isTongYi && (isWanT2I || isZImage || isWan26Image);

  // 通义文生图模型使用专用控件（不显示比例和分辨率）
  if (isTongYiT2IModel) {
    return (
      <TongYiImageGenControls
        currentModel={currentModel}
        style={style}
        setStyle={setStyle}
        numberOfImages={numberOfImages}
        setNumberOfImages={setNumberOfImages}
        aspectRatio={aspectRatio}
        setAspectRatio={setAspectRatio}
        resolution={resolution}
        setResolution={setResolution}
        showAdvanced={showAdvanced}
        setShowAdvanced={setShowAdvanced}
      />
    );
  }

  // 其他提供商使用通用控件
  return (
    <GenericImageGenControls
      isOpenAI={isOpenAI}
      isGoogle={isGoogle}
      style={style}
      setStyle={setStyle}
      numberOfImages={numberOfImages}
      setNumberOfImages={setNumberOfImages}
      aspectRatio={aspectRatio}
      setAspectRatio={setAspectRatio}
      resolution={resolution}
      setResolution={setResolution}
      showAdvanced={showAdvanced}
      setShowAdvanced={setShowAdvanced}
    />
  );
};

// 通用图像生成控件（OpenAI、Google 等）
interface GenericImageGenControlsProps {
  isOpenAI: boolean;
  isGoogle: boolean;
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

const GenericImageGenControls: React.FC<GenericImageGenControlsProps> = ({
  isOpenAI,
  isGoogle,
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

  // 动态获取可用比例和分辨率档位
  const availableRatios = useMemo(() => {
    if (isOpenAI) return OPENAI_ASPECT_RATIOS;
    if (isGoogle) return getAvailableAspectRatios('google');
    return OPENAI_ASPECT_RATIOS;
  }, [isOpenAI, isGoogle]);

  const availableResolutionTiers = useMemo(() => {
    if (isGoogle) return getAvailableResolutionTiers('google');
    return [];
  }, [isGoogle]);

  // 显示逻辑
  const maxImageCount = isOpenAI ? 1 : 4;
  const canChangeCount = isGoogle && maxImageCount > 1;
  const showStyles = isGoogle;
  const showAspectRatio = isGoogle || isOpenAI;
  const showResolution = isGoogle && availableResolutionTiers.length > 0;

  // OpenAI 只支持 1 张图片
  useEffect(() => {
    if (isOpenAI && numberOfImages !== 1) {
      setNumberOfImages(1);
    } else if (numberOfImages > maxImageCount) {
      setNumberOfImages(maxImageCount);
    }
  }, [isOpenAI, numberOfImages, maxImageCount, setNumberOfImages]);

  // 当提供商变化时，验证当前比例是否有效
  useEffect(() => {
    const validRatios = availableRatios.map(r => r.value);
    if (!validRatios.includes(aspectRatio)) {
      setAspectRatio(validRatios[0] || '1:1');
    }
  }, [availableRatios, aspectRatio, setAspectRatio]);

  // 当提供商变化时，验证当前分辨率档位是否有效
  useEffect(() => {
    if (availableResolutionTiers.length > 0) {
      const validTiers = availableResolutionTiers.map(t => t.value);
      if (!validTiers.includes(resolution)) {
        setResolution(validTiers[0] || '1K');
      }
    }
  }, [availableResolutionTiers, resolution, setResolution]);

  // 计算当前选择组合的实际像素分辨率（仅 Google）
  const currentPixelResolution = useMemo(() => {
    if (!isGoogle) return '';
    const pixelRes = getPixelResolution(aspectRatio, resolution, 'google');
    return pixelRes.replace('*', '×');
  }, [isGoogle, aspectRatio, resolution]);

  return (
    <>
      <AdvancedToggle showAdvanced={showAdvanced} setShowAdvanced={setShowAdvanced} />

      {/* 风格选择：只有谷歌显示 */}
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

      {/* 图片数量：只有谷歌可以改 */}
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

      {/* 比例选择：谷歌和 OpenAI 显示（仅显示比例标签） */}
      {showAspectRatio && (
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
                  {availableRatios.map((ratio) => (
                    <button 
                      key={ratio.value} 
                      onClick={() => { setAspectRatio(ratio.value); setShowAspectMenu(false); }} 
                      className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between ${aspectRatio === ratio.value ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}
                    >
                      {ratio.label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* 分辨率档位选择：只有谷歌显示（显示当前比例+档位的实际像素分辨率） */}
      {showResolution && (
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
                    const tierPixelRes = getPixelResolution(aspectRatio, tier.value, 'google').replace('*', '×');
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

export default ImageGenControls;
