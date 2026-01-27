import React from 'react';
import { ToggleButtonProps } from '../types';

const colorMap: Record<string, { bg: string; text: string }> = {
  blue: { bg: 'bg-blue-600', text: 'text-blue-50' },
  purple: { bg: 'bg-purple-600', text: 'text-purple-50' },
  emerald: { bg: 'bg-emerald-600', text: 'text-emerald-50' },
  amber: { bg: 'bg-amber-600', text: 'text-amber-50' },
  orange: { bg: 'bg-orange-600', text: 'text-orange-50' },
  teal: { bg: 'bg-teal-600', text: 'text-teal-50' },
  pink: { bg: 'bg-pink-600', text: 'text-pink-50' },
};

export const ToggleButton: React.FC<ToggleButtonProps> = ({
  enabled,
  onToggle,
  disabled = false,
  icon,
  label,
  activeColor = 'blue',
  title,
}) => {
  const colors = colorMap[activeColor] || colorMap.blue;

  const getClassName = () => {
    const base = 'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border shrink-0';
    
    if (disabled) {
      return `${base} bg-transparent text-slate-600 cursor-not-allowed opacity-40 border-transparent`;
    }
    if (enabled) {
      return `${base} ${colors.bg} ${colors.text} border-transparent shadow-sm`;
    }
    return `${base} bg-transparent text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200`;
  };

  return (
    <button
      onClick={() => !disabled && onToggle()}
      disabled={disabled}
      title={title || label}
      className={getClassName()}
    >
      {icon}
      {label}
    </button>
  );
};

export default ToggleButton;
