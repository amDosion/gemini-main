/**
 * @file CacheIndicator.tsx
 * @description 缓存状态指示器组件，显示缓存状态图标和信息。
 */

import React from 'react';
import { CacheStatusInfo } from '../../hooks/useCacheStatus';

/**
 * CacheIndicator 组件属性
 */
export interface CacheIndicatorProps {
  /** 缓存状态信息 */
  status: CacheStatusInfo;
  /** 刷新回调函数 */
  onRefresh?: () => void;
  /** 是否显示时间戳 */
  showTimestamp?: boolean;
  /** 自定义类名 */
  className?: string;
}

/**
 * 格式化时间戳为可读字符串
 */
function formatTimestamp(timestamp: number | null): string {
  if (!timestamp) return '未知';
  
  const now = Date.now();
  const diff = now - timestamp;
  
  // 小于 1 分钟
  if (diff < 60 * 1000) {
    return '刚刚';
  }
  // 小于 1 小时
  if (diff < 60 * 60 * 1000) {
    const minutes = Math.floor(diff / (60 * 1000));
    return `${minutes} 分钟前`;
  }
  // 小于 24 小时
  if (diff < 24 * 60 * 60 * 1000) {
    const hours = Math.floor(diff / (60 * 60 * 1000));
    return `${hours} 小时前`;
  }
  // 超过 24 小时，显示日期
  const date = new Date(timestamp);
  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * 缓存状态指示器组件
 * 
 * 显示缓存状态图标：
 * - 🔄 正在刷新
 * - ⚠️ 数据陈旧
 * - ✅ 来自缓存
 * - 🌐 来自网络
 */
export const CacheIndicator: React.FC<CacheIndicatorProps> = ({
  status,
  onRefresh,
  showTimestamp = false,
  className = '',
}) => {
  const { isFromCache, isStale, isRefreshing, lastUpdated, error } = status;

  // 确定显示的图标和文本
  let icon: string;
  let text: string;
  let colorClass: string;

  if (isRefreshing) {
    icon = '🔄';
    text = '刷新中...';
    colorClass = 'text-blue-500';
  } else if (error) {
    icon = '❌';
    text = '加载失败';
    colorClass = 'text-red-500';
  } else if (isStale) {
    icon = '⚠️';
    text = '数据可能过期';
    colorClass = 'text-yellow-500';
  } else if (isFromCache) {
    icon = '✅';
    text = '来自缓存';
    colorClass = 'text-green-500';
  } else {
    icon = '🌐';
    text = '来自网络';
    colorClass = 'text-gray-500';
  }

  return (
    <div className={`inline-flex items-center gap-1 text-xs ${colorClass} ${className}`}>
      <span title={text}>{icon}</span>
      
      {showTimestamp && lastUpdated && (
        <span className="text-gray-400" title={new Date(lastUpdated).toLocaleString('zh-CN')}>
          {formatTimestamp(lastUpdated)}
        </span>
      )}
      
      {onRefresh && !isRefreshing && (
        <button
          onClick={onRefresh}
          className="ml-1 p-0.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
          title="刷新数据"
          disabled={isRefreshing}
        >
          🔃
        </button>
      )}
    </div>
  );
};

export default CacheIndicator;
