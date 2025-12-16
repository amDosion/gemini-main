
import React from 'react';
import { Globe } from 'lucide-react';

interface SearchProcessProps {
  queries: string[];
  entryPoint?: string;
  isThinking: boolean;
}

export const SearchProcess: React.FC<SearchProcessProps> = ({ queries, entryPoint, isThinking }) => {
  return (
    <div className="flex flex-col gap-2 mb-1 bg-slate-900/60 p-3 rounded-lg border border-slate-700/50 animate-[fadeIn_0.5s_ease-out]">
        <div className="flex items-center gap-2 text-xs text-blue-300 font-bold uppercase tracking-wider mb-1">
            <Globe size={12} className={isThinking ? "animate-pulse" : ""} />
            <span>Search Process</span>
        </div>
        {queries.length > 0 ? (
        <div className="space-y-2">
            {queries.map((query, idx) => (
            <div key={idx} className="flex items-start gap-2 text-xs text-slate-400">
                <div className="mt-1.5 w-1 h-1 rounded-full bg-blue-500 shrink-0"></div>
                <div>
                    <span className="opacity-70 mr-1">Searching:</span>
                    <span className="font-mono text-blue-200 break-words">"{query}"</span>
                </div>
            </div>
            ))}
        </div>
        ) : (
        !entryPoint && <div className="text-xs text-slate-500 italic pl-3">Analyzing search results...</div>
        )}
        {entryPoint && (
            <div 
                className="mt-2 overflow-hidden rounded bg-white text-black"
                dangerouslySetInnerHTML={{ __html: entryPoint }} 
            />
        )}
    </div>
  );
};
