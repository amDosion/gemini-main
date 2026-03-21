
import React from 'react';
import { UrlContextMetadata } from '../../types/types';
import { Link2, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

interface UrlContextStatusProps {
  metadata: UrlContextMetadata | null | undefined;
}

export const UrlContextStatus: React.FC<UrlContextStatusProps> = ({ metadata }) => {
  if (!metadata || !metadata.urlMetadata || metadata.urlMetadata.length === 0) return null;

  return (
    <div className="bg-slate-900/40 rounded-lg p-3 border border-slate-700/50 mt-2 animate-[fadeIn_0.5s_ease-out]">
        <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2 flex items-center gap-1.5">
            <Link2 size={12} />
            URL Context Status
        </div>
        <div className="space-y-2">
            {metadata.urlMetadata.map((item: { retrievedUrl: string; urlRetrievalStatus: string }, idx: number) => {
                const isSuccess = item.urlRetrievalStatus === 'URL_RETRIEVAL_STATUS_SUCCESS' || item.urlRetrievalStatus === 'SUCCESS';
                const isUnsafe = item.urlRetrievalStatus?.includes('UNSAFE');
                
                return (
                    <div key={idx} className="flex items-center justify-between text-xs p-2 rounded bg-slate-800/50 border border-slate-800">
                        <div className="flex items-center gap-2 min-w-0">
                            {isSuccess ? <CheckCircle2 size={14} className="text-emerald-500 shrink-0" /> : 
                             isUnsafe ? <AlertTriangle size={14} className="text-orange-500 shrink-0" /> :
                             <XCircle size={14} className="text-red-500 shrink-0" />}
                            <a href={item.retrievedUrl} target="_blank" rel="noreferrer" className="truncate text-slate-300 hover:text-blue-400 hover:underline" title={item.retrievedUrl}>
                                {item.retrievedUrl}
                            </a>
                        </div>
                        <span className={`text-[9px] font-mono uppercase ml-2 shrink-0 ${isSuccess ? 'text-emerald-500' : 'text-slate-500'}`}>
                            {isSuccess ? 'Fetched' : 'Failed'}
                        </span>
                    </div>
                );
            })}
        </div>
    </div>
  );
};
