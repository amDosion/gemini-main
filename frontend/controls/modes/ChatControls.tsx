import React from 'react';
import { Globe, Brain, Code2, Link2, MonitorDot, Zap, Database } from 'lucide-react';
import { ChatControlsProps } from '../types';

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
    <div className="flex items-center gap-1 bg-slate-900/60 p-1 rounded-full border border-slate-700/50 backdrop-blur-md overflow-x-auto max-w-full custom-scrollbar shadow-sm">
      <button
        onClick={() => canSearch && setEnableSearch(!enableSearch)}
        disabled={!canSearch}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border shrink-0 ${!canSearch ? 'bg-transparent text-slate-600 cursor-not-allowed opacity-40 border-transparent'
          : enableSearch ? 'bg-blue-600 text-blue-50 border-transparent shadow-sm'
            : 'bg-transparent text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200'
          }`}
        title="Google Search Grounding"
      >
        <Globe size={13} strokeWidth={2.5} /> Search
      </button>

      {canBrowse && (
        <button
          onClick={() => setEnableBrowser && setEnableBrowser(!enableBrowser)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border shrink-0 ${enableBrowser ? 'bg-orange-600 text-orange-50 border-transparent shadow-sm'
            : 'bg-transparent text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200'
            }`}
          title="Real-time Web Browser (Needs Backend)"
        >
          <MonitorDot size={13} strokeWidth={2.5} /> Browse
        </button>
      )}

      {canRAG && (
        <button
          onClick={() => {
            if (onOpenDocuments && !enableRAG) onOpenDocuments();
            setEnableRAG && setEnableRAG(!enableRAG);
          }}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border shrink-0 ${enableRAG ? 'bg-teal-600 text-teal-50 border-transparent shadow-sm'
            : 'bg-transparent text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200'
            }`}
          title="RAG: Talk to Your Documents"
        >
          <Database size={13} strokeWidth={2.5} /> RAG
        </button>
      )}


      {canCache && (
        <button
          onClick={cycleCacheMode}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border shrink-0 ${googleCacheMode === 'exact' ? 'bg-blue-600 text-blue-50 border-transparent shadow-sm'
            : googleCacheMode === 'semantic' ? 'bg-purple-600 text-purple-50 border-transparent shadow-sm'
              : 'bg-transparent text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200'
            }`}
          title="Implicit Context Caching (Reduce latency/cost)"
        >
          <Zap size={13} strokeWidth={2.5} className={googleCacheMode !== 'none' ? 'fill-current' : ''} />
          {getCacheLabel()}
        </button>
      )}

      <button
        onClick={() => canThink && setEnableThinking(!enableThinking)}
        disabled={!canThink}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border shrink-0 ${!canThink ? 'bg-transparent text-slate-600 cursor-not-allowed opacity-40 border-transparent'
          : enableThinking ? 'bg-purple-600 text-purple-50 border-transparent shadow-sm'
            : 'bg-transparent text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200'
          }`}
        title="Reasoning / Thinking"
      >
        <Brain size={13} strokeWidth={2.5} /> Reasoning
      </button>

      <button
        onClick={() => canUrlContext && setEnableUrlContext(!enableUrlContext)}
        disabled={!canUrlContext}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border shrink-0 ${!canUrlContext ? 'bg-transparent text-slate-600 cursor-not-allowed opacity-40 border-transparent'
          : enableUrlContext ? 'bg-emerald-600 text-emerald-50 border-transparent shadow-sm'
            : 'bg-transparent text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200'
          }`}
        title="Read content from URLs in prompt"
      >
        <Link2 size={13} strokeWidth={2.5} /> URL Context
      </button>

      <button
        onClick={() => canCode && setEnableCodeExecution(!enableCodeExecution)}
        disabled={!canCode}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border shrink-0 ${!canCode ? 'bg-transparent text-slate-600 cursor-not-allowed opacity-40 border-transparent'
          : enableCodeExecution ? 'bg-amber-600 text-amber-50 border-transparent shadow-sm'
            : 'bg-transparent text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200'
          }`}
        title="Code Execution"
      >
        <Code2 size={13} strokeWidth={2.5} /> Code
      </button>
    </div>
  );
};

export default ChatControls;
