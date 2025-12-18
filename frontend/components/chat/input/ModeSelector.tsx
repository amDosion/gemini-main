
import React from 'react';
import { MessageSquare, Wand2, Crop, Expand, PlaySquare, Mic, FileText } from 'lucide-react';
import { AppMode, ModelConfig } from '../../../../types';

interface ModeSelectorProps {
  mode: AppMode;
  setMode: (mode: AppMode) => void;
  currentModel?: ModelConfig;
}

export const ModeSelector: React.FC<ModeSelectorProps> = ({ mode, setMode, currentModel }) => {
  const canGenImage = currentModel?.capabilities.vision || false;

  const modes = [
    { id: 'chat', label: 'Chat', icon: MessageSquare, disabled: false, color: 'bg-indigo-600' },
    { id: 'image-gen', label: 'Gen', icon: Wand2, disabled: !canGenImage, color: 'bg-emerald-600' },
    { id: 'image-edit', label: 'Edit', icon: Crop, disabled: !canGenImage, color: 'bg-pink-600' },
    { id: 'image-outpainting', label: 'Expand', icon: Expand, disabled: false, color: 'bg-orange-600' },
    { id: 'video-gen', label: 'Video', icon: PlaySquare, disabled: !canGenImage, color: 'bg-indigo-500' },
    { id: 'audio-gen', label: 'Audio', icon: Mic, disabled: false, color: 'bg-cyan-600' },
    { id: 'pdf-extract', label: 'PDF', icon: FileText, disabled: false, color: 'bg-purple-600' },
  ];

  return (
    <div className="flex items-center gap-1 bg-slate-900/60 p-1 rounded-full border border-slate-700/50 backdrop-blur-md overflow-x-auto max-w-full custom-scrollbar shadow-sm">
      {modes.map((m) => (
        <button
          key={m.id}
          onClick={() => setMode(m.id as AppMode)}
          disabled={m.disabled}
          className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-all flex items-center gap-1.5 whitespace-nowrap ${m.disabled
            ? 'opacity-40 cursor-not-allowed text-slate-500'
            : mode === m.id
              ? `${m.color} text-white shadow-md ring-1 ring-white/10`
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
        >
          <m.icon size={13} strokeWidth={2.5} /> {m.label}
        </button>
      ))}
    </div>
  );
};
