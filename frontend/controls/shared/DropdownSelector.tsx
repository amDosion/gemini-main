import React, { useState, ReactNode } from 'react';
import { DropdownSelectorProps } from '../types';

const activeColorMap: Record<string, string> = {
  pink: 'bg-pink-600',
  blue: 'bg-blue-600',
  indigo: 'bg-indigo-600',
  emerald: 'bg-emerald-600',
  orange: 'bg-orange-600',
};

export function DropdownSelector<T extends string | number>({
  value,
  onChange,
  options,
  icon,
  iconColor = 'text-slate-400',
  placeholder = 'Select',
  className = '',
  activeColor = 'indigo',
}: DropdownSelectorProps<T> & { activeColor?: string }) {
  const [isOpen, setIsOpen] = useState(false);
  const selectedOption = options.find(opt => opt.value === value);
  const activeBg = activeColorMap[activeColor] || activeColorMap.indigo;

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all"
      >
        {icon && <span className={iconColor}>{icon}</span>}
        {selectedOption?.label.split(' ')[0] || placeholder}
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div className="absolute bottom-full right-0 mb-2 w-48 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out] max-h-64 overflow-y-auto custom-scrollbar">
            <div className="p-1">
              {options.map((opt) => (
                <button
                  key={String(opt.value)}
                  onClick={() => { onChange(opt.value); setIsOpen(false); }}
                  className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between ${
                    value === opt.value ? `${activeBg} text-white` : 'text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default DropdownSelector;
