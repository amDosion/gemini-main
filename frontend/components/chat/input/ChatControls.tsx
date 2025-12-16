
import React from 'react';
import { Globe, Brain, Code2, Link2, MonitorDot, Zap, Database } from 'lucide-react';
import { ModelConfig } from '../../../../types';

interface ChatControlsProps {
  currentModel?: ModelConfig;
  enableSearch: boolean;
  setEnableSearch: (v: boolean) => void;
  enableThinking: boolean;
  setEnableThinking: (v: boolean) => void;
  enableCodeExecution: boolean;
  setEnableCodeExecution: (v: boolean) => void;
  enableUrlContext: boolean;
  setEnableUrlContext: (v: boolean) => void;
  enableBrowser?: boolean;
  setEnableBrowser?: (v: boolean) => void;
  enableRAG?: boolean;
  setEnableRAG?: (v: boolean) => void;
  onOpenDocuments?: () => void;
  // Cache Control
  googleCacheMode?: 'none' | 'exact' | 'semantic';
  setGoogleCacheMode?: (v: 'none' | 'exact' | 'semantic') => void;
}

export const ChatControls: React.FC<ChatControlsProps> = ({
  currentModel,
  enableSearch, setEnableSearch,
  enableThinking, setEnableThinking,
  enableCodeExecution, setEnableCodeExecution,
  enableUrlContext, setEnableUrlContext,
  enableBrowser, setEnableBrowser,
  enableRAG, setEnableRAG,
  onOpenDocuments,
  googleCacheMode = 'none', setGoogleCacheMode
}) => {
  const canSearch = currentModel?.capabilities.search || false;
  const canThink = currentModel?.capabilities.reasoning || false;
  const canCode = currentModel?.capabilities.coding || false;
  const canUrlContext = !currentModel?.id.includes('imagen') && !currentModel?.id.includes('veo');
  const canBrowse = !currentModel?.id.includes('imagen') && !currentModel?.id.includes('veo') && setEnableBrowser;
  const canRAG = !currentModel?.id.includes('imagen') && !currentModel?.id.includes('veo') && setEnableRAG;

  // Cache is supported broadly on Gemini, but we can restrict if needed.
  // Assuming all Google models might support implicit cache in v1beta.
  const canCache = currentModel?.id.includes('gemini') && setGoogleCacheMode;

  const cycleCacheMode = () => {
    if (!setGoogleCacheMode) return;
    if (googleCacheMode === 'none') setGoogleCacheMode('exact');
    else if (googleCacheMode === 'exact') setGoogleCacheMode('semantic');
    else setGoogleCacheMode('none');
  };

  const getCacheLabel = () => {
    if (googleCacheMode === 'exact') return 'Cache: Exact';
    if (googleCacheMode === 'semantic') return 'Cache: Smart';
    return 'Cache: Off';
  };

  return (
    <div className="flex items-center gap-2 overflow-x-auto scrollbar-hide max-w-full sm:max-w-none pb-1 sm:pb-0">
      <button
        onClick={() => canSearch && setEnableSearch(!enableSearch)}
        disabled={!canSearch}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border shrink-0 ${!canSearch ? 'bg-slate-800/20 text-slate-600 cursor-not-allowed opacity-50'
            : enableSearch ? 'bg-blue-600/20 text-blue-300 border-blue-500/50'
              : 'bg-slate-800/50 text-slate-400 border-transparent'
          }`}
        title="Google Search Grounding"
      >
        <Globe size={14} /> Search
      </button>

      {canBrowse && (
        <button
          onClick={() => setEnableBrowser && setEnableBrowser(!enableBrowser)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border shrink-0 ${enableBrowser ? 'bg-orange-600/20 text-orange-300 border-orange-500/50'
              : 'bg-slate-800/50 text-slate-400 border-transparent'
            }`}
          title="Real-time Web Browser (Needs Backend)"
        >
          <MonitorDot size={14} /> Browse
        </button>
      )}

      {canRAG && (
        <button
          onClick={() => {
            if (onOpenDocuments && !enableRAG) {
              // If RAG is disabled and we have the open documents callback, open the modal
              onOpenDocuments();
            }
            setEnableRAG && setEnableRAG(!enableRAG);
          }}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border shrink-0 ${enableRAG ? 'bg-teal-600/20 text-teal-300 border-teal-500/50'
              : 'bg-slate-800/50 text-slate-400 border-transparent'
            }`}
          title="RAG: Talk to Your Documents"
        >
          <Database size={14} /> RAG
        </button>
      )}

      {canCache && (
        <button
          onClick={cycleCacheMode}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border shrink-0 ${googleCacheMode === 'exact' ? 'bg-blue-600/20 text-blue-300 border-blue-500/50'
              : googleCacheMode === 'semantic' ? 'bg-purple-600/20 text-purple-300 border-purple-500/50'
                : 'bg-slate-800/50 text-slate-400 border-transparent'
            }`}
          title="Implicit Context Caching (Reduce latency/cost)"
        >
          <Zap size={14} className={googleCacheMode !== 'none' ? 'fill-current' : ''} />
          {getCacheLabel()}
        </button>
      )}

      <button
        onClick={() => canThink && setEnableThinking(!enableThinking)}
        disabled={!canThink}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border shrink-0 ${!canThink ? 'bg-slate-800/20 text-slate-600 cursor-not-allowed opacity-50'
            : enableThinking ? 'bg-purple-600/20 text-purple-300 border-purple-500/50'
              : 'bg-slate-800/50 text-slate-400 border-transparent'
          }`}
        title="Reasoning / Thinking"
      >
        <Brain size={14} /> Reasoning
      </button>

      <button
        onClick={() => canUrlContext && setEnableUrlContext(!enableUrlContext)}
        disabled={!canUrlContext}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border shrink-0 ${!canUrlContext ? 'bg-slate-800/20 text-slate-600 cursor-not-allowed opacity-50'
            : enableUrlContext ? 'bg-emerald-600/20 text-emerald-300 border-emerald-500/50'
              : 'bg-slate-800/50 text-slate-400 border-transparent'
          }`}
        title="Read content from URLs in prompt"
      >
        <Link2 size={14} /> URL Context
      </button>

      <button
        onClick={() => canCode && setEnableCodeExecution(!enableCodeExecution)}
        disabled={!canCode}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border shrink-0 ${!canCode ? 'bg-slate-800/20 text-slate-600 cursor-not-allowed opacity-50'
            : enableCodeExecution ? 'bg-amber-600/20 text-amber-300 border-amber-500/50'
              : 'bg-slate-800/50 text-slate-400 border-transparent'
          }`}
        title="Code Execution"
      >
        <Code2 size={14} /> Code
      </button>
    </div>
  );
};
