/**
 * Google 音频生成模式参数控件（仅 Panel 模式）
 * 
 * 用于右侧参数面板，通过 ModeControlsCoordinator 分发
 */
import React from 'react';
import { Mic } from 'lucide-react';
import { AudioGenControlsProps } from '../../types';
import { VOICES, DEFAULT_CONTROLS } from '../../constants/index';

export const AudioGenControls: React.FC<AudioGenControlsProps> = ({
  controls,
  voice: propVoice, setVoice: propSetVoice,
}) => {
  // 优先使用 controls 对象，fallback 到单独 props
  const voice = controls?.voice ?? propVoice ?? DEFAULT_CONTROLS.voice;
  const setVoice = controls?.setVoice ?? propSetVoice ?? (() => {});

  return (
    <div className="space-y-4">
      {/* 语音选择 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Mic size={12} className="text-purple-400" />
          <span className="text-xs text-slate-300">语音</span>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {VOICES.map((v) => (
            <button
              key={v.value}
              onClick={() => setVoice(v.value)}
              className={`py-1.5 text-[10px] font-medium rounded-lg transition-all ${
                voice === v.value
                  ? 'bg-purple-600 text-white'
                  : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default AudioGenControls;
