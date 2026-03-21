/**
 * Google 音频生成模式参数控件（仅 Panel 模式）
 *
 * 用于右侧参数面板，通过 ModeControlsCoordinator 分发
 */
import React, { useEffect, useMemo } from 'react';
import { Mic } from 'lucide-react';
import { AudioGenControlsProps } from '../../types';
import { useModeControlsSchema } from '../../../hooks/useModeControlsSchema';

export const AudioGenControls: React.FC<AudioGenControlsProps> = ({
  providerId = 'google',
  controls,
  voice: propVoice, setVoice: propSetVoice,
}) => {
  const { schema, loading, error } = useModeControlsSchema(providerId, 'audio-gen');
  const voiceOptions = useMemo(() => schema?.paramOptions?.voice ?? [], [schema]);
  const defaults = schema?.defaults ?? {};
  const defaultVoice =
    (typeof defaults.voice === 'string' ? defaults.voice : undefined) ??
    (typeof voiceOptions[0]?.value === 'string' ? voiceOptions[0].value : undefined) ??
    'Puck';

  const voice = controls?.voice ?? propVoice ?? defaultVoice;
  const setVoice = controls?.setVoice ?? propSetVoice ?? (() => {});

  useEffect(() => {
    const validVoices = voiceOptions
      .map((option) => option.value)
      .filter((value): value is string => typeof value === 'string');
    if (validVoices.length > 0 && !validVoices.includes(voice)) {
      setVoice(validVoices[0]);
    }
  }, [voice, voiceOptions, setVoice]);

  return (
    <div className="space-y-4">
      {!loading && (error || voiceOptions.length === 0) && (
        <div className="text-[10px] text-rose-400">
          音频参数配置加载失败，请检查后端 `mode_controls_catalog.json`。
        </div>
      )}
      {/* 语音选择 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Mic size={12} className="text-purple-400" />
          <span className="text-xs text-slate-300">语音</span>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {voiceOptions.map((v) => (
            <button
              key={String(v.value)}
              onClick={() => typeof v.value === 'string' && setVoice(v.value)}
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
