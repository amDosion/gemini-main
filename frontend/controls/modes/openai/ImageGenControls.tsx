/**
 * OpenAI (DALL-E) 图像生成专用控件（仅 Panel 模式）
 * 
 * OpenAI 特点：
 * - 比例限制：仅支持固定比例
 * - 图片数量：固定为 1
 * - 不显示分辨率档位
 */
import React, { useMemo } from 'react';
import { Ratio } from 'lucide-react';
import { ImageGenControlsProps } from '../../types';
import { OPENAI_ASPECT_RATIOS, DEFAULT_CONTROLS } from '../../constants/index';

export const ImageGenControls: React.FC<ImageGenControlsProps> = (props) => {
  const {
    controls,
    // 单独 props（向后兼容）
    aspectRatio: propAspectRatio, setAspectRatio: propSetAspectRatio,
  } = props;

  // 优先使用 controls 对象，fallback 到单独 props
  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? DEFAULT_CONTROLS.aspectRatio;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? (() => {});

  // OpenAI 可用比例
  const availableRatios = OPENAI_ASPECT_RATIOS;

  return (
    <div className="space-y-4">
      {/* 图片比例 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Ratio size={12} className="text-emerald-400" />
          <span className="text-xs text-slate-300">图片比例</span>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {availableRatios.map((ratio) => (
            <button
              key={ratio.value}
              onClick={() => setAspectRatio(ratio.value)}
              className={`py-1.5 text-[10px] font-medium rounded-lg transition-all ${
                aspectRatio === ratio.value
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {ratio.value}
            </button>
          ))}
        </div>
      </div>

      {/* OpenAI 信息提示 */}
      <div className="text-[10px] text-slate-500 italic">
        OpenAI DALL-E：固定生成 1 张图片
      </div>
    </div>
  );
};

export default ImageGenControls;
