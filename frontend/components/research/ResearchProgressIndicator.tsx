import React from 'react';
import { AlertTriangle, CheckCircle2, Loader2, PauseCircle, Search, XCircle } from 'lucide-react';

const formatTime = (totalSeconds: number): string => {
  if (isNaN(totalSeconds) || totalSeconds < 0) return '00:00';
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
};

// 定义 ResearchProgressIndicator 组件的属性接口
export interface ResearchProgressIndicatorProps {
  status: 'starting' | 'in_progress' | 'awaiting_action' | 'completed' | 'failed' | 'cancelled';
  elapsedTime: number; // 已经过的时间，单位：秒
  estimatedTime?: number; // 预计剩余时间，单位：秒
  progress?: string; // 进度描述文本
}

const ResearchProgressIndicator: React.FC<ResearchProgressIndicatorProps> = ({
  status,
  elapsedTime,
  estimatedTime,
  progress,
}) => {
  const getStatusDisplay = () => {
    switch (status) {
      case 'starting':
        return (
          <div className="flex items-center gap-2 text-sky-300">
            <Loader2 size={16} className="animate-spin" />
            <span className="text-sm font-medium">正在启动研究</span>
          </div>
        );
      case 'in_progress':
        return (
          <div className="flex items-center gap-2 text-indigo-300">
            <Search size={16} className="animate-pulse" />
            <span className="text-sm font-medium">研究进行中</span>
          </div>
        );
      case 'completed':
        return (
          <div className="flex items-center gap-2 text-emerald-300">
            <CheckCircle2 size={16} />
            <span className="text-sm font-medium">研究完成</span>
          </div>
        );
      case 'awaiting_action':
        return (
          <div className="flex items-center gap-2 text-amber-300">
            <PauseCircle size={16} />
            <span className="text-sm font-medium">等待动作</span>
          </div>
        );
      case 'failed':
        return (
          <div className="flex items-center gap-2 text-rose-300">
            <AlertTriangle size={16} />
            <span className="text-sm font-medium">研究失败</span>
          </div>
        );
      case 'cancelled':
        return (
          <div className="flex items-center gap-2 text-slate-300">
            <XCircle size={16} />
            <span className="text-sm font-medium">已取消</span>
          </div>
        );
      default:
        return null;
    }
  };

  const calculateProgress = () => {
    if (status !== 'in_progress' || !estimatedTime || estimatedTime <= 0) {
      return { percentage: 0, remaining: 0 };
    }

    const currentProgress = Math.min(95, Math.floor((elapsedTime / estimatedTime) * 100));
    const remainingTime = Math.max(0, estimatedTime - elapsedTime);

    return { percentage: currentProgress, remaining: remainingTime };
  };

  const { percentage, remaining } = calculateProgress();
  const showBusy = status === 'starting' || status === 'in_progress';

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-900/70 px-4 py-3 text-slate-100 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        {getStatusDisplay()}
        {showBusy && (
          <div className="text-xs text-slate-400">
            已用时 {formatTime(elapsedTime)}
            {estimatedTime ? ` · 剩余 ${formatTime(remaining)}` : ''}
          </div>
        )}
      </div>

      {status === 'in_progress' && estimatedTime ? (
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className="h-full rounded-full bg-indigo-500 transition-all duration-500 ease-out"
            style={{ width: `${percentage}%` }}
            role="progressbar"
            aria-valuenow={percentage}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Research progress"
          />
        </div>
      ) : showBusy ? (
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
          <div className="h-full w-1/3 animate-[pulse_1.2s_ease-in-out_infinite] rounded-full bg-indigo-500/70" />
        </div>
      ) : null}

      {progress && (
        <p className="mt-2 text-xs italic text-slate-400">
          {progress}
        </p>
      )}
    </div>
  );
};

export default ResearchProgressIndicator;
