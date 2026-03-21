/**
 * @file ErrorView.tsx
 * @description 错误页面组件，用于显示加载失败或其他错误状态。
 */

import React from 'react';

/**
 * ErrorView 组件属性
 */
export interface ErrorViewProps {
  /** 错误对象 */
  error: Error;
  /** 重试回调函数 */
  onRetry?: () => void;
  /** 错误标题 */
  title?: string;
  /** 是否显示错误详情 */
  showDetails?: boolean;
  /** 自定义类名 */
  className?: string;
}

/**
 * 错误页面组件
 * 
 * 显示一个全屏错误页面，包含错误图标、标题、消息和重试按钮。
 * 用于应用初始化失败、网络错误等场景。
 * 
 * @example
 * ```tsx
 * <ErrorView 
 *   error={new Error('加载失败')} 
 *   onRetry={() => window.location.reload()} 
 * />
 * ```
 */
export const ErrorView: React.FC<ErrorViewProps> = ({
  error,
  onRetry,
  title = '加载失败',
  showDetails = true,
  className = '',
}) => {
  // 记录错误到控制台
  React.useEffect(() => {
  }, [error, title]);

  return (
    <div className={`fixed inset-0 bg-[#0f172a] flex items-center justify-center ${className}`}>
      <div className="flex flex-col items-center gap-4 max-w-md p-6">
        {/* 错误图标 */}
        <div 
          className="text-red-500 text-4xl"
          role="img"
          aria-label="错误"
        >
          ⚠️
        </div>
        
        {/* 错误标题 */}
        <h2 className="text-xl font-semibold text-white">
          {title}
        </h2>
        
        {/* 错误消息 */}
        {showDetails && (
          <p className="text-gray-400 text-center">
            {error.message || '发生未知错误'}
          </p>
        )}
        
        {/* 重试按钮 */}
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors font-medium"
          >
            重试
          </button>
        )}
      </div>
    </div>
  );
};

export default ErrorView;
