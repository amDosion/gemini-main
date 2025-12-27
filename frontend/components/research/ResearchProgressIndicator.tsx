import React from 'react';
import { formatTime } from '../../hooks/useDeepResearch'; // 导入 formatTime 辅助函数

// 定义 ResearchProgressIndicator 组件的属性接口
export interface ResearchProgressIndicatorProps {
  status: 'starting' | 'in_progress' | 'completed' | 'failed';
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
  // 根据状态显示不同的图标和文本
  const getStatusDisplay = () => {
    switch (status) {
      case 'starting':
        return (
          <span className="flex items-center text-blue-500">
            <span className="animate-spin mr-2">🔄</span> 开始研究... {/* 🔄 转圈图标表示开始 */}
          </span>
        );
      case 'in_progress':
        return (
          <span className="flex items-center text-yellow-500">
            <span className="animate-pulse mr-2">🔍</span> 研究进行中... {/* 🔍 放大镜图标表示进行中 */}
          </span>
        );
      case 'completed':
        return (
          <span className="flex items-center text-green-500">
            <span className="mr-2">✅</span> 研究完成 {/* ✅ 勾选图标表示完成 */}
          </span>
        );
      case 'failed':
        return (
          <span className="flex items-center text-red-500">
            <span className="mr-2">❌</span> 研究失败 {/* ❌ 叉号图标表示失败 */}
          </span>
        );
      default:
        return null;
    }
  };

  // 计算进度百分比和剩余时间
  const calculateProgress = () => {
    if (status !== 'in_progress' || !estimatedTime || estimatedTime <= 0) {
      return { percentage: 0, remaining: 0 };
    }

    // 确保进度条在未完成时不达到100%，最大限制为95%
    const currentProgress = Math.min(95, Math.floor((elapsedTime / estimatedTime) * 100));
    const remainingTime = Math.max(0, estimatedTime - elapsedTime);

    return { percentage: currentProgress, remaining: remainingTime };
  };

  const { percentage, remaining } = calculateProgress();

  return (
    <div className="p-4 bg-gray-800 rounded-lg shadow-md text-white max-w-sm mx-auto">
      {/* 状态显示区域 */}
      <div className="flex items-center justify-between mb-3">
        <div className="text-lg font-semibold">{getStatusDisplay()}</div>
        {/* 如果正在进行中，显示已用时间和预估时间 */}
        {status === 'in_progress' && (
          <div className="text-sm text-gray-400">
            已用时: {formatTime(elapsedTime)}
            {estimatedTime && ` | 剩余: ${formatTime(remaining)}`} {/* 只在有预估时间时显示剩余时间 */}
          </div>
        )}
      </div>

      {/* 进度条 (只在进行中且有预估时间时显示) */}
      {status === 'in_progress' && estimatedTime && (
        <div className="w-full bg-gray-700 rounded-full h-2.5 mb-3">
          <div
            className="bg-blue-600 h-2.5 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${percentage}%` }}
            role="progressbar"
            aria-valuenow={percentage}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Research progress"
          ></div>
        </div>
      )}

      {/* 进度描述文本 (如果提供) */}
      {progress && (
        <p className="text-sm text-gray-300 italic">
          {progress}
        </p>
      )}
    </div>
  );
};

export default ResearchProgressIndicator;