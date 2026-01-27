import React from 'react';
import { Settings2, Cloud, Zap } from 'lucide-react';
import { DeepResearchControlsProps } from '../../types';

export const DeepResearchControls: React.FC<DeepResearchControlsProps> = ({
  thinkingSummaries,
  setThinkingSummaries,
  researchMode = 'vertex-ai',
  setResearchMode
}) => {
  return (
    <div className="flex items-center gap-1 bg-slate-900/60 p-1 rounded-full border border-slate-700/50 backdrop-blur-md overflow-x-auto max-w-full custom-scrollbar shadow-sm">
      {/* 工作模式切换 */}
      {setResearchMode && (
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => setResearchMode(
              researchMode === 'vertex-ai' ? 'gemini-api' : 'vertex-ai'
            )}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border shrink-0 ${
              researchMode === 'gemini-api'
                ? 'bg-blue-600 text-blue-50 border-transparent shadow-sm'
                : 'bg-transparent text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200'
            }`}
            title={researchMode === 'gemini-api' 
              ? 'Gemini API 模式（使用 genai SDK，不依赖 Vertex AI 配额）' 
              : 'Vertex AI 模式（使用 interactions API，需要配额）'}
          >
            {researchMode === 'gemini-api' ? (
              <Zap size={13} strokeWidth={2.5} />
            ) : (
              <Cloud size={13} strokeWidth={2.5} />
            )}
            <span>{researchMode === 'gemini-api' ? 'Gemini API' : 'Vertex AI'}</span>
          </button>
        </div>
      )}

      {/* 思考摘要配置 */}
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={() => setThinkingSummaries(thinkingSummaries === 'auto' ? 'none' : 'auto')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border shrink-0 ${
            thinkingSummaries === 'auto'
              ? 'bg-purple-600 text-purple-50 border-transparent shadow-sm'
              : 'bg-transparent text-slate-400 border-transparent hover:bg-slate-800/50 hover:text-slate-200'
          }`}
          title={`思考摘要: ${thinkingSummaries === 'auto' ? '自动（显示思考过程）' : '关闭（仅显示结果）'}`}
        >
          <Settings2 size={13} strokeWidth={2.5} />
          <span>思考摘要: {thinkingSummaries === 'auto' ? '自动' : '关闭'}</span>
        </button>
      </div>
    </div>
  );
};

export default DeepResearchControls;
