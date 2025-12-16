/**
 * ImageCanvasControls 组件
 * 
 * 图片画布的控制按钮组件，包含：
 * - 放大 / 缩小 / 重置
 * - 全屏查看
 * - 下载
 * - 扩图跳转（可选）
 * - 对比模式切换（可选）
 */

import React from 'react';
import { Plus, Minus, RotateCcw, Maximize2, Download, Expand, SplitSquareHorizontal } from 'lucide-react';

export interface ImageCanvasControlsProps {
  /** 当前缩放比例 */
  zoom: number;
  /** 放大回调 */
  onZoomIn: (e?: React.MouseEvent) => void;
  /** 缩小回调 */
  onZoomOut: (e?: React.MouseEvent) => void;
  /** 重置回调 */
  onReset: (e?: React.MouseEvent) => void;
  /** 全屏查看回调 */
  onFullscreen?: () => void;
  /** 下载回调或 URL */
  downloadUrl?: string;
  /** 扩图跳转回调 */
  onExpand?: () => void;
  /** 对比模式切换回调 */
  onToggleCompare?: () => void;
  /** 是否处于对比模式 */
  isCompareMode?: boolean;
  /** 主题色，默认 slate */
  accentColor?: 'pink' | 'orange' | 'emerald' | 'indigo';
  /** 自定义类名 */
  className?: string;
}

export const ImageCanvasControls: React.FC<ImageCanvasControlsProps> = ({
  zoom,
  onZoomIn,
  onZoomOut,
  onReset,
  onFullscreen,
  downloadUrl,
  onExpand,
  onToggleCompare,
  isCompareMode = false,
  accentColor = 'pink',
  className = '',
}) => {
  const accentColors = {
    pink: 'bg-pink-600 hover:bg-pink-500 text-pink-400',
    orange: 'bg-orange-600 hover:bg-orange-500 text-orange-400',
    emerald: 'bg-emerald-600 hover:bg-emerald-500 text-emerald-400',
    indigo: 'bg-indigo-600 hover:bg-indigo-500 text-indigo-400',
  };

  const buttonBase = 'p-2 hover:bg-white/10 rounded-lg text-slate-300 hover:text-white transition-colors';
  const accentButton = `p-2 ${accentColors[accentColor].split(' ').slice(0, 2).join(' ')} text-white rounded-lg shadow-lg`;

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {/* 缩放控制 */}
      <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-xl p-1.5 flex flex-col gap-1 shadow-xl">
        <button onClick={onZoomIn} className={buttonBase} title="放大">
          <Plus size={18} />
        </button>
        <button onClick={onReset} className={buttonBase} title="重置视图">
          <RotateCcw size={16} />
        </button>
        <button onClick={onZoomOut} className={buttonBase} title="缩小">
          <Minus size={18} />
        </button>
        {/* 缩放比例显示 */}
        <div className="text-center text-[10px] text-slate-500 font-mono py-1 border-t border-white/10">
          {Math.round(zoom * 100)}%
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-xl p-1.5 flex flex-col gap-1 shadow-xl">
        {/* 对比模式切换 */}
        {onToggleCompare && (
          <button 
            onClick={(e) => { e.stopPropagation(); onToggleCompare(); }}
            className={`${buttonBase} ${isCompareMode ? 'bg-white/20 text-white' : ''}`}
            title={isCompareMode ? '退出对比' : '对比原图'}
          >
            <SplitSquareHorizontal size={18} />
          </button>
        )}

        {/* 扩图跳转 */}
        {onExpand && (
          <button 
            onClick={(e) => { e.stopPropagation(); onExpand(); }}
            className={`p-2 hover:bg-orange-600/80 rounded-lg ${accentColors.orange.split(' ')[2]} hover:text-white transition-colors`}
            title="扩图"
          >
            <Expand size={18} />
          </button>
        )}

        {/* 全屏查看 */}
        {onFullscreen && (
          <button 
            onClick={(e) => { e.stopPropagation(); onFullscreen(); }}
            className={buttonBase}
            title="全屏查看"
          >
            <Maximize2 size={18} />
          </button>
        )}

        {/* 下载 */}
        {downloadUrl && (
          <button 
            onClick={async (e) => {
              e.stopPropagation();
              // 判断 URL 类型
              const isBase64 = downloadUrl.startsWith('data:');
              const isBlob = downloadUrl.startsWith('blob:');
              const isCloudUrl = downloadUrl.startsWith('http://') || downloadUrl.startsWith('https://');
              
              if (isBase64 || isBlob) {
                // 同源图片：直接 fetch 下载
                const response = await fetch(downloadUrl);
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `image-${Date.now()}.png`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
              } else if (isCloudUrl) {
                // 跨域云存储 URL：通过后端代理下载
                const proxyUrl = `/api/storage/download?url=${encodeURIComponent(downloadUrl)}`;
                const a = document.createElement('a');
                a.href = proxyUrl;
                a.download = `image-${Date.now()}.png`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
              }
            }}
            className={accentButton}
            title="下载"
          >
            <Download size={18} />
          </button>
        )}
      </div>
    </div>
  );
};

export default ImageCanvasControls;
