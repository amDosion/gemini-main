/**
 * OpenAI (DALL-E) 图像生成专用控件（仅 Panel 模式）
 * 
 * OpenAI 特点：
 * - 比例限制：仅支持固定比例
 * - 图片数量：固定为 1
 * - 不显示分辨率档位
 */
import React, { useEffect, useMemo } from 'react';
import { Ratio } from 'lucide-react';
import { ImageGenControlsProps } from '../../types';
import { useModeControlsSchema } from '../../../hooks/useModeControlsSchema';

export const ImageGenControls: React.FC<ImageGenControlsProps> = (props) => {
  const {
    providerId = 'openai',
    currentModel,
    controls,
    // 单独 props（向后兼容）
    aspectRatio: propAspectRatio, setAspectRatio: propSetAspectRatio,
  } = props;

  const { schema, loading, error } = useModeControlsSchema(providerId, 'image-gen', currentModel?.id);
  const availableRatios = useMemo(() => {
    return schema?.aspectRatios ?? [];
  }, [schema]);
  const defaults = schema?.defaults ?? {};
  const defaultAspectRatio =
    (typeof defaults.aspect_ratio === 'string' ? defaults.aspect_ratio : undefined) ??
    availableRatios[0]?.value ??
    '1:1';

  // 优先使用 controls 对象，fallback 到单独 props
  const aspectRatio = controls?.aspectRatio ?? propAspectRatio ?? defaultAspectRatio;
  const setAspectRatio = controls?.setAspectRatio ?? propSetAspectRatio ?? (() => {});

  useEffect(() => {
    const validRatios = availableRatios.map((r) => r.value);
    if (validRatios.length > 0 && !validRatios.includes(aspectRatio)) {
      setAspectRatio(validRatios[0]);
    }
  }, [availableRatios, aspectRatio, setAspectRatio]);

  return (
    <div className="space-y-4">
      {!loading && (error || availableRatios.length === 0) && (
        <div className="text-[10px] text-rose-400">
          比例配置加载失败，请检查后端 `mode_controls_catalog.json`。
        </div>
      )}
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
