/**
 * @file SkeletonLoader.tsx
 * @description 骨架屏加载组件，用于在数据加载时显示占位内容，提升用户体验
 */

import React from 'react';

/**
 * SkeletonLoader 组件属性
 */
export interface SkeletonLoaderProps {
  /** 骨架屏类型 */
  type?: 'text' | 'card' | 'list' | 'table';
  /** 行数（用于 text 和 list 类型） */
  rows?: number;
  /** 自定义类名 */
  className?: string;
}

/**
 * 骨架屏加载组件
 * 
 * 显示占位内容，在数据加载时提供视觉反馈，提升用户体验。
 * 
 * @example
 * ```tsx
 * <SkeletonLoader type="list" rows={5} />
 * ```
 */
export const SkeletonLoader: React.FC<SkeletonLoaderProps> = ({
  type = 'text',
  rows = 3,
  className = '',
}) => {
  const renderSkeleton = () => {
    switch (type) {
      case 'text':
        return (
          <div className="space-y-2">
            {Array.from({ length: rows }).map((_, i) => (
              <div
                key={i}
                className="h-4 bg-slate-700 rounded animate-pulse"
                style={{ width: i === rows - 1 ? '60%' : '100%' }}
              />
            ))}
          </div>
        );

      case 'card':
        return (
          <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
            <div className="h-4 bg-slate-700 rounded w-3/4 mb-3 animate-pulse" />
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-3 bg-slate-700 rounded animate-pulse"
                  style={{ width: i === 2 ? '50%' : '100%' }}
                />
              ))}
            </div>
          </div>
        );

      case 'list':
        return (
          <div className="space-y-2">
            {Array.from({ length: rows }).map((_, i) => (
              <div
                key={i}
                className="flex items-center gap-3 p-3 bg-slate-800 rounded-lg border border-slate-700"
              >
                <div className="w-10 h-10 bg-slate-700 rounded-full animate-pulse flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-slate-700 rounded w-3/4 animate-pulse" />
                  <div className="h-3 bg-slate-700 rounded w-1/2 animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        );

      case 'table':
        return (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  {Array.from({ length: 4 }).map((_, i) => (
                    <th key={i} className="px-4 py-2">
                      <div className="h-4 bg-slate-700 rounded w-20 animate-pulse mx-auto" />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: rows }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 4 }).map((_, j) => (
                      <td key={j} className="px-4 py-2">
                        <div className="h-4 bg-slate-700 rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className={`skeleton-loader ${className}`}>
      {renderSkeleton()}
    </div>
  );
};

export default SkeletonLoader;
