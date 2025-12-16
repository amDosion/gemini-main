
import React from 'react';
import { LoraConfig } from '../../../../types';

interface AdvancedSettingsProps {
  negativePrompt: string;
  setNegativePrompt: (v: string) => void;
  seed: number;
  setSeed: (v: number) => void;
  // LoRA support
  loraConfig?: LoraConfig;
  setLoraConfig?: (v: LoraConfig) => void;
}

export const AdvancedSettings: React.FC<AdvancedSettingsProps> = ({
  negativePrompt, setNegativePrompt,
  seed, setSeed,
  loraConfig, setLoraConfig
}) => {
  return (
    <div className="mb-2 p-3 bg-slate-900/80 rounded-xl border border-slate-800 grid grid-cols-1 md:grid-cols-2 gap-3 animate-[fadeIn_0.2s_ease-out]">
        <div className="space-y-1">
            <label className="text-[10px] uppercase text-slate-500 font-bold tracking-wider">Negative Prompt</label>
            <input 
              type="text"
              value={negativePrompt}
              onChange={(e) => setNegativePrompt(e.target.value)}
              placeholder="blurry, bad quality, distorted..."
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:border-red-500/50 outline-none"
            />
        </div>
        <div className="space-y-1">
             <label className="text-[10px] uppercase text-slate-500 font-bold tracking-wider">Seed</label>
             <div className="flex gap-2">
                 <input 
                      type="number"
                      value={seed}
                      onChange={(e) => setSeed(parseInt(e.target.value))}
                      placeholder="-1 (Random)"
                      className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:border-indigo-500/50 outline-none font-mono"
                 />
                 <button onClick={() => setSeed(-1)} className="px-2 bg-slate-800 border border-slate-700 rounded-lg hover:bg-slate-700 text-slate-400" title="Randomize">🎲</button>
             </div>
        </div>
        
        {/* LoRA Settings (Only show if setLoraConfig is provided) */}
        {setLoraConfig && (
            <div className="md:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-slate-800/50">
                <div className="space-y-1">
                    <label className="text-[10px] uppercase text-indigo-400 font-bold tracking-wider">LoRA Image URL (WanX 2.5)</label>
                    <input 
                      type="text"
                      value={loraConfig?.image || ''}
                      onChange={(e) => setLoraConfig({ ...loraConfig, image: e.target.value })}
                      placeholder="https://example.com/style.png"
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:border-indigo-500/50 outline-none"
                    />
                </div>
                <div className="space-y-1">
                    <label className="text-[10px] uppercase text-indigo-400 font-bold tracking-wider">LoRA Strength (0.0 - 1.0)</label>
                    <input 
                      type="number"
                      min="0" max="1" step="0.1"
                      value={loraConfig?.alpha ?? 0.6}
                      onChange={(e) => setLoraConfig({ ...loraConfig, alpha: parseFloat(e.target.value) })}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:border-indigo-500/50 outline-none"
                    />
                </div>
            </div>
        )}
    </div>
  );
};
