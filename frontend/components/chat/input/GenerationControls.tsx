
import React, { useState, useMemo } from 'react';
import { Sliders, Palette, Layers, Ratio, Maximize2, Expand, Shirt, Link } from 'lucide-react';
import { AppMode } from '../../../../types';

interface GenerationControlsProps {
  mode: AppMode;
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
  style: string;
  setStyle: (v: string) => void;
  numberOfImages: number;
  setNumberOfImages: (v: number) => void;
  aspectRatio: string;
  setAspectRatio: (v: string) => void;
  resolution: string;
  setResolution: (v: string) => void;
  // Outpainting
  outPaintingMode: 'scale' | 'offset';
  setOutPaintingMode: (v: 'scale' | 'offset') => void;
  scaleFactor: number;
  setScaleFactor: (v: number) => void;
  offsetPixels: { left: number; right: number; top: number; bottom: number };
  setOffsetPixels: (v: React.SetStateAction<{ left: number; right: number; top: number; bottom: number }>) => void;
  // Try-On
  showTryOn?: boolean;
  setShowTryOn?: (v: boolean) => void;
  tryOnTarget?: string;
  setTryOnTarget?: (v: string) => void;
  // Context
  providerId: string;
}

// --- CONSTANTS ---

const GEN_ASPECT_RATIOS = [
    { label: "1:1 Square", value: "1:1" },
    { label: "3:4 Portrait", value: "3:4" },
    { label: "4:3 Landscape", value: "4:3" },
    { label: "9:16 Portrait", value: "9:16" },
    { label: "16:9 Landscape", value: "16:9" },
];

// Google Gemini Edit supports a wider range
const GOOGLE_EDIT_ASPECT_RATIOS = [
    { label: "1:1 Square", value: "1:1" },
    { label: "2:3 Portrait", value: "2:3" },
    { label: "3:2 Landscape", value: "3:2" },
    { label: "3:4 Portrait", value: "3:4" },
    { label: "4:3 Landscape", value: "4:3" },
    { label: "4:5 Portrait", value: "4:5" },
    { label: "5:4 Landscape", value: "5:4" },
    { label: "9:16 Portrait", value: "9:16" },
    { label: "16:9 Landscape", value: "16:9" },
    { label: "21:9 Ultrawide", value: "21:9" },
];

const OPENAI_ASPECT_RATIOS = [
    { label: "1:1 Square", value: "1:1" },
    { label: "Portrait (1024x1792)", value: "9:16" },
    { label: "Landscape (1792x1024)", value: "16:9" },
];

const STYLES = [
    { label: "No Style", value: "None" },
    { label: "Photorealistic", value: "Photorealistic" },
    { label: "Anime", value: "Anime" },
    { label: "Digital Art", value: "Digital Art" },
    { label: "Oil Painting", value: "Oil Painting" },
    { label: "Cyberpunk", value: "Cyberpunk" },
    { label: "Watercolor", value: "Watercolor" },
];

export const GenerationControls: React.FC<GenerationControlsProps> = ({
  mode,
  showAdvanced, setShowAdvanced,
  style, setStyle,
  numberOfImages, setNumberOfImages,
  aspectRatio, setAspectRatio,
  resolution, setResolution,
  outPaintingMode, setOutPaintingMode,
  scaleFactor, setScaleFactor,
  offsetPixels, setOffsetPixels,
  showTryOn, setShowTryOn,
  tryOnTarget, setTryOnTarget,
  providerId
}) => {
  const [showStyleMenu, setShowStyleMenu] = useState(false);
  const [showCountMenu, setShowCountMenu] = useState(false);
  const [showAspectMenu, setShowAspectMenu] = useState(false);
  const [showResMenu, setShowResMenu] = useState(false);
  const [showOutPaintMenu, setShowOutPaintMenu] = useState(false);

  // --- Dynamic Configuration based on Provider ---
  const isOpenAI = providerId === 'openai';
  const isTongYi = providerId === 'tongyi';
  const isGoogle = providerId === 'google' || providerId === 'google-custom';

  // 1. Aspect Ratios
  const availableRatios = useMemo(() => {
      if (mode === 'video-gen') {
          return [
              { label: "16:9 Landscape", value: "16:9" },
              { label: "9:16 Portrait", value: "9:16" },
          ];
      }
      if (isOpenAI) return OPENAI_ASPECT_RATIOS;
      
      // Google Specific: Edit mode has more ratios
      if (isGoogle && mode === 'image-edit') {
          return GOOGLE_EDIT_ASPECT_RATIOS;
      }

      // Default to standard set for Google Gen / TongYi / Others
      return GEN_ASPECT_RATIOS; 
  }, [mode, providerId]);

  // 2. Image Count Capability
  const canChangeCount = !isOpenAI && (mode === 'image-gen' || (isTongYi && mode === 'image-edit')); 

  // 3. Style Capability
  const showStyles = isTongYi || (isGoogle && mode === 'image-gen');

  // 4. Resolution Capability
  const showResolution = (isGoogle && mode === 'video-gen') || (mode !== 'video-gen' && !isOpenAI);
  const allow4K = isGoogle && mode === 'image-edit';

  // 5. LoRA Capability (TongYi Wanx 2.5)
  // We check if advanced is open inside the main AdvancedSettings component, 
  // but we can add a quick toggle here if needed. For now, let's keep it simple.

  // Helper for resolution label
  const getResolutionLabel = (res: string) => {
      if (mode === 'video-gen') {
          if (res === '1K') return '720p (HD)';
          if (res === '2K') return '1080p (FHD)';
          return res;
      }
      if (res === '1K') return '1K Standard';
      if (res === '2K') return '2K High';
      if (res === '4K') return '4K Ultra';
      return res;
  };

  return (
    <>
      {/* Try-On Controls (Edit Mode Only) */}
      {mode === 'image-edit' && setShowTryOn && !isTongYi && (
          <div className="flex items-center gap-2 bg-slate-800/50 p-1 rounded-lg border border-slate-700/50 transition-all hover:bg-slate-800">
              <button 
                  onClick={() => setShowTryOn(!showTryOn)}
                  className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium transition-all ${showTryOn ? 'bg-pink-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'}`}
                  title="Virtual Try-On Mode: Replaces specific items."
              >
                  <Shirt size={14} /> Try-On
              </button>
          </div>
      )}

      {/* Out-Painting Controls */}
      {mode === 'image-outpainting' && (
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
                              {['top', 'bottom', 'left', 'right'].map((dir) => (
                                  <div key={dir} className="flex flex-col gap-1">
                                      <label className="text-[10px] text-slate-500 uppercase">{dir}</label>
                                      <input 
                                          type="number" min="0" max="2000" step="64"
                                          value={offsetPixels[dir as keyof typeof offsetPixels]}
                                          onChange={(e) => setOffsetPixels(prev => ({...prev, [dir]: parseInt(e.target.value) || 0}))}
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
      )}

      {/* Advanced Toggle (Seed/Negative/LoRA) */}
      <button 
         onClick={() => setShowAdvanced(!showAdvanced)} 
         className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-transparent transition-all ${showAdvanced ? 'bg-slate-800 text-white' : 'bg-slate-800/50 text-slate-400 hover:text-slate-200'}`}
         title={isTongYi && mode === 'image-edit' ? "Advanced: Seed, Negative, LoRA" : "Advanced: Seed, Negative Prompt"}
      >
          <Sliders size={14} />
      </button>
      
      {/* Style Menu */}
      {showStyles && (
      <div className="relative">
         <button onClick={() => setShowStyleMenu(!showStyleMenu)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all">
            <Palette size={14} className="text-pink-400" />
            {style === "None" ? "Style" : style}
         </button>
         {showStyleMenu && (
             <>
             <div className="fixed inset-0 z-10" onClick={() => setShowStyleMenu(false)} />
             <div className="absolute bottom-full right-0 mb-2 w-48 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out]">
                 <div className="p-1 max-h-48 overflow-y-auto custom-scrollbar">
                     {STYLES.map((s) => (
                         <button key={s.value} onClick={() => { setStyle(s.value); setShowStyleMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between ${style === s.value ? 'bg-pink-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
                             {s.label}
                         </button>
                     ))}
                 </div>
             </div>
             </>
         )}
     </div>
     )}

     {/* Number of Images */}
     {canChangeCount && (
         <div className="relative">
             <button onClick={() => setShowCountMenu(!showCountMenu)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all">
                 <Layers size={14} className="text-blue-400" />
                 {numberOfImages} Img
             </button>
             {showCountMenu && (
                 <>
                 <div className="fixed inset-0 z-10" onClick={() => setShowCountMenu(false)} />
                 <div className="absolute bottom-full right-0 mb-2 w-32 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out]">
                     <div className="p-1">
                         {[1, 2, 3, 4].map((n) => (
                             <button key={n} onClick={() => { setNumberOfImages(n); setShowCountMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between ${numberOfImages === n ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
                                 {n} Image{n > 1 ? 's' : ''}
                             </button>
                         ))}
                     </div>
                 </div>
                 </>
             )}
         </div>
     )}
     
     {/* Aspect Ratio */}
     <div className="relative">
         <button onClick={() => setShowAspectMenu(!showAspectMenu)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all">
             <Ratio size={14} className="text-slate-400" />
             {availableRatios.find(r => r.value === aspectRatio)?.label.split(' ')[0] || aspectRatio}
         </button>
         {showAspectMenu && (
             <>
             <div className="fixed inset-0 z-10" onClick={() => setShowAspectMenu(false)} />
             <div className="absolute bottom-full right-0 mb-2 w-48 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out] max-h-64 overflow-y-auto custom-scrollbar">
                 <div className="p-1">
                     {availableRatios.map((ratio) => (
                         <button key={ratio.value} onClick={() => { setAspectRatio(ratio.value); setShowAspectMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between ${aspectRatio === ratio.value ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
                             {ratio.label}
                         </button>
                     ))}
                 </div>
             </div>
             </>
         )}
     </div>

     {/* Resolution */}
     {showResolution && (
         <div className="relative">
             <button onClick={() => setShowResMenu(!showResMenu)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all">
                <Maximize2 size={14} className="text-emerald-400" />
                {getResolutionLabel(resolution)}
             </button>
             {showResMenu && (
                 <>
                 <div className="fixed inset-0 z-10" onClick={() => setShowResMenu(false)} />
                 <div className="absolute bottom-full right-0 mb-2 w-40 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out]">
                     <div className="p-1">
                         <button onClick={() => { setResolution("1K"); setShowResMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between ${resolution === "1K" ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
                            {getResolutionLabel("1K")}
                         </button>
                         <button onClick={() => { setResolution("2K"); setShowResMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between ${resolution === "2K" ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
                            {getResolutionLabel("2K")}
                         </button>
                         {allow4K && (
                             <button onClick={() => { setResolution("4K"); setShowResMenu(false); }} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between ${resolution === "4K" ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
                                {getResolutionLabel("4K")}
                             </button>
                         )}
                     </div>
                 </div>
                 </>
             )}
         </div>
     )}
    </>
  );
};
