import React, { useState } from 'react';
import { Shirt } from 'lucide-react';
import { VirtualTryOnControlsProps } from '../types';

const CLOTHING_TYPES = [
  { label: 'Upper Body', value: 'upper' },
  { label: 'Lower Body', value: 'lower' },
  { label: 'Full Body', value: 'full' },
];

export const VirtualTryOnControls: React.FC<VirtualTryOnControlsProps> = ({
  tryOnTarget,
  setTryOnTarget,
}) => {
  const [showTargetMenu, setShowTargetMenu] = useState(false);

  return (
    <>
      {/* 服装类型选择 */}
      <div className="relative">
        <button
          onClick={() => setShowTargetMenu(!showTargetMenu)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all"
        >
          <Shirt size={14} className="text-rose-400" />
          {CLOTHING_TYPES.find(t => t.value === tryOnTarget)?.label || 'Select Target'}
        </button>
        {showTargetMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowTargetMenu(false)} />
            <div className="absolute bottom-full right-0 mb-2 w-40 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out]">
              <div className="p-1">
                {CLOTHING_TYPES.map((type) => (
                  <button
                    key={type.value}
                    onClick={() => { setTryOnTarget(type.value); setShowTargetMenu(false); }}
                    className={`w-full text-left px-2 py-1.5 rounded-lg text-xs ${
                      tryOnTarget === type.value 
                        ? 'bg-rose-600 text-white' 
                        : 'text-slate-300 hover:bg-slate-800'
                    }`}
                  >
                    {type.label}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
};

export default VirtualTryOnControls;
