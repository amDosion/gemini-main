import React from 'react';
import { Search, Brain } from 'lucide-react';
import { DeepResearchControlsProps } from '../types';

export const DeepResearchControls: React.FC<DeepResearchControlsProps> = ({
  currentModel
}) => {
  return (
    <div className="flex items-center gap-1 bg-slate-900/60 p-1 rounded-full border border-slate-700/50 backdrop-blur-md overflow-x-auto max-w-full custom-scrollbar shadow-sm">
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-indigo-600 text-indigo-50 border-transparent shadow-sm shrink-0">
        <Search size={13} strokeWidth={2.5} />
        <Brain size={13} strokeWidth={2.5} />
        Deep Research Mode
      </div>
      
      {currentModel && (
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-transparent text-slate-400 border-transparent shrink-0">
          Model: {currentModel.name}
        </div>
      )}
    </div>
  );
};

export default DeepResearchControls;
