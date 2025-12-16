
import React from 'react';
import { Link as LinkIcon } from 'lucide-react';
import { GroundingChunk } from '../../../types';

interface GroundingSourcesProps {
  chunks?: GroundingChunk[];
}

export const GroundingSources: React.FC<GroundingSourcesProps> = ({ chunks }) => {
  if (!chunks || chunks.length === 0) return null;

  return (
    <div className="bg-slate-900/40 rounded-lg p-3 border border-slate-700/50 mt-2">
        <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2 flex items-center gap-1.5">
            <LinkIcon size={12} />
            Sources found
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {chunks.map((chunk, idx) => chunk.web ? (
                <a 
                    key={idx} 
                    href={chunk.web.uri} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 p-2 rounded-lg hover:bg-slate-700/50 transition-all border border-slate-800 hover:border-slate-600 group/link bg-slate-900/50"
                >
                    <div className="w-5 h-5 rounded bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 text-[10px] text-slate-400 font-mono group-hover/link:text-blue-400 group-hover/link:border-blue-500/30">
                        {idx + 1}
                    </div>
                    <div className="min-w-0 flex-1">
                        <div className="text-xs text-blue-300 truncate font-medium group-hover/link:text-blue-200">{chunk.web.title}</div>
                        <div className="text-[10px] text-slate-500 truncate">{new URL(chunk.web.uri).hostname}</div>
                    </div>
                </a>
            ) : null)}
        </div>
    </div>
  );
};
