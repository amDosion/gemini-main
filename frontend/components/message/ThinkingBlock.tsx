
import React from 'react';
import { BrainCircuit, ChevronDown, ChevronRight } from 'lucide-react';

interface ThinkingBlockProps {
  content: string;
  isOpen: boolean;
  onToggle: () => void;
  isComplete: boolean;
}

export const ThinkingBlock: React.FC<ThinkingBlockProps> = ({ content, isOpen, onToggle, isComplete }) => {
  if (!content) return null;

  return (
    <div className="border border-purple-500/30 bg-purple-900/10 rounded-lg overflow-hidden mb-2 animate-[fadeIn_0.5s_ease-out]">
        <button 
            onClick={onToggle}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-purple-300 hover:bg-purple-900/20 transition-colors bg-purple-900/20"
        >
            <BrainCircuit size={14} className={!isComplete ? "animate-pulse" : ""} />
            <span>
                {isComplete ? "Thought Process" : "Thinking..."}
            </span>
            <div className="ml-auto">
                {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </div>
        </button>
        {isOpen && (
            <div className="px-3 py-2 border-t border-purple-500/20 bg-slate-900/30 max-h-[300px] overflow-y-auto custom-scrollbar">
                <div className="prose prose-invert prose-xs max-w-none text-slate-400 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
                    {content}
                    {!isComplete && (
                        <span className="inline-block w-1.5 h-3 ml-1 bg-purple-400 animate-pulse align-middle"/>
                    )}
                </div>
            </div>
        )}
    </div>
  );
};
