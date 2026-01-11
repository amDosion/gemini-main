import React from 'react';
import { SliderControlProps } from '../types';

export const SliderControl: React.FC<SliderControlProps> = ({
  value,
  onChange,
  min,
  max,
  step,
  label,
  formatValue = (v) => v.toString(),
}) => {
  return (
    <div className="space-y-2">
      <div className="text-xs text-slate-400 flex justify-between">
        <span>{label}</span>
        <span>{formatValue(value)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer"
      />
    </div>
  );
};

export default SliderControl;
