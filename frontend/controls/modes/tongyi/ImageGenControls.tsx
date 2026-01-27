/**
 * 通义图像生成专用控件（仅 Panel 模式）
 * 支持 wan2.x-t2i / z-image-turbo / wan2.6-image 系列模型
 * 
 * 显示逻辑：
 * - 风格选择
 * - 图片数量（z-image-turbo 只支持 1 张）
 * - 比例选择（仅显示比例标签，如 "1:1 Square"）
 * - 分辨率档位选择（根据模型动态显示）
 * - 实际像素分辨率显示（比例 + 档位的联动结果）
 * - 高级选项（Seed、Negative Prompt、Prompt Extend）
 * 
 * 模型支持：
 * - wan2.x-t2i: 8 比例 × 3 档位 (1K/1.25K/1.5K)
 * - z-image-turbo: 11 比例 × 4 档位 (1K/1.25K/1.5K/2K)
 * - wan2.6-image: 10 比例 × 单档位
 */
import React, { useEffect, useMemo } from 'react';
import { Palette, Layers, Ratio, Maximize2, ChevronUp, ChevronDown, Dices, Sparkles, Wand2 } from 'lucide-react';
import { ControlsState } from '../../types';
import { 
  STYLES, 
  getAvailableAspectRatios, 
  getAvailableResolutionTiers,
  getPixelResolution,
  DEFAULT_CONTROLS
} from '../../constants/index';

export interface ImageGenControlsProps {
  currentModel?: { id: string; name?: string };
  /** 传递 controls 状态对象 */
  controls?: ControlsState;
  // 单独 props（向后兼容）
  style?: string;
  setStyle?: (v: string) => void;
  numberOfImages?: number;
  setNumberOfImages?: (v: number) => void;
  aspectRatio?: string;
  setAspectRatio?: (v: string) => void;
  resolution?: string;
  setResolution?: (v: string) => void;
  showAdvanced?: boolean;
  setShowAdvanced?: (v: boolean) => void;
  seed?: number;
  setSeed?: (v: number) => void;
  negativePrompt?: string;
  setNegativePrompt?: (v: string) => void;
  promptExtend?: boolean;
  setPromptExtend?: (v: boolean) => void;
  addMagicSuffix?: boolean;
  setAddMagicSuffix?: (v: boolean) => void;
}

export const ImageGenControls: React.FC<ImageGenControlsProps> = ({
  currentModel,
  controls,
  // 单独 props（向后兼容）
  style: propStyle, setStyle: propSetStyle,
  numberOfImages: propNumberOfImages, setNumberOfImages: propSetNumberOfImages,
  aspectRatio: propAspectRatio, setAspectRatio: propSetAspectRatio,
  resolution: propResolution, setResolution: propSetResolution,
  showAdvanced: propShowAdvanced, setShowAdvanced: propSetShowAdvanced,
  seed: propSeed, setSeed: propSetSeed,
  negativePrompt: propNegativePrompt, setNegativePrompt: propSetNegativePrompt,
  promptExtend: propPromptExtend, setPromptExtend: propSetPromptExtend,
  addMagicSuffix: propAddMagicSuffix, setAddMagicSuffix: propSetAddMagicSuffix,
}) => {
  // 优先使用 controls 对象，fallback 到单独 props
  const style = controls?.style ?? propStyle ?? DEFAULT_CONTROLS.style;
  const setStyle = controls?.setStyle ?? propSetStyle ?? (() => {});
  const numberOfImages = controls?.numberOfImages ?? propNumberOfImages ?? DEFAULT_CONTROLS.numberOfImages;
  const setNumberOfImages = controls?.setNumberOfImages ?? propSetNumberOfImages ?? (() => {});
  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? DEFAULT_CONTROLS.aspectRatio;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? (() => {});
  const resolution = controls?.resolution ?? propResolution ?? DEFAULT_CONTROLS.resolution;
  const setResolution = controls?.setResolution ?? propSetResolution ?? (() => {});
  const showAdvanced = controls?.showAdvanced ?? propShowAdvanced ?? true;
  const setShowAdvanced = controls?.setShowAdvanced ?? propSetShowAdvanced ?? (() => {});
  const seed = controls?.seed ?? propSeed ?? DEFAULT_CONTROLS.seed;
  const setSeed = controls?.setSeed ?? propSetSeed ?? (() => {});
  const negativePrompt = controls?.negativePrompt ?? propNegativePrompt ?? DEFAULT_CONTROLS.negativePrompt;
  const setNegativePrompt = controls?.setNegativePrompt ?? propSetNegativePrompt ?? (() => {});
  const promptExtend = controls?.promptExtend ?? propPromptExtend ?? false;
  const setPromptExtend = controls?.setPromptExtend ?? propSetPromptExtend ?? (() => {});
  const addMagicSuffix = controls?.addMagicSuffix ?? propAddMagicSuffix ?? true;
  const setAddMagicSuffix = controls?.setAddMagicSuffix ?? propSetAddMagicSuffix ?? (() => {});

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
    <div className="space-y-4">
      {/* ==================== 基础参数 ==================== */}
      
      {/* 风格选择 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Palette size={12} className="text-pink-400" />
          <span className="text-xs text-slate-300">风格</span>
        </div>
        <select
          value={style}
          onChange={(e) => setStyle(e.target.value)}
          className="w-full px-3 py-2 text-xs bg-slate-800 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-pink-500"
        >
          {STYLES.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>

      {/* 图片数量（z-image-turbo 只支持 1 张） */}
      {maxImageCount > 1 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Layers size={12} className="text-blue-400" />
            <span className="text-xs text-slate-300">图片数量</span>
          </div>
          <div className="flex gap-2">
            {Array.from({ length: maxImageCount }, (_, i) => i + 1).map((n) => (
              <button
                key={n}
                onClick={() => setNumberOfImages(n)}
                className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                  numberOfImages === n
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                }`}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 图片比例 + 分辨率联动 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Ratio size={12} className="text-indigo-400" />
            <span className="text-xs text-slate-300">图片比例</span>
          </div>
          {currentPixelResolution && (
            <span className="text-[10px] text-indigo-400 font-mono">{currentPixelResolution}</span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {availableAspectRatios.slice(0, 10).map((ratio) => (
            <button
              key={ratio.value}
              onClick={() => setAspectRatio(ratio.value)}
              className={`py-1.5 text-[10px] font-medium rounded-lg transition-all ${
                aspectRatio === ratio.value
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {ratio.value}
            </button>
          ))}
        </div>
      </div>

      {/* 分辨率档位（如果有多档） */}
      {showResolutionTier && availableResolutionTiers.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Maximize2 size={12} className="text-emerald-400" />
            <span className="text-xs text-slate-300">分辨率档位</span>
          </div>
          <div className="flex gap-2">
            {availableResolutionTiers.map((tier) => {
              const tierPixelRes = getPixelResolution(aspectRatio, tier.value, 'tongyi', modelId).replace('*', '×');
              return (
                <button
                  key={tier.value}
                  onClick={() => setResolution(tier.value)}
                  className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all flex flex-col items-center gap-0.5 ${
                    resolution === tier.value
                      ? 'bg-emerald-600 text-white'
                      : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                  }`}
                >
                  <span className="font-bold">{tier.value}</span>
                  <span className="text-[10px] opacity-70">{tierPixelRes}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* ==================== 高级参数折叠区 ==================== */}
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
            {/* Seed */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-300">Seed</span>
                <button
                  onClick={() => setSeed(Math.floor(Math.random() * 2147483647))}
                  className="text-xs text-indigo-400 hover:text-indigo-300"
                  title="随机种子"
                >
                  <Dices size={14} />
                </button>
              </div>
              <input
                type="number"
                value={seed === -1 ? '' : seed}
                onChange={(e) => setSeed(e.target.value ? parseInt(e.target.value) : -1)}
                placeholder="随机 (-1)"
                min="0"
                max="2147483647"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500/50"
              />
            </div>

            {/* 负向提示词 */}
            <div className="space-y-2">
              <span className="text-xs text-slate-300">负向提示词</span>
              <textarea
                value={negativePrompt}
                onChange={(e) => setNegativePrompt(e.target.value)}
                placeholder="不想出现的内容..."
                className="w-full h-16 bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50"
              />
            </div>

            {/* 增强提示词 - Switch 开关 */}
            <div className="flex items-center justify-between py-1">
              <div className="flex items-center gap-2">
                <Sparkles size={12} className="text-pink-400" />
                <span className="text-xs text-slate-300">AI 增强提示词</span>
              </div>
              <div
                onClick={() => setPromptExtend(!promptExtend)}
                className={`w-10 h-6 flex items-center rounded-full p-1 cursor-pointer transition-colors duration-200 ${
                  promptExtend ? 'bg-pink-600' : 'bg-slate-600'
                }`}
              >
                <div
                  className={`w-4 h-4 bg-white rounded-full shadow-md transform transition-transform duration-200 ${
                    promptExtend ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </div>
            </div>

            {/* 魔法词组 - Switch 开关 */}
            <div className="flex items-center justify-between py-1">
              <div className="flex items-center gap-2">
                <Wand2 size={12} className="text-pink-400" />
                <span className="text-xs text-slate-300">魔法词组</span>
              </div>
              <div
                onClick={() => setAddMagicSuffix(!addMagicSuffix)}
                className={`w-10 h-6 flex items-center rounded-full p-1 cursor-pointer transition-colors duration-200 ${
                  addMagicSuffix ? 'bg-pink-600' : 'bg-slate-600'
                }`}
              >
                <div
                  className={`w-4 h-4 bg-white rounded-full shadow-md transform transition-transform duration-200 ${
                    addMagicSuffix ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </div>
            </div>
            <p className="text-[10px] text-slate-500 mt-1">自动添加"超清，4K，电影级构图"等质量增强词</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ImageGenControls;
