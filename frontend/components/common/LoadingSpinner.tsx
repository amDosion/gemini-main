/**
 * @file LoadingSpinner.tsx
 * @description 全屏加载动画组件，用于显示应用初始化或数据加载状态。
 */

import React from 'react';

/**
 * LoadingSpinner 组件属性
 */
export interface LoadingSpinnerProps {
  /** 加载消息文本 */
  message?: string;
  /** 是否显示消息 */
  showMessage?: boolean;
  /** 自定义类名 */
  className?: string;
}

/**
 * 全屏加载动画组件
 * 
 * 显示一个居中的旋转加载动画，可选显示加载消息。
 * 用于应用初始化、认证检查等全屏加载场景。
 * 
 * @example
 * ```tsx
 * <LoadingSpinner message="正在加载配置..." />
 * ```
 */
export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  message = '加载中...',
  showMessage = true,
  className = '',
}) => {
  return (
    <div className={`fixed inset-0 bg-[#0f172a] flex items-center justify-center ${className}`}>
      <div className="flex flex-col items-center gap-4">
        {/* 旋转加载动画 */}
        <div 
          className="w-10 h-10 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"
          role="status"
          aria-label="加载中"
        />
        
        {/* 加载消息 */}
        {showMessage && message && (
          <p className="text-gray-400 text-sm">
            {message}
          </p>
        )}
      </div>
    </div>
  );
};

export default LoadingSpinner;
