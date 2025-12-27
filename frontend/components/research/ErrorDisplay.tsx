import React, { useState } from 'react';

// 定义 ResearchError 接口，描述错误的结构
export interface ResearchError {
  code: string; // 错误代码，用于识别错误类型
  message: string; // 错误消息，显示给用户
  suggestions: string[]; // 解决建议列表
  details?: any; // 可选的错误详情，可以是任何类型，用于技术调试
}

// 定义 ErrorDisplay 组件的属性接口
export interface ErrorDisplayProps {
  error: ResearchError; // 错误对象
  onRetry?: () => void; // 可选的重试回调函数
  onDismiss?: () => void; // 可选的关闭回调函数
}

const ErrorDisplay: React.FC<ErrorDisplayProps> = ({ error, onRetry, onDismiss }) => {
  // 控制技术详情部分是否展开的状态
  const [showDetails, setShowDetails] = useState(false);

  // 根据错误代码获取对应的图标
  const getErrorIcon = (code: string) => {
    switch (code) {
      case 'RESOURCE_EXHAUSTED':
        return '⏱️'; // 配额超出
      case 'INVALID_ARGUMENT':
        return '⚠️'; // 无效请求参数
      case 'SERVICE_UNAVAILABLE':
        return '🔧'; // 服务不可用
      case 'TIMEOUT':
        return '⏰'; // 请求超时
      case 'UNAUTHENTICATED':
        return '🔑'; // 认证失败
      default:
        return '❌'; // 默认通用错误
    }
  };

  // 根据错误代码获取主色调
  const getErrorColorClass = (code: string) => {
    switch (code) {
      case 'RESOURCE_EXHAUSTED':
      case 'TIMEOUT':
        return 'bg-orange-600 border-orange-700'; // 橙色系表示警告或暂时性问题
      case 'INVALID_ARGUMENT':
      case 'UNAUTHENTICATED':
        return 'bg-yellow-600 border-yellow-700'; // 黄色系表示用户输入问题或权限问题
      case 'SERVICE_UNAVAILABLE':
      default:
        return 'bg-red-600 border-red-700'; // 红色系表示严重错误
    }
  };

  const icon = getErrorIcon(error.code);
  const colorClass = getErrorColorClass(error.code);

  return (
    <div className={`p-4 rounded-lg border-2 shadow-lg text-white max-w-md mx-auto ${colorClass}`}>
      {/* 错误头部：图标和错误消息 */}
      <div className="flex items-center mb-3">
        <span className="text-3xl mr-3">{icon}</span>
        <h3 className="text-xl font-bold flex-grow">{error.message}</h3>
      </div>

      {/* 解决建议列表（如果存在） */}
      {error.suggestions && error.suggestions.length > 0 && (
        <div className="mb-3">
          <p className="font-semibold mb-1">解决建议:</p>
          <ul className="list-disc list-inside text-sm text-gray-100">
            {error.suggestions.map((suggestion, index) => (
              <li key={index}>{suggestion}</li>
            ))}
          </ul>
        </div>
      )}

      {/* 技术详情（如果存在且已展开） */}
      {error.details && (
        <div className="mb-3">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="text-blue-200 hover:text-blue-100 text-sm focus:outline-none flex items-center"
            aria-expanded={showDetails}
            aria-controls="technical-details"
          >
            技术详情
            <svg
              className={`ml-1 w-4 h-4 transition-transform duration-300 ${showDetails ? 'rotate-90' : ''}`}
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                clipRule="evenodd"
              />
            </svg>
          </button>
          {showDetails && (
            <div id="technical-details" className="mt-2 p-2 bg-gray-700 rounded-md text-xs font-mono overflow-auto max-h-40">
              <pre className="whitespace-pre-wrap">{JSON.stringify(error.details, null, 2)}</pre>
            </div>
          )}
        </div>
      )}

      {/* 动作按钮（如果回调函数存在） */}
      <div className="flex justify-end gap-2">
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-4 py-2 rounded-md bg-blue-500 hover:bg-blue-600 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
          >
            重试
          </button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="px-4 py-2 rounded-md bg-gray-500 hover:bg-gray-600 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-opacity-50"
          >
            关闭
          </button>
        )}
      </div>
    </div>
  );
};

export default ErrorDisplay;