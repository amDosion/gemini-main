
import React, { useEffect, useState } from 'react';
import { 
  browserProgressService, 
  BrowseProgressUpdate 
} from '../../services/browserProgressService';
import { Globe, Loader2, CheckCircle2, XCircle } from 'lucide-react';

interface BrowserProgressIndicatorProps {
  operationId: string;
  onComplete?: () => void;
  onError?: (error: string) => void;
}

export const BrowserProgressIndicator: React.FC<BrowserProgressIndicatorProps> = ({
  operationId,
  onComplete,
  onError
}) => {
  const [progress, setProgress] = useState<BrowseProgressUpdate | null>(null);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    // Subscribe to progress updates
    const unsubscribe = browserProgressService.subscribe(
      operationId,
      (update) => {
        setProgress(update);
      },
      () => {
        onComplete?.();
        // Keep it visible for a moment showing completion state
        setTimeout(() => setIsVisible(false), 3000);
      },
      (error) => {
        onError?.(error);
        // Keep error visible longer
        setTimeout(() => setIsVisible(false), 5000);
      }
    );

    // Cleanup on unmount
    return () => {
      unsubscribe();
    };
  }, [operationId, onComplete, onError]);

  if (!isVisible || !progress) {
    return null;
  }

  const isCompleted = progress.status === 'completed';
  const isError = progress.status === 'error';

  return (
    <div className="flex flex-col gap-2 mt-2 mb-3 bg-slate-900/60 p-3 rounded-xl border border-slate-700/50 animate-[fadeIn_0.3s_ease-out] w-full max-w-md">
      <div className="flex items-start gap-3">
        {/* Status Icon */}
        <div className={`mt-0.5 shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${
            isCompleted ? 'bg-emerald-500/10 text-emerald-400' :
            isError ? 'bg-red-500/10 text-red-400' :
            'bg-blue-500/10 text-blue-400'
        }`}>
            {isCompleted ? <CheckCircle2 size={14} /> :
             isError ? <XCircle size={14} /> :
             <Loader2 size={14} className="animate-spin" />}
        </div>

        <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wide flex items-center gap-1.5">
                    <Globe size={10} className="opacity-70" />
                    Browser Tool
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                    {progress.status === 'in_progress' ? `${progress.progress || 0}%` : progress.status}
                </span>
            </div>
            
            <div className="text-xs text-slate-200 font-medium mt-1 truncate">
                {progress.step}
            </div>
            
            {progress.details && (
                <div className="text-[11px] text-slate-500 mt-0.5 leading-snug line-clamp-2">
                    {progress.details}
                </div>
            )}
        </div>
      </div>

      {/* Progress Bar */}
      {progress.status === 'in_progress' && (
          <div className="w-full bg-slate-800/80 rounded-full h-1 mt-1 overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-300 ease-out"
              style={{ width: `${progress.progress || 0}%` }}
            />
          </div>
      )}
    </div>
  );
};
