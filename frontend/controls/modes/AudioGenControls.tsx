import React, { useState } from 'react';
import { Mic } from 'lucide-react';
import { AudioGenControlsProps } from '../types';
import { VOICES } from '../constants';

export const AudioGenControls: React.FC<AudioGenControlsProps> = ({
  voice, setVoice,
}) => {
  const [showVoiceMenu, setShowVoiceMenu] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setShowVoiceMenu(!showVoiceMenu)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all"
      >
        <Mic size={14} className="text-purple-400" />
        {voice}
      </button>
      {showVoiceMenu && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setShowVoiceMenu(false)} />
          <div className="absolute bottom-full right-0 mb-2 w-40 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out]">
            <div className="p-1">
              {VOICES.map((v) => (
                <button
                  key={v.value}
                  onClick={() => { setVoice(v.value); setShowVoiceMenu(false); }}
                  className={`w-full text-left px-2 py-1.5 rounded-lg text-xs ${voice === v.value ? 'bg-purple-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}
                >
                  {v.label}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default AudioGenControls;
