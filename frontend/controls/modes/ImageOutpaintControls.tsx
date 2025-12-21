import React, { useState } from 'react';
import { Expand } from 'lucide-react';
import { ImageOutpaintControlsProps } from '../types';
import { AdvancedToggle } from '../shared';

export const ImageOutpaintControls: React.FC<ImageOutpaintControlsProps> = ({
  outPaintingMode, setOutPaintingMode,
  scaleFactor, setScaleFactor,
  offsetPixels, setOffsetPixels,
  showAdvanced, setShowAdvanced,
}) => {
  const [showOutPaintMenu, setShowOutPaintMenu] = useState(false);

  return (
    <>
      <div className="relative">
        <button
          onClick={() => setShowOutPaintMenu(!showOutPaintMenu)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all"
        >
          <Expand size={14} className="text-orange-400" />
          {outPaintingMode === 'scale' ? `Scale ${scaleFactor}x` : 'Custom Offset'}
        </button>
        {showOutPaintMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowOutPaintMenu(false)} />
            <div className="absolute bottom-full right-0 mb-2 w-64 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out] p-3">
              <div className="flex gap-2 mb-3">
                <button
                  onClick={() => setOutPaintingMode('scale')}
                  className={`flex-1 py-1.5 text-xs rounded-md ${outPaintingMode === 'scale' ? 'bg-orange-600 text-white' : 'bg-slate-800 text-slate-400'}`}
                >Scale</button>
                <button
                  onClick={() => setOutPaintingMode('offset')}
                  className={`flex-1 py-1.5 text-xs rounded-md ${outPaintingMode === 'offset' ? 'bg-orange-600 text-white' : 'bg-slate-800 text-slate-400'}`}
                >Offset</button>
              </div>


              {outPaintingMode === 'scale' ? (
                <div className="space-y-2">
                  <div className="text-xs text-slate-400 flex justify-between">
                    <span>Scale Factor</span>
                    <span>{scaleFactor.toFixed(1)}x</span>
                  </div>
                  <input
                    type="range" min="1.0" max="4.0" step="0.1"
                    value={scaleFactor}
                    onChange={(e) => setScaleFactor(parseFloat(e.target.value))}
                    className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {(['top', 'bottom', 'left', 'right'] as const).map((dir) => (
                    <div key={dir} className="flex flex-col gap-1">
                      <label className="text-[10px] text-slate-500 uppercase">{dir}</label>
                      <input
                        type="number" min="0" max="2000" step="64"
                        value={offsetPixels[dir]}
                        onChange={(e) => setOffsetPixels(prev => ({ ...prev, [dir]: parseInt(e.target.value) || 0 }))}
                        className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <AdvancedToggle showAdvanced={showAdvanced} setShowAdvanced={setShowAdvanced} />
    </>
  );
};

export default ImageOutpaintControls;
