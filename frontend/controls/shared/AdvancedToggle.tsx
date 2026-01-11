import React from 'react';
import { Sliders } from 'lucide-react';
import { AdvancedToggleProps } from '../types';

export const AdvancedToggle: React.FC<AdvancedToggleProps> = ({
  showAdvanced,
  setShowAdvanced,
  title = 'Advanced: Seed, Negative Prompt',
}) => {
  return (
    <button
      onClick={() => setShowAdvanced(!showAdvanced)}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-transparent transition-all ${
        showAdvanced
          ? 'bg-slate-800 text-white'
          : 'bg-slate-800/50 text-slate-400 hover:text-slate-200'
      }`}
      title={title}
    >
      <Sliders size={14} />
    </button>
  );
};

export default AdvancedToggle;
