/**
 * @file WelcomeScreen.tsx
 * @description 欢迎屏幕组件，用于引导新用户配置应用。
 */

import React from 'react';

/**
 * WelcomeScreen 组件属性
 */
export interface WelcomeScreenProps {
  /** 打开设置回调函数 */
  onOpenSettings: () => void;
  /** 欢迎标题 */
  title?: string;
  /** 欢迎消息 */
  message?: string;
  /** 按钮文本 */
  buttonText?: string;
  /** 自定义类名 */
  className?: string;
}

/**
 * 欢迎屏幕组件
 * 
 * 显示一个全屏欢迎页面，引导用户进行初始配置。
 * 用于新用户首次使用或用户未配置 AI 提供商的场景。
 * 
 * @example
 * ```tsx
 * <WelcomeScreen 
 *   onOpenSettings={() => setIsSettingsOpen(true)} 
 * />
 * ```
 */
export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
  onOpenSettings,
  title = '欢迎使用！',
  message = '请先配置您的 AI 提供商以开始使用',
  buttonText = '打开设置',
  className = '',
}) => {
  return (
    <div className={`fixed inset-0 z-40 bg-[#0f172a] flex items-center justify-center ${className}`}>
      <div className="flex flex-col items-center gap-6 max-w-md p-6">
        {/* 欢迎图标 */}
        <div 
          className="text-6xl"
          role="img"
          aria-label="欢迎"
        >
          👋
        </div>
        
        {/* 欢迎标题 */}
        <h2 className="text-2xl font-semibold text-white">
          {title}
        </h2>
        
        {/* 欢迎消息 */}
        <p className="text-gray-400 text-center">
          {message}
        </p>
        
        {/* 打开设置按钮 */}
        <button
          onClick={onOpenSettings}
          className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors font-medium"
        >
          {buttonText}
        </button>
      </div>
    </div>
  );
};

export default WelcomeScreen;
