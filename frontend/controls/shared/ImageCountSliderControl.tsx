import React from 'react';
import { Layers } from 'lucide-react';

export interface ImageCountSliderControlProps {
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  label?: string;
}

export const ImageCountSliderControl: React.FC<ImageCountSliderControlProps> = ({
  value,
  onChange,
  min,
  max,
  label = '图片数量',
}) => {
  if (max <= min) {
    return null;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Layers size={12} className="text-blue-400" />
          <span className="text-xs text-slate-300">{label}</span>
        </div>
        <span className="text-xs text-blue-400 font-mono font-bold">{value}</span>
      </div>
      <input
        type="range"
        aria-label={label}
        min={min}
        max={max}
        step={1}
        value={value}
        onChange={(event) => onChange(parseInt(event.target.value, 10))}
        className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-blue-500"
      />
      <div className="flex justify-between text-[10px] text-slate-500 px-0.5">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
};

export default ImageCountSliderControl;
